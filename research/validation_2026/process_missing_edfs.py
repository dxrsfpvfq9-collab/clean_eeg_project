"""Batch-run the Brain Panel pipeline on the 23 EDFs from the original
n=100 cohort that don't yet have a .icale.rep.pdf.

Mirrors test_discriminant.py's setup but runs the standard report only
(selstring[6]=1 ICALE + selstring[8]=1 standard PDF) -- no discriminant
report needed for the z-score parsing.

Output PDFs land next to each source EDF.  Progress goes to:
  out/process_missing_edfs.log
"""
import csv
import os
import sys
import time
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

import files.allocate_data_array  # noqa: E402
import files.edftotextbynameplotproc  # noqa: E402

OUT = os.path.join(HERE, "out")
MATCH_CSV = os.path.join(OUT, "original_cohort_match.csv")
LOG_PATH = os.path.join(OUT, "process_missing_edfs.log")
DATABASE_NAME = ""
EXCEL_FILE = "EC_191.out_file.icale.xlsx"


def find_pdf(edf_path):
    if not edf_path:
        return None
    bn = os.path.basename(edf_path).replace(".edf", "")
    d = os.path.dirname(edf_path)
    for sub in ("", "output", "output version 1"):
        cand = os.path.join(d, sub, bn + ".icale.rep.pdf")
        if os.path.exists(cand):
            return cand
    return None


def collect_missing():
    rows = list(csv.DictReader(open(MATCH_CSV, encoding="utf-8")))
    missing = []
    for r in rows:
        if not r["edf_path"]:
            continue
        if find_pdf(r["edf_path"]) is None and os.path.exists(r["edf_path"]):
            missing.append((r["client_id"], r["edf_path"]))
    return missing


def process_one(client_id, filepath, logf):
    """Run the standard ICALE pipeline on one EDF; emits .icale.rep.pdf
    next to the source.  Returns (ok, duration_s, error_str)."""
    t0 = time.time()
    err = ""
    try:
        # Mirror test_discriminant.py setup -- but standard report only.
        current_data = files.allocate_data_array.allocate_data_array(20, 512)
        files.allocate_data_array.process_data_array(current_data)

        dirpath = os.path.dirname(filepath)
        file = os.path.basename(filepath)
        outname = dirpath + "/"
        if not os.path.exists(outname):
            os.mkdir(outname)
        dirtouse1 = filepath[:-4]
        outputdir1 = (dirpath + "/" + file)[:-4]

        selstring = np.zeros(16)
        selstring[6] = 1   # ICALE montage
        selstring[8] = 1   # standard report PDF

        try:
            files.edftotextbynameplotproc.edf_to_text_by_name_plot_proc(
                dirtouse1, outputdir1, 1, 2560, 6,
                selstring, outname, DATABASE_NAME, EXCEL_FILE,
            )
        except TypeError:
            # Some signatures return None; ignore mismatch from positional unpack
            pass

        # Verify the PDF actually landed
        expected = outputdir1 + ".icale.rep.pdf"
        if os.path.exists(expected):
            ok = True
        else:
            ok = False
            err = f"expected PDF not found: {expected}"
    except Exception as e:
        ok = False
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}"
    dur = time.time() - t0
    logf.write(f"[{time.strftime('%H:%M:%S')}] {client_id!r:<24} "
               f"{'OK ' if ok else 'FAIL'} {dur:5.1f}s  "
               f"{os.path.basename(filepath)[:60]}\n")
    if err:
        logf.write(f"    error: {err[:200]}\n")
    logf.flush()
    return ok, dur, err


def main():
    os.chdir(PROJECT_ROOT)  # pipeline expects EXCEL_FILE in cwd

    missing = collect_missing()
    print(f"Found {len(missing)} EDFs needing processing.\n")
    if not missing:
        print("Nothing to do.")
        return

    with open(LOG_PATH, "w", encoding="utf-8") as logf:
        logf.write(f"# Processing {len(missing)} EDFs at "
                   f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        ok_count = 0
        fail_count = 0
        total_dur = 0.0
        for idx, (cid, edf) in enumerate(missing, 1):
            print(f"[{idx:2d}/{len(missing)}] {cid:<24} "
                  f"-> {os.path.basename(edf)[:55]}", flush=True)
            ok, dur, err = process_one(cid, edf, logf)
            total_dur += dur
            if ok:
                ok_count += 1
                print(f"             OK   ({dur:.0f}s)")
            else:
                fail_count += 1
                print(f"             FAIL ({dur:.0f}s)  {err[:120]}")

        summary = (f"\nDone.  {ok_count} OK, {fail_count} FAIL, "
                   f"total {total_dur/60:.1f} min.")
        print(summary)
        logf.write(summary + "\n")


if __name__ == "__main__":
    main()
