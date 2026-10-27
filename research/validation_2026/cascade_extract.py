# cascade_extract.py
# Extract the per-component summary table (page 2) from every rendered
# .imagecascade.pdf under a root, into one tidy CSV: one row per
# (recording, ICA component). No recompute -- reads the rendered PDFs.
#
# Columns captured from the cascade table:
#   comp_no, pct, max_site, rsi, machine, user, lobe, region, area, fft_peak
# Plus metadata parsed from the filename / path:
#   file, folder(top-level), rel_path, subject, age, condition(EC/EO), n_comp
#
# Usage:
#   py cascade_extract.py ["<root>"] [--out=<csv>] [--top=2026]

import os
import re
import sys
import glob
import csv

import fitz  # PyMuPDF

DEFAULT_ROOT = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"

HEADER_TOKENS = ["Comp.", "%", "Max", "RSI", "Machine", "User",
                 "Lobe", "Region", "Area", "FFT"]
FIELDS = ["comp_no", "pct", "max_site", "rsi", "machine", "user",
          "lobe", "region", "area", "fft_peak"]


def cluster_rows(words, ytol=4.0):
    """Group (x0,y0,x1,y1,word,...) tuples into rows by y0."""
    rows = []
    for w in sorted(words, key=lambda t: (t[1], t[0])):
        y = w[1]
        if rows and abs(y - rows[-1][0]) <= ytol:
            rows[-1][1].append(w)
        else:
            rows.append([y, [w]])
    return [sorted(r[1], key=lambda t: t[0]) for r in rows]


def column_starts(header_row):
    """x0 of each of the 10 columns, from the header tokens."""
    starts = []
    used = set()
    for tok in HEADER_TOKENS:
        best = None
        for i, w in enumerate(header_row):
            if i in used:
                continue
            if w[4] == tok:
                best = (i, w[0])
                break
        if best is None:
            return None
        used.add(best[0])
        starts.append(best[1])
    return starts


def assign_columns(row_words, starts, tol=2.0):
    cells = [[] for _ in starts]
    for w in row_words:
        x0 = w[0]
        col = 0
        for i, s in enumerate(starts):
            if x0 + tol >= s:
                col = i
            else:
                break
        cells[col].append(w[4])
    return [" ".join(c).strip() for c in cells]


def parse_meta(pdf_path, root):
    base = os.path.basename(pdf_path)[:-len(".imagecascade.pdf")]
    rel = os.path.relpath(pdf_path, root)
    folder = rel.split(os.sep)[0]
    m_age = re.search(r"AGE\s*(\d+)", base, re.IGNORECASE)
    age = int(m_age.group(1)) if m_age else ""
    cond = ""
    bl = base.lower()
    # condition: last standalone EC/EO token wins
    toks = re.findall(r"\b(ec|eo)\b", bl)
    if toks:
        cond = toks[-1].upper()
    # subject guess: leading id/name up to first "AGE"
    subj = re.split(r"\s*AGE\s*\d+", base, flags=re.IGNORECASE)[0].strip()
    return base, folder, rel, subj, age, cond


def extract_pdf(pdf_path, root):
    try:
        d = fitz.open(pdf_path)
    except Exception as e:
        return None, f"open-failed: {e}"
    if d.page_count < 2:
        d.close()
        return None, "too-few-pages"
    words = d[1].get_text("words")
    d.close()
    if not words:
        return None, "no-text-page2"
    rows = cluster_rows(words)
    # find header row (the one containing 'Comp.')
    hdr_idx = None
    for i, r in enumerate(rows):
        toks = [w[4] for w in r]
        if "Comp." in toks and "Region" in toks:
            hdr_idx = i
            break
    if hdr_idx is None:
        return None, "no-header"
    starts = column_starts(rows[hdr_idx])
    if starts is None:
        return None, "bad-header"
    base, folder, rel, subj, age, cond = parse_meta(pdf_path, root)
    out = []
    for r in rows[hdr_idx + 1:]:
        cells = assign_columns(r, starts)
        # a valid data row: comp_no integer, pct float-ish
        if not re.fullmatch(r"\d+", cells[0] or ""):
            continue
        rec = dict(zip(FIELDS, cells))
        rec.update(file=base, folder=folder, rel_path=rel,
                   subject=subj, age=age, condition=cond)
        out.append(rec)
    for rec in out:
        rec["n_comp"] = len(out)
    return out, None


def main():
    args = sys.argv[1:]
    top = None
    out_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "out", "cascade_components.csv")
    roots = []
    for a in args:
        if a.startswith("--out="):
            out_csv = a.split("=", 1)[1]
        elif a.startswith("--top="):
            top = a.split("=", 1)[1]
        elif not a.startswith("--"):
            roots.append(a)
    if not roots:
        roots = [DEFAULT_ROOT]
    root = roots[0]

    pdfs = glob.glob(os.path.join(root, "**", "*.imagecascade.pdf"),
                     recursive=True)
    if top is not None:
        pdfs = [p for p in pdfs
                if top in os.path.relpath(p, root).split(os.sep)[0]]
    pdfs.sort()
    print(f"Root: {root}")
    print(f"Cascade PDFs found: {len(pdfs)}"
          + (f"  (top~{top})" if top else ""))

    all_rows = []
    skipped = []
    for i, p in enumerate(pdfs, 1):
        rows, err = extract_pdf(p, root)
        if err:
            skipped.append((os.path.basename(p), err))
            continue
        all_rows.extend(rows)
        if i % 25 == 0:
            print(f"  {i}/{len(pdfs)} parsed, {len(all_rows)} component rows")

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    cols = ["file", "folder", "condition", "age", "subject", "n_comp",
            "comp_no", "pct", "max_site", "rsi", "machine", "user",
            "lobe", "region", "area", "fft_peak", "rel_path"]
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols)
        wr.writeheader()
        for r in all_rows:
            wr.writerow({k: r.get(k, "") for k in cols})

    n_files = len(set(r["file"] for r in all_rows))
    print(f"\nWrote {out_csv}")
    print(f"Recordings parsed: {n_files}   component rows: {len(all_rows)}")
    if skipped:
        print(f"Skipped {len(skipped)}:")
        for name, why in skipped[:20]:
            print("  ", why, "-", name)


if __name__ == "__main__":
    main()
