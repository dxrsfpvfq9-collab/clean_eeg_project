"""Batch-run the Brain Panel pipeline on the 251 new EDFs from
candidate_new_edfs.csv.  Single labeler: P. David Ims.

Mirrors process_missing_edfs.py but iterates over the candidate CSV
rather than the original cohort match CSV.  Each EDF gets the standard
ICALE + report PDF (selstring[6]=1 and selstring[8]=1).

Output:
  Per-EDF .icale.rep.pdf next to the source EDF.
  Progress log at out/process_new_cohort.log.
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
CANDIDATE_CSV = os.path.join(OUT, "candidate_new_edfs.csv")
LOG_PATH = os.path.join(OUT, "process_new_cohort.log")
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


def process_one(client_key, filepath, logf):
    """Run the standard ICALE pipeline on one EDF."""
    t0 = time.time()
    err = ""
    try:
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
                selstring, outname, "", EXCEL_FILE,
            )
        except TypeError:
            pass

        expected = outputdir1 + ".icale.rep.pdf"
        ok = os.path.exists(expected)
        if not ok:
            err = f"expected PDF not found: {expected}"
    except Exception as e:
        ok = False
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}"
    dur = time.time() - t0
    logf.write(f"[{time.strftime('%H:%M:%S')}] {client_key!r:<26} "
               f"{'OK ' if ok else 'FAIL'} {dur:5.1f}s  "
               f"{os.path.basename(filepath)[:55]}\n")
    if err:
        logf.write(f"    error: {err[:200]}\n")
    logf.flush()
    return ok, dur, err


def main():
    os.chdir(PROJECT_ROOT)

    rows = list(csv.DictReader(open(CANDIDATE_CSV, encoding="utf-8")))
    # Skip any already-completed (in case of resume after partial run)
    todo = []
    for r in rows:
        if not r["edf_path"] or not os.path.exists(r["edf_path"]):
            continue
        if find_pdf(r["edf_path"]) is not None:
            continue
        todo.append(r)

    print(f"Found {len(todo)} EDFs to process out of {len(rows)} candidates.\n")
    if not todo:
        print("Nothing to do.")
        return

    with open(LOG_PATH, "w", encoding="utf-8") as logf:
        logf.write(f"# Processing {len(todo)} EDFs at "
                   f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        logf.write("# Labeler: P. David Ims (single rater)\n\n")
        ok_count = 0
        fail_count = 0
        total_dur = 0.0
        for idx, r in enumerate(todo, 1):
            cid = r["patient_key"]
            edf = r["edf_path"]
            print(f"[{idx:3d}/{len(todo)}] {cid:<24} "
                  f"({r['year']})  {os.path.basename(edf)[:50]}",
                  flush=True)
            ok, dur, err = process_one(cid, edf, logf)
            total_dur += dur
            if ok:
                ok_count += 1
            else:
                fail_count += 1
                print(f"            FAIL ({dur:.0f}s)  {err[:120]}")

        summary = (f"\nDone.  {ok_count} OK, {fail_count} FAIL, "
                   f"total {total_dur/60:.1f} min.")
        print(summary)
        logf.write(summary + "\n")


if __name__ == "__main__":
    main()
