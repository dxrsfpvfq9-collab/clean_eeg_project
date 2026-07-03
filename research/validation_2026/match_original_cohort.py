"""Match the n=100 study cohort (original spreadsheet IDs) to source EDFs
in the STS QA Reviews tree.

Strategy:
  1. For each spreadsheet Client ID, search the QA Reviews tree for a
     doctor's-report .docx (or .pdf) whose filename CONTAINS the Client ID.
  2. The corresponding EDF lives in the same session folder.  Prefer EC.
  3. When ambiguous, report all candidates so the user can confirm.

Output:
  out/original_cohort_match.csv  — one row per spreadsheet ID with the
                                    matched EDF path (or 'UNMATCHED').
"""
import csv
import os
import re
import sys
from collections import defaultdict

from openpyxl import load_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
ROOT = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
SPREADSHEET = (r"C:\BrainPanel\01_Comparison Chart BP to DR 2024_2025 "
               r"Comments Complete Added Drowsiness Column minus DOC full "
               r"txt and BP_PDR07AUG.xlsx")


def load_spreadsheet_ids():
    wb = load_workbook(SPREADSHEET, data_only=True)
    ws = wb.active
    ids = []
    for r in ws.iter_rows(min_row=4, values_only=True):
        if r[1] is None:
            continue
        ids.append(str(r[1]).strip())
    return ids


def walk_tree(root):
    """Yield (full_path, kind) for every relevant file under root."""
    for dirpath, dirs, files in os.walk(root):
        for f in files:
            low = f.lower()
            if low.endswith(".docx") and "quality assurance review" in low:
                yield (os.path.join(dirpath, f), "report")
            elif low.endswith(".pdf") and "quality assurance review" in low:
                yield (os.path.join(dirpath, f), "report_pdf")
            elif low.endswith(".edf"):
                # Tag EC-mentioning files; "other" includes EDFs with no
                # EC/EO marker (e.g., YNJP0001.edf) which we still allow
                # as candidates when no EC match exists.
                if " ec" in low or "ec." in low or "_ec" in low:
                    kind = "edf_ec"
                elif " eo" in low or "eo." in low or "_eo" in low:
                    kind = "edf_eo"
                else:
                    kind = "edf_other"
                yield (os.path.join(dirpath, f), kind)


def alternates(sid):
    """Yield candidate search keys for a spreadsheet ID, including typo
    fixes (missing leading zero) and the trailing numeric token.
    Order matters: most specific first."""
    out = [sid]
    # Jo476_1254 -> Jo0476_1254  (missing leading zero)
    m = re.match(r"^Jo(\d{3})_(.+)$", sid)
    if m:
        out.append(f"Jo0{m.group(1)}_{m.group(2)}")
    # Jo0479_1259 -> any Jo0XXX_1259 (the 1259 is the patient #)
    m = re.match(r"^Jo\d+_(.+)$", sid)
    if m:
        out.append(m.group(1))  # just the trailing patient ID
    # Plain numeric trailing token (last group of digits) as a fallback
    nums = re.findall(r"(\d{3,5})", sid)
    out.extend(nums)
    # Dedup preserving order
    seen = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def normalize_for_search(s):
    """Lowercase and remove _, -, space for fuzzy substring matching."""
    return re.sub(r"[_\-\s]", "", s.lower())


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _meaningful_tokens(s):
    """Extract identifier-like tokens (alphanumeric runs), keep only
    those that look like patient IDs / numeric tags, not common words."""
    common = {"qeeg", "eeg", "quality", "assurance", "review",
              "sts", "rt", "docx", "pdf", "edf", "ec", "eo",
              "age", "and", "for"}
    out = []
    for tok in _TOKEN_RE.findall(s.lower()):
        if tok in common:
            continue
        # Skip pure-numeric tokens that look like dates (year/month/day)
        # 4-digit year-like
        if tok.isdigit() and 1900 <= int(tok) <= 2030:
            continue
        out.append(tok)
    return out


