"""Rebuild a reference database from a folder of EDFs using the CURRENT (fixed)
pipeline, the same way EC_191 was built (directory mode): each file appends a
column and AVG/STD are the trimmed estimator inside metrics_to_excel_file.

We drive the workhorse directly with an incrementing plot_num and:
  selstring[6]=1  montage 6 (ICALE)
  selstring[9]=1  write metrics to the database  (out_file)
  selstring[8]=0  SKIP the report PDF (fast; we only want the metrics)

Usage:  py build_db_from_edfs.py <src_folder> <database_name> [limit]
Output: ./<database_name>.out_file.icale.xlsx  (in the repo root / CWD)
"""
import builtins
import os
import re
import sys
import time

import numpy as np

# ---- silence the pipeline's very verbose logging (this dominates runtime).
# We do it here in the driver so the pipeline source stays untouched. A no-op
# print skips formatting huge numpy arrays entirely; progress goes to stderr.
_real_print = builtins.print
builtins.print = lambda *a, **k: None
try:
    import mne
    mne.set_log_level("ERROR")
except Exception:
    pass


def progress(msg):
    _real_print(msg, file=sys.stderr, flush=True)


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)  # out_file is written relative to CWD; keep it at repo root
import files.edftotextbynameplotproc as work  # noqa: E402
import files.file_svc as _fs  # noqa: E402

# The pipeline writes big per-file byproducts we don't need for a database build
# (a text dump + an xlsx dump of the full EEG, and a component-metrics file).
# metrics_to_excel_file (the actual DB writer) is kept. No-op the rest.
_fs.data_to_text_file = lambda *a, **k: None
_fs.data_to_excel_file = lambda *a, **k: None
_fs.comps_to_excel_file = lambda *a, **k: None

# Capture (filename, age, 56 metrics) per file for the age-regression table,
# by wrapping the DB writer. Age comes from the "AGE nn" token in the filename.
_AGE_RE = re.compile(r"\bAGE\s*(\d{1,3})", re.I)
_age_rows = []
_orig_mte = _fs.metrics_to_excel_file


def _capture_mte(name, metrics, plot_num, montage, database_name):
    b = os.path.basename(name)
    m = _AGE_RE.search(b)
    age = int(m.group(1)) if m else ""
    _age_rows.append([b, age] + [float(x) for x in metrics])
    return _orig_mte(name, metrics, plot_num, montage, database_name)


_fs.metrics_to_excel_file = _capture_mte

VARIANT = re.compile(r"\.(clean1?|recon|unclean)\.edf$", re.I)
ECRE = re.compile(r"(?<![A-Za-z])EC(?![A-Za-z])", re.I)


def primary_ec_edfs(folder):
    # Process every non-variant EDF in the (pre-staged, condition-specific)
    # folder. Do NOT re-filter by EC/EO here -- staging already selected the
    # condition, and re-filtering silently dropped EO files.
    fs = [f for f in os.listdir(folder)
          if f.lower().endswith(".edf") and not VARIANT.search(f)
          and "disregard" not in f.lower()]
    return sorted(fs)


def main():
    src = sys.argv[1]
    dbname = sys.argv[2]
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    count = int(sys.argv[4]) if len(sys.argv) > 4 else None

    edfs = primary_ec_edfs(src)
    edfs = edfs[start:start + count] if count else edfs[start:]
    progress(f"Building DB '{dbname}' chunk [{start}:{start + len(edfs)}] "
             f"= {len(edfs)} EDFs")

    selstring = np.zeros(16)
    selstring[6] = 1   # montage 6
    selstring[8] = 0   # no report PDF
    selstring[9] = 1   # write metrics to database
    excel_file_path = os.path.join(REPO_ROOT, "EC_191.out_file.icale.xlsx")

    t0 = time.time()
    ok = err = 0
    for i, f in enumerate(edfs, 1):
        filepath = os.path.join(src, f)
        base = filepath[:-4]
        outname = src + os.sep
        try:
            work.edf_to_text_by_name_plot_proc(
                base, base, i, 2560, 6, selstring, outname, dbname, excel_file_path)
            ok += 1
        except Exception as exc:
            err += 1
            progress(f"  ERR [{i}] {f}: {type(exc).__name__}: {exc}")
        el = time.time() - t0
        progress(f"[{i}/{len(edfs)}] {f[:45]:45s}  ({el/i:.1f}s/file avg)")
    # age-regression rows: filename, age, m0..m55  (48 report metrics = m8..m55)
    import csv as _csv
    ar = os.path.join(os.path.dirname(__file__), "out", f"{dbname}.agerows.csv")
    with open(ar, "w", newline="", encoding="utf-8") as fh:
        _csv.writer(fh).writerows(_age_rows)
    progress(f"\nDone: {ok} ok, {err} err in {(time.time()-t0)/60:.1f} min")
    progress(f"age rows -> {ar}")


if __name__ == "__main__":
    main()
