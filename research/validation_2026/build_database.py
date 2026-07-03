"""Construct a new reference database from the current Brain Panel file set,
in the same format as EC_191.out_file.icale.xlsx.

Layout (matching the original):
  - columns: AVG, STD DEV, C1, C2, ... CN  (one column per source file)
  - rows:    row 0 header; rows 1-8 internal metrics; rows 9-56 = the 48
             report metrics in display order (STD Raw .. Delta Moment 3).
  - AVG / STD DEV use the SAME trimmed estimator as file_svc.py:623-628 --
    drop the top and bottom 5% of each metric's values, then mean / population
    std of the remainder.

Per-file metric VALUES are read from the saved report PDFs (the "Value"
column). Rows 1-8 are auxiliary (not z-scored on the report); their AVG/STD are
carried forward from the original DB and per-file cells left blank.

Default file set: valid eyes-closed panels of one ML version (v2025_brainml) so
the norms are internally consistent. Override COHORT_VERSIONS in config to widen.
"""
import csv
import os
import sys

import numpy as np
from openpyxl import Workbook, load_workbook

import config
import panel_parser as pp

sys.path.insert(0, config.REPO_ROOT)
from process import discriminant  # noqa: E402

NAME_STRINGS = pp.NAME_STRINGS                 # 48 report metrics (rows 9-56)
ORIG_DB = os.path.join(config.REPO_ROOT, "EC_191.out_file.icale.xlsx")
OUT_DB = os.path.join(config.OUT_DIR, "EC_NEW.out_file.icale.xlsx")
N_INTERNAL = 8                                  # rows 1-8 (mymetrics 0-7)
VERSIONS = ["v2025_brainml"]                     # file set for the new DB


def trimmed_avg_std(values):
    """Replicates file_svc.remove_outliers: drop top/bottom 5%, then mean/std."""
    v = np.sort(np.asarray([x for x in values if x == x], float))
    n = len(v)
    k = int(0.05 * n)
    core = v[k:n - k] if k > 0 else v
    if core.size == 0:
        core = v
    return float(core.mean()), float(core.std())  # np std -> population (ddof=0)


def load_panels():
    rows = [r for r in csv.DictReader(
        open(os.path.join(config.OUT_DIR, "manifest_ec_features.csv"), encoding="utf-8"))
        if r["version"] in VERSIONS and r["valid"] == "True"]
    print(f"Source files: {len(rows)} valid EC panels ({'/'.join(VERSIONS)})")
    cols = []  # list of (label, 48-value-vector)
    for i, r in enumerate(rows, 1):
        parsed = pp.parse_panel_pdf(r["ec_panel_path"])
        cols.append((f"C{i}", parsed["values"]))
        if i % 25 == 0:
            print(f"   parsed {i}/{len(rows)}")
    return cols


def main():
    cols = load_panels()
    n = len(cols)
    # 48 x n matrix of report-metric values
    M = np.array([vec for _lbl, vec in cols], float).T   # rows=metric, cols=file
    assert M.shape[0] == 48

    # original DB for carry-forward of the 8 internal rows + comparison
    orig = list(load_workbook(ORIG_DB, data_only=True, read_only=True).active
                .iter_rows(values_only=True))

    wb = Workbook(); ws = wb.active
    ws.append(["AVG", "STD DEV"] + [lbl for lbl, _ in cols])

    # rows 1-8 : carry original AVG/STD, blank per-file cells
    for ri in range(1, N_INTERNAL + 1):
        avg = orig[ri][0] if ri < len(orig) else None
        std = orig[ri][1] if ri < len(orig) else None
        ws.append([avg, std] + [None] * n)

    # rows 9-56 : the 48 report metrics, rebuilt from current files
    new_stats = []
    for mi in range(48):
        vals = M[mi]
        avg, std = trimmed_avg_std(vals)
        new_stats.append((avg, std))
        ws.append([round(avg, 4), round(std, 4)] + [round(float(x), 4) if x == x else None for x in vals])

    wb.save(OUT_DB)
    print(f"\nWrote {OUT_DB}  ({57} rows x {n + 2} cols)")

    # comparison vs original (rows 9-56 -> original rows 9..56)
    comp = [["metric", "orig_AVG", "new_AVG", "orig_STD", "new_STD", "AVG_%chg"]]
    print(f"\n{'metric':18s} {'orig_AVG':>10} {'new_AVG':>10} {'orig_STD':>9} {'new_STD':>9} {'AVGchg%':>7}")
    for mi, name in enumerate(NAME_STRINGS):
        orow = orig[9 + mi]
        oavg = float(orow[0]) if isinstance(orow[0], (int, float)) else float("nan")
        ostd = float(orow[1]) if isinstance(orow[1], (int, float)) else float("nan")
        navg, nstd = new_stats[mi]
        chg = 100 * (navg - oavg) / oavg if oavg else float("nan")
        comp.append([name, round(oavg, 3), round(navg, 3), round(ostd, 3), round(nstd, 3),
                     round(chg, 1) if chg == chg else ""])
        flag = "  <== version artifact" if name == "Global STD" else (
            "  *" if abs(chg) >= 25 and chg == chg else "")
        print(f"{name:18s} {oavg:>10.2f} {navg:>10.2f} {ostd:>9.2f} {nstd:>9.2f} "
              f"{chg:>6.0f}%{flag}")
    with open(os.path.join(config.OUT_DIR, "database_comparison.csv"), "w",
              newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(comp)
    print("\nWrote out/database_comparison.csv")
    print("\nNOTE: Global STD (row 10) reflects the x1000 reconstruction artifact "
          "in v2025 panels (constant ~1000, std~0). Rebuild this row after the "
          "Global-STD code fix; all other metrics carry valid current norms.")


if __name__ == "__main__":
    main()