def find_match(sid, reports_by_dir, edfs_by_dir):
    """Find the EDF that goes with this spreadsheet ID.

    Tries multiple key forms (typo fixes, trailing numeric).  For each
    matching report, picks the EDF in its directory whose filename
    shares the most tokens with the report's filename, falling back to
    any EDF in the folder if no token overlap.
    """
    matching_reports = []
    matched_via_key = None
    for key in alternates(sid):
        key_norm = normalize_for_search(key)
        if not key_norm:
            continue
        for d, reports in reports_by_dir.items():
            for report_path in reports:
                rname = os.path.basename(report_path)
                if key_norm in normalize_for_search(rname):
                    matching_reports.append(report_path)
        if matching_reports:
            matched_via_key = key
            break  # Stop at first key that finds something

    if not matching_reports:
        # Last fallback: search EDFs DIRECTLY (some IDs like YNJP have an
        # EDF without a paired QA-review doc — e.g., YNJP0001.edf).
        for key in alternates(sid):
            key_norm = normalize_for_search(key)
            if not key_norm:
                continue
            for d, kinds in edfs_by_dir.items():
                for kind in ("edf_ec", "edf_other"):
                    for edf_path in kinds.get(kind, []):
                        if key_norm in normalize_for_search(os.path.basename(edf_path)):
                            return edf_path, [(edf_path, None, 1)]
        return None, []

    # For each matching report, pair it with the SINGLE EDF in the same
    # folder whose filename contains the spreadsheet ID's PATIENT-LEVEL
    # identifier — either the full ID prefix (e.g., "TJTX00004") or the
    # trailing patient number (e.g., "1257" from "Jo0478_1257").  This
    # rejects cross-patient pollution when one folder holds many
    # patients' files (each with their own report + EDF).
    ident_keys = []
    # The full spreadsheet ID itself
    ident_keys.append(normalize_for_search(sid))
    # Trailing patient number (e.g., "1257" from "Jo0478_1257")
    m = re.match(r"^[A-Za-z]+\d*_(.+)$", sid)
    if m:
        ident_keys.append(normalize_for_search(m.group(1)))
    # Trailing numeric token
    for n in re.findall(r"\d{3,5}", sid):
        ident_keys.append(n)
    # Site-prefix (e.g., "AD00016" should match an EDF containing AD00016)
    # That's already included by the full-ID key.
    ident_keys = [k for k in ident_keys if k]

    best = None  # (score, edf_path, report_path)
    all_candidates = []
    for report_path in matching_reports:
        d = os.path.dirname(report_path)
        ec_edfs    = edfs_by_dir.get(d, {}).get("edf_ec", [])
        other_edfs = edfs_by_dir.get(d, {}).get("edf_other", [])
        for edf_path in ec_edfs + other_edfs:
            ename = normalize_for_search(os.path.basename(edf_path))
            # Score: number of ident keys that appear in the EDF filename
            score = sum(1 for k in ident_keys if k in ename)
            if edf_path in ec_edfs:
                score += 0.5  # prefer EC when ID-match score ties
            if score < 1:
                continue  # EDF doesn't bear the patient's identifier
            all_candidates.append((edf_path, report_path, score))
            if best is None or score > best[0]:
                best = (score, edf_path, report_path)

    if best is None:
        # Last-resort fallback: ANY EDF in ANY matching report's folder
        # (used for YNJP-style cases where the EDF is just "YNJP0001.edf"
        # with no shared age/date tokens with the report filename).
        for report_path in matching_reports:
            d = os.path.dirname(report_path)
            for kind in ("edf_ec", "edf_other"):
                edfs = edfs_by_dir.get(d, {}).get(kind, [])
                if edfs:
                    return edfs[0], [(p, report_path, 0) for p in edfs]
        return None, []

    return best[1], all_candidates


def main():
    print("Loading spreadsheet IDs...")
    ids = load_spreadsheet_ids()
    print(f"  {len(ids)} IDs")

    print("Indexing STS QA Reviews tree...")
    reports_by_dir = defaultdict(list)
    edfs_by_dir = defaultdict(lambda: {"edf_ec": [], "edf_other": []})
    file_count = 0
    for path, kind in walk_tree(ROOT):
        d = os.path.dirname(path)
        if kind in ("report", "report_pdf"):
            reports_by_dir[d].append(path)
        elif kind == "edf_ec":
            edfs_by_dir[d]["edf_ec"].append(path)
        elif kind == "edf_other":
            edfs_by_dir[d]["edf_other"].append(path)
        file_count += 1
    print(f"  indexed {file_count} files; "
          f"{sum(len(v) for v in reports_by_dir.values())} reports, "
          f"{sum(len(v['edf_ec']) for v in edfs_by_dir.values())} EC EDFs")

    print("Matching...")
    rows = []
    matched = 0
    multi = 0
    for sid in ids:
        primary, all_candidates = find_match(sid, reports_by_dir, edfs_by_dir)
        if primary is None:
            rows.append({
                "client_id": sid,
                "edf_path": "",
                "n_candidates": 0,
                "all_candidates": "",
                "status": "UNMATCHED",
            })
            continue
        matched += 1
        n_cand = len(all_candidates)
        if n_cand > 1:
            multi += 1
        # Tally distinct EDFs and use top-score for status
        top_score = max((s for _, _, s in all_candidates), default=0)
        good = [c for c in all_candidates if c[2] == top_score]
        rows.append({
            "client_id": sid,
            "edf_path": primary,
            "n_candidates": len(set(p for p, _, _ in all_candidates)),
            "all_candidates": " | ".join(sorted(set(
                p for p, _, _ in all_candidates))),
            "status": ("MATCHED" if len(good) == 1 and top_score > 0
                       else ("AMBIGUOUS" if top_score > 0 else "WEAK")),
        })

    print(f"  matched: {matched}/{len(ids)}")
    print(f"  ambiguous (multi-candidate): {multi}")
    print(f"  unmatched: {len(ids) - matched}")

    out_path = os.path.join(OUT, "original_cohort_match.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "client_id", "status", "n_candidates", "edf_path", "all_candidates"
        ])
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"\nWrote {out_path}")

    # Print a short sample for quick review
    print("\nSample matches (first 12 MATCHED):")
    shown = 0
    for r in rows:
        if r["status"] == "MATCHED":
            print(f"  {r['client_id']:<22} -> {os.path.basename(r['edf_path'])[:55]}")
            shown += 1
            if shown >= 12:
                break

    print("\nSample AMBIGUOUS (multi-EDF in same session folder):")
    shown = 0
    for r in rows:
        if r["status"] == "AMBIGUOUS":
            print(f"  {r['client_id']:<22} ({r['n_candidates']} cand) -> "
                  f"{os.path.basename(r['edf_path'])[:55]}")
            shown += 1
            if shown >= 5:
                break

    print("\nUNMATCHED:")
    for r in rows:
        if r["status"] == "UNMATCHED":
            print(f"  {r['client_id']}")


if __name__ == "__main__":
    main()
