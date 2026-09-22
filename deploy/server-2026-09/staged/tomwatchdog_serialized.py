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

# Per-study wall-clock cap. A panel alone is well under a minute; a panel plus
# a 19-component cascade runs ~7-8 min. A study past this has hung (Tk or
# source-localization deadlock) and is killed so one bad file cannot stall the
# queue forever. Set to 0 to disable the cap.
PER_FILE_TIMEOUT = 1500   # seconds (25 min)

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
            proc = subprocess.Popen([sys.executable, "module7.py", path])
            try:
                proc.wait(timeout=PER_FILE_TIMEOUT or None)
            except subprocess.TimeoutExpired:
                print("  TIMED OUT after %ds, killing:" % PER_FILE_TIMEOUT, path)
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"])
                try:
                    proc.wait(timeout=30)
                except Exception:
                    pass
            print("  DONE in %ds  rc=%s  %s"
                  % (time.time() - started, proc.returncode, path))
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
