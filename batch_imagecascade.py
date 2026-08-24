# batch_imagecascade.py
# Run the IMG cascade (selstring[12]=1) over a folder of EDF files, producing
# <edfname>.imagecascade.pdf next to each source EDF.
#
# Usage:
#   py batch_imagecascade.py "<folder-with-edfs>"          # process a folder
#   py batch_imagecascade.py "<folder>" --redo             # re-render even if PDF exists
#   py batch_imagecascade.py --list "<folder>"             # just list what WOULD run
#
# Notes:
#   * Skips *.clean.edf and *.unclean.edf variants (keeps one panel per subject).
#   * Skips an EDF whose .imagecascade.pdf already exists (unless --redo).
#   * IMPORTANT: cascade rendering uses ImageGrab of an on-screen Tk window, so
#     this must run on the active desktop session and will flash windows the
#     whole time. Do not cover the flashing windows or the captures corrupt.

import os
import sys
import time
import glob
import shutil
import subprocess
import traceback

import numpy as np

import files.allocate_data_array
import files.edftotextbynameplotproc

# Abort the batch if free space on the output drive ever drops below this many
# GB. A single cascade PDF is ~7 MB, so 10 GB is a large safety margin -- the
# guard exists so a runaway/other process filling the disk cannot corrupt a
# partial write or lock up the machine.
MIN_FREE_GB = 10.0

# Per-file wall-clock cap. A real cascade renders in ~1.5-13 min; a file that
# exceeds this has hung (Tk/ImageGrab or source-localization deadlock) and is
# killed so ONE bad file can't freeze the whole unattended batch (this happened
# on '1345 Sarya T ... EO' -- stalled 38 h). 0 disables (in-process, no cap).
PER_FILE_TIMEOUT = 1500  # seconds (25 min)

_PROJ_ROOT = os.path.dirname(os.path.abspath(__file__))


def render_subprocess(filepath, timeout):
    """Render one cascade in an isolated subprocess with a hard timeout. On
    timeout, kill the whole process tree (Tk children included) and report."""
    cascade = filepath[:-4] + ".imagecascade.pdf"
    proc = subprocess.Popen(
        ["py", "test_imagecascade.py", filepath],
        cwd=_PROJ_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=30)
        except Exception:
            pass
        return cascade, "timeout"
    return cascade, None


def free_gb(path):
    return shutil.disk_usage(path).free / (1024 ** 3)


def find_edfs(folder, recursive=True, order="mtime"):
    if recursive:
        edfs = glob.glob(os.path.join(folder, "**", "*.edf"), recursive=True)
    else:
        edfs = glob.glob(os.path.join(folder, "*.edf"))
    keep = []
    for p in edfs:
        low = p.lower()
        if low.endswith(".clean.edf") or low.endswith(".unclean.edf"):
            continue
        keep.append(p)
    if order == "mtime":
        # newest first (reverse chronological)
        keep.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    else:
        keep.sort()
    return keep


def run_one(filepath):
    dirpath = os.path.dirname(filepath)
    file = os.path.basename(filepath)

    database_name = ""
    excel_file_path = "EC_191.out_file.icale.xlsx"
    outname = dirpath + "/"

    dirtouse1 = filepath[:-4]
    outputdir1 = (dirpath + "/" + file)[:-4]

    selstring = np.zeros(16)
    selstring[6] = 1    # ICALE montage
    selstring[8] = 1    # standard report PDF
    selstring[12] = 1   # IMG cascade

    try:
        files.edftotextbynameplotproc.edf_to_text_by_name_plot_proc(
            dirtouse1, outputdir1, 1, 2560, 6,
            selstring, outname, database_name, excel_file_path,
        )
    except TypeError:
        pass  # matches test_imagecascade.py: the proc returns None on this path

    return outputdir1 + ".imagecascade.pdf"


