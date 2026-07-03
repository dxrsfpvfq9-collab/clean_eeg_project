"""Build the labels CSV for the 251 new EDFs from candidate_new_edfs.csv.

For each candidate row, parse the matched doctor's-report .docx using
dr_report_parser.parse_report() and emit a row with:
  patient_key, year, edf_path, report_path, author,
  quality, artifact_severity, artifact_free,
  pdr_freq, pdr_freq_lo,
  drowsiness, paroxysmal, clinical_abnormality,
  background (truncated), comments (truncated), valid

Output: out/new_cohort_labels.csv
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dr_report_parser import parse_report

OUT = os.path.join(HERE, "out")
CANDIDATE_CSV = os.path.join(OUT, "candidate_new_edfs.csv")
LABELS_CSV = os.path.join(OUT, "new_cohort_labels.csv")


def main():
    rows = list(csv.DictReader(open(CANDIDATE_CSV, encoding="utf-8")))
    print(f"Building labels for {len(rows)} reports...")

    fieldnames = [
        "patient_key", "year", "edf_path", "report_path",
        "author", "quality", "artifact_severity", "artifact_free",
        "pdr_freq", "pdr_freq_lo",
        "drowsiness", "paroxysmal", "clinical_abnormality",
        "background", "comments", "valid",
    ]
    with open(LABELS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        n_valid = 0
        for i, r in enumerate(rows, 1):
            res = parse_report(r["report_path"])
            if res.get("valid"):
                n_valid += 1
            out_row = {
                "patient_key": r["patient_key"],
                "year": r["year"],
                "edf_path": r["edf_path"],
                "report_path": r["report_path"],
                "author": res.get("author", ""),
                "quality": res.get("quality") or "",
                "artifact_severity": res.get("artifact_severity") or "",
                "artifact_free": res.get("artifact_free") or "",
                "pdr_freq": res.get("pdr_freq") or "",
                "pdr_freq_lo": res.get("pdr_freq_lo") or "",
                "drowsiness": res.get("drowsiness") or "",
                "paroxysmal": res.get("paroxysmal") or "",
                "clinical_abnormality": res.get("clinical_abnormality") or "",
                "background": (res.get("background") or "")[:300],
                "comments": (res.get("comments") or "")[:500],
                "valid": "1" if res.get("valid") else "0",
            }
            w.writerow(out_row)
            if i % 50 == 0:
                print(f"  parsed {i}/{len(rows)} ({n_valid} valid so far)")

    print(f"\nDone.  {n_valid}/{len(rows)} reports parsed >= 4 fields.")
    print(f"Wrote {LABELS_CSV}")


if __name__ == "__main__":
    main()
