"""Walk the STS QA Reviews tree and find every session folder containing
an EC EDF + a doctor's quality-assurance report (.docx) where no
.icale.rep.pdf has been produced yet.  These are candidates for
expanding the validation cohort.

For each candidate folder, emit:
  - the EC EDF path
  - the matched doctor's report (.docx)
  - a likely patient_key (hash of identifier tokens)
  - the year the session occurred (parent folder)

Also report counts broken down by year and by why an EDF was skipped.

Output: out/candidate_new_edfs.csv  +  summary printed to stdout.
"""
import csv
import hashlib
import os
import re
import sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "out")
ROOT = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"


def patient_key(client_filename):
    """Anonymized hash of the identifier tokens in an EDF filename.
    Same algorithm as the original validation cohort's patient_key."""
    base = os.path.basename(client_filename).lower()
    base = re.sub(r"\.edf$", "", base)
    # Extract alphanumeric identifier tokens (drop common words)
    common = {"qeeg", "eeg", "age", "ec", "eo", "clean", "unclean",
              "recon", "review", "quality", "assurance"}
    toks = [t for t in re.findall(r"[a-z0-9]+", base) if t not in common]
    s = "|".join(sorted(set(toks)))
    return "pk_" + hashlib.md5(s.encode()).hexdigest()[:12]


def has_pdf(edf_path):
    """Check whether a Brain Panel report exists for this EDF in standard
    locations (next to it, in output/, or in output version 1/)."""
    bn = os.path.basename(edf_path).replace(".edf", "")
    d = os.path.dirname(edf_path)
    for sub in ("", "output", "output version 1"):
        cand = os.path.join(d, sub, bn + ".icale.rep.pdf")
        if os.path.exists(cand):
            return cand
    return None


def is_ec(edf_basename):
    low = edf_basename.lower()
    return " ec" in low or "_ec" in low or low.endswith("ec.edf")


def session_year(path):
    """Best-effort extract of the session year from the path."""
    for part in path.split(os.sep):
        m = re.match(r"^(\d{4})(?:\s|$|\.|-)", part)
        if m:
            return m.group(1)
    return "unknown"


def main():
    print("Walking STS QA Reviews tree...")
    edfs_by_dir = defaultdict(list)
    reports_by_dir = defaultdict(list)

    n_files = 0
    for dp, dirs, files in os.walk(ROOT):
        for f in files:
            n_files += 1
            low = f.lower()
            full = os.path.join(dp, f)
            if low.endswith(".edf"):
                # Skip cleaned/recon/derived variants — only original EDFs
                if any(s in low for s in (".clean.", ".unclean.",
                                          ".recon.", ".clean1.", ".clean2.")):
                    continue
                if is_ec(f):
                    edfs_by_dir[dp].append(full)
            elif low.endswith(".docx") and "quality assurance review" in low:
                reports_by_dir[dp].append(full)
    print(f"  {n_files} total files indexed; "
          f"{sum(len(v) for v in edfs_by_dir.values())} EC EDFs, "
          f"{sum(len(v) for v in reports_by_dir.values())} review docs")
    print()

    # For each EC EDF, check whether the same folder has a report AND
    # the EDF lacks a Brain Panel PDF.
    candidates = []
    skipped = Counter()
    n_with_pdf = 0
    n_no_report = 0
    n_no_pdf_with_report = 0

    for d, edfs in edfs_by_dir.items():
        reports = reports_by_dir.get(d, [])
        for edf in edfs:
            existing = has_pdf(edf)
            if existing:
                n_with_pdf += 1
                skipped["already has Brain Panel PDF"] += 1
                continue
            if not reports:
                n_no_report += 1
                skipped["no report in folder"] += 1
                continue
            # Pick the most likely report for this EDF -- one whose
            # filename shares a token with the EDF.  If multiple, prefer
            # the one with the most token-overlap; if none share, use the
            # alphabetically-first report (it might just be a folder with
            # multiple patients).
            edf_toks = set(re.findall(r"[a-z0-9]+", os.path.basename(edf).lower()))
            best = None
            for rp in reports:
                rtoks = set(re.findall(r"[a-z0-9]+",
                                       os.path.basename(rp).lower()))
                overlap = edf_toks & rtoks - {"qeeg", "eeg", "age", "ec",
                                              "01", "02", "03"}
                score = len(overlap)
                if best is None or score > best[0]:
                    best = (score, rp)
            chosen_report = best[1] if best else reports[0]
            n_no_pdf_with_report += 1
            candidates.append({
                "patient_key": patient_key(edf),
                "year": session_year(edf),
                "edf_path": edf,
                "report_path": chosen_report,
                "session_dir": d,
                "report_token_overlap": str(best[0]) if best else "0",
            })

    # Summary
    print("=" * 70)
    print(f"EC EDFs already with Brain Panel PDF:        {n_with_pdf}")
    print(f"EC EDFs without report in their folder:      {n_no_report}")
    print(f"EC EDFs *without* PDF *with* report:         {n_no_pdf_with_report}")
    print(f"  (these are candidate new EDFs to process)")
    print("=" * 70)
    print()

    # By year
    yearly = Counter()
    for c in candidates:
        yearly[c["year"]] += 1
    print("Candidate EDFs by year:")
    for y in sorted(yearly):
        print(f"  {y}: {yearly[y]}")
    print()

    # By session sub-directory (informative)
    by_dir = Counter()
    for c in candidates:
        rel = os.path.relpath(c["session_dir"], ROOT)
        by_dir[rel] += 1
    print(f"Distinct session folders contributing candidates: {len(by_dir)}")
    print("Top 12 session folders by candidate count:")
    for d, n in by_dir.most_common(12):
        print(f"  {n:>3}  {d[:75]}")
    print()

    # Token-overlap quality distribution (how well-matched the
    # EDF->report pairings are)
    overlap_dist = Counter()
    for c in candidates:
        overlap_dist[c["report_token_overlap"]] += 1
    print("EDF<->report token-overlap quality:")
    for k in sorted(overlap_dist, key=int, reverse=True):
        print(f"  overlap={k}: {overlap_dist[k]} candidates")
    print()

    # Compare against existing validation cohort to flag duplicates
    existing_keys = set()
    cohort_csv = os.path.join(OUT, "study_cohort.csv")
    if os.path.exists(cohort_csv):
        with open(cohort_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing_keys.add(row["patient_key"])
    n_overlap = sum(1 for c in candidates if c["patient_key"] in existing_keys)
    print(f"Candidates already in n=98 validation cohort (by patient_key):"
          f" {n_overlap}")
    n_overlap_orig = 0
    orig_match_csv = os.path.join(OUT, "original_cohort_match.csv")
    if os.path.exists(orig_match_csv):
        orig_paths = set()
        with open(orig_match_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["edf_path"]:
                    orig_paths.add(os.path.normpath(row["edf_path"]).lower())
        n_overlap_orig = sum(1 for c in candidates
                              if os.path.normpath(c["edf_path"]).lower()
                              in orig_paths)
    print(f"Candidates that match the original n=100 cohort:"
          f" {n_overlap_orig}")
    truly_new = len(candidates) - n_overlap - n_overlap_orig
    print(f"Truly new EDFs (not in either previous cohort):"
          f" ~{truly_new}")
    print()

    # Save CSV
    out_csv = os.path.join(OUT, "candidate_new_edfs.csv")
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "patient_key", "year", "edf_path", "report_path",
            "session_dir", "report_token_overlap",
        ])
        w.writeheader()
        for c in candidates:
            w.writerow(c)
    print(f"Wrote {out_csv}  ({len(candidates)} rows)")


if __name__ == "__main__":
    main()