def main():
    args = [a for a in sys.argv[1:]]
    list_only = "--list" in args
    redo = "--redo" in args
    flat = "--flat" in args              # only the top folder, no recursion
    name_order = "--name-order" in args  # alphabetical instead of newest-first
    limit = None
    top = None                           # keep only EDFs whose top-level
    filelist = None                      # subfolder (under root) contains this
    timeout = PER_FILE_TIMEOUT           # per-file wall-clock cap (0 disables)
    for a in args:
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])
        if a.startswith("--top="):
            top = a.split("=", 1)[1]
        if a.startswith("--filelist="):
            filelist = a.split("=", 1)[1]
        if a.startswith("--timeout="):
            timeout = int(a.split("=", 1)[1])
        if a == "--no-timeout":
            timeout = 0
    args = [a for a in args if not a.startswith("--")]

    # --filelist mode: render an explicit list of EDF paths (scattered across
    # folders), newest-first, skipping any that already have a cascade.
    if filelist is not None:
        with open(filelist, encoding="utf-8") as fh:
            edfs = [ln.strip() for ln in fh if ln.strip()
                    and ln.strip().lower().endswith(".edf")]
        edfs = [p for p in edfs if os.path.exists(p)]
        edfs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        current_data = files.allocate_data_array.allocate_data_array(20, 512)
        files.allocate_data_array.process_data_array(current_data)
        todo = [p for p in edfs
                if redo or not os.path.exists(p[:-4] + ".imagecascade.pdf")]
        if limit is not None:
            todo = todo[:limit]
        print(f"Filelist: {filelist}")
        print(f"EDFs listed/existing: {len(edfs)}   to render: {len(todo)}")
        log_dir = os.path.dirname(os.path.abspath(filelist))
        _run_todo(todo, os.path.join(log_dir, "_filelist_cascade.log"), timeout)
        return

    if not args:
        print("Usage: py batch_imagecascade.py \"<folder-with-edfs>\" [--redo] [--list]")
        sys.exit(1)

    folder = args[0]
    edfs = find_edfs(folder, recursive=not flat,
                     order="name" if name_order else "mtime")

    if top is not None:
        def top_component(p):
            rel = os.path.relpath(p, folder)
            return rel.split(os.sep)[0]
        edfs = [p for p in edfs if top in top_component(p)]

    current_data = files.allocate_data_array.allocate_data_array(20, 512)
    files.allocate_data_array.process_data_array(current_data)

    todo = []
    done_already = []
    for p in edfs:
        cascade = p[:-4] + ".imagecascade.pdf"
        if os.path.exists(cascade) and not redo:
            done_already.append(p)
        else:
            todo.append(p)

    if limit is not None:
        todo = todo[:limit]

    print(f"Folder: {folder}")
    print(f"EDFs (excluding clean/unclean): {len(edfs)}")
    print(f"Already have cascade PDF: {len(done_already)}")
    print(f"Order: {'name' if name_order else 'newest-first (mtime)'}"
          f"{'' if limit is None else f'  limit={limit}'}")
    print(f"To render this run: {len(todo)}")
    if list_only:
        for p in todo:
            ts = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(p)))
            print(f"  TODO [{ts}]:", os.path.relpath(p, folder))
        return

    print(f"Free space on output drive: {free_gb(folder):.1f} GB "
          f"(safety floor {MIN_FREE_GB:.0f} GB)")
    _run_todo(todo, os.path.join(folder, "_imagecascade_batch.log"), timeout)


def _run_todo(todo, log_path, timeout=PER_FILE_TIMEOUT):
    """Render each EDF in `todo`, logging results. Disk-guarded per file
    (space measured on each file's own drive). When `timeout` > 0 each file
    renders in an isolated subprocess with that wall-clock cap, so a hung file
    is killed and skipped instead of freezing the batch; 0 = in-process."""
    ok, fail = [], []
    for i, p in enumerate(todo, 1):
        name = os.path.basename(p)

        avail = free_gb(os.path.dirname(p) or "C:\\")
        if avail < MIN_FREE_GB:
            print(f"\nABORT: free space {avail:.1f} GB below floor "
                  f"{MIN_FREE_GB:.0f} GB. Stopping before {name}.", flush=True)
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(f"ABORT low disk\t{avail:.1f}GB free\tbefore {name}\n")
            break

        t0 = time.time()
        cap = f"  cap:{timeout}s" if timeout else ""
        print(f"\n[{i}/{len(todo)}] {name}  (free: {avail:.1f} GB){cap}",
              flush=True)
        try:
            if timeout:
                cascade, err = render_subprocess(p, timeout)
            else:
                cascade, err = run_one(p), None
            dt = time.time() - t0
            if err == "timeout":
                print(f"    TIMEOUT after {dt:.0f}s -- killed, skipping",
                      flush=True)
                fail.append((name, f"timeout>{timeout}s"))
                status = f"TIMEOUT\t{timeout}s\t{dt:.0f}s"
            elif os.path.exists(cascade):
                sz = os.path.getsize(cascade)
                print(f"    OK  {sz} bytes  {dt:.0f}s", flush=True)
                ok.append((name, sz, dt))
                status = f"OK\t{sz}\t{dt:.0f}s"
            else:
                print(f"    MISSING output  {dt:.0f}s", flush=True)
                fail.append((name, "missing output"))
                status = f"FAIL\tmissing output\t{dt:.0f}s"
        except Exception as e:
            dt = time.time() - t0
            print(f"    ERROR {e}  {dt:.0f}s", flush=True)
            traceback.print_exc()
            fail.append((name, str(e)))
            status = f"ERROR\t{e}\t{dt:.0f}s"
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}\t{status}\n")

    print(f"\n==== DONE ====  ok={len(ok)}  fail={len(fail)}")
    if fail:
        for name, why in fail:
            print("  FAIL:", name, "-", why)


if __name__ == "__main__":
    main()
