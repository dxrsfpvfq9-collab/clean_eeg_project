# tomwatchdog_serialized.py
# Drop-in replacement for tomwatchdog.py, required once image cascades are on.
#
# WHY: the original handler calls subprocess.Popen per created .edf with no
# limit, so N simultaneous uploads means N concurrent module7 processes. With
# panel-only processing that just competes for CPU. With selstring[12]=1 each
# process opens a FULLSCREEN Tk component window and screenshots it with
# ImageGrab, which copies raw screen pixels -- two at once and both cascades
# capture whichever window happens to be on top. Output is silently wrong, not
# an error. This version feeds one worker thread from a queue so exactly one
# study renders at a time.
#
# ALSO: on_created fires when the file APPEARS, which for a 6-8 MB EDF arriving
# over HTTP is well before the last byte lands. Panel-only that usually
# survived because processing started slowly; it is a real risk either way, and
# an 8-minute cascade on a truncated file is 8 minutes wasted. _wait_until_settled
# holds each path until its size stops changing before queueing it.
#
# USAGE:
#   py tomwatchdog_serialized.py                      # watches the production path
#   py tomwatchdog_serialized.py "<monitor dir>"      # e.g. the dev server's c:/app/... path
#
# The two servers differ: production watches c:/inetpub/wwwroot/EEGScreening/...
# and the development server watches c:/app/STSEEGScreening/... . Pass the dir
# on the command line rather than editing this file per server. module7 is
# launched with the SAME interpreter running this script (sys.executable), which
# also removes the "py" vs "python" difference between the two boxes.

import os
import queue
import shutil
import subprocess
import sys
import threading
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

DEFAULT_MONITOR_DIR = "c:/inetpub/wwwroot/EEGScreening/Source/Practitioners"

# Log a loud warning before each study when free space on the monitored drive
# is below this. A panel + cascade adds ~15 MB per study; 10 GB is ~650 more
# studies of headroom, which is plenty of notice to clear space. Processing is
# NOT stopped -- the panel is the essential output and must keep flowing.
LOW_SPACE_GB = 10.0

# Size must hold steady this many consecutive polls before the file is
# considered fully written.
SETTLE_POLLS = 3
SETTLE_INTERVAL = 2.0     # seconds between size checks
SETTLE_TIMEOUT = 300.0    # give up waiting after this long

# Two-pass processing. module7.py writes the brain panel (fast, seconds), then
# run_cascade.py adds the image cascade (~8 min). Splitting them means the panel
# reaches the practitioner without waiting on the cascade, and a cascade that
# dies -- including a native VTK/OpenGL abort that Python cannot trap -- can no
# longer take the panel with it, because the panel is already on disk.
# Set to False for panel-only processing.
CASCADE_PASS = True

# Wall-clock caps, PER PASS. A study past its cap has hung (Tk deadlock, a
# wedged render) and is killed so one bad file cannot stall the queue forever.
# Set either to 0 to disable that cap.
#
# The panel is seconds of work, so a low cap here catches a genuine hang fast.
#
# The cascade is a different animal: it renders and screen-captures one page per
# ICA component, and that is far slower on a small cloud VM over RDP than on a
# workstation -- the dev server blew through 25 minutes on 2026-09-24 and was
# killed mid-render. Because the panel is now written by a SEPARATE earlier
# pass, a long cascade cap costs nothing: the clinical output is already on
# disk, and the only thing at risk is the cascade itself. Raise this rather than
# lose cascades, and watch the "CASCADE in Ns" line to learn the real number for
# your hardware.
PANEL_TIMEOUT = 600      # seconds (10 min)
CASCADE_TIMEOUT = 5400   # seconds (90 min)

work_q = queue.Queue()


def _wait_until_settled(path):
    """Block until path's size stops changing. False if it never settles."""
    stable = 0
    last = -1
    deadline = time.time() + SETTLE_TIMEOUT
    while time.time() < deadline:
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size == last and size > 0:
            stable += 1
            if stable >= SETTLE_POLLS:
                return True
        else:
            stable = 0
            last = size
        time.sleep(SETTLE_INTERVAL)
    print("  TIMEOUT waiting for upload to finish:", path)
    return False


def _free_gb(path):
    try:
        return shutil.disk_usage(os.path.dirname(path)).free / (1024 ** 3)
    except OSError:
        return float("nan")


def _run(script, path, timeout):
    """Run one pipeline pass, killing the whole tree if it overruns."""
    proc = subprocess.Popen([sys.executable, script, path])
    try:
        proc.wait(timeout=timeout or None)
    except subprocess.TimeoutExpired:
        print("  TIMED OUT after %ds, killing %s for:" % (timeout, script), path)
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=30)
        except Exception:
            pass
        return "timeout"
    return proc.returncode


def worker():
    """Process one study at a time, forever."""
    while True:
        path = work_q.get()
        try:
            if not _wait_until_settled(path):
                continue
            free = _free_gb(path)
            if free < LOW_SPACE_GB:
                print("  *** LOW DISK SPACE: %.1f GB free on the upload drive ***" % free)
            print("PROCESSING:", path, " (queue depth %d, %.1f GB free)"
                  % (work_q.qsize(), free))
            started = time.time()

            rc = _run("module7.py", path, PANEL_TIMEOUT)
            print("  PANEL in %ds  rc=%s" % (time.time() - started, rc))

            if CASCADE_PASS:
                casc_started = time.time()
                rc_c = _run("run_cascade.py", path, CASCADE_TIMEOUT)
                print("  CASCADE in %ds  rc=%s" % (time.time() - casc_started, rc_c))

            print("  DONE in %ds  %s" % (time.time() - started, path))
        except Exception as exc:            # never let one study kill the worker
            print("  ERROR on", path, "->", repr(exc))
        finally:
            work_q.task_done()


class NewFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if not path.lower().endswith(".edf"):
            return
        print("QUEUED:", path)
        work_q.put(path)


if __name__ == "__main__":
    # Line-buffer stdout so QUEUED/PROCESSING/DONE lines reach a redirected log
    # file as they happen, not only when the buffer fills or the process exits.
    # Without this, `py tomwatchdog_serialized.py > watchdog.log` shows nothing
    # for hours and loses everything if the process is killed.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    MONITOR_DIR = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MONITOR_DIR
    if not os.path.isdir(MONITOR_DIR):
        sys.exit("monitor dir does not exist: %s" % MONITOR_DIR)
    print("entering main")
    print("monitor dir:", MONITOR_DIR)
    print("interpreter:", sys.executable)

    threading.Thread(target=worker, daemon=True).start()
    print("worker thread started (one study at a time)")

    observer = Observer()
    observer.schedule(NewFileHandler(), MONITOR_DIR, recursive=True)
    observer.start()
    print("observer created and started")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
