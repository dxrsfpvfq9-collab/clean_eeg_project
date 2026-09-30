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
# is below this. A panel + cascade adds ~21 MB per study; 10 GB is ~450 more
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
#
# Site note: this server receives well under one study per day, so nothing ever
# queues behind a slow cascade. The cascade cap is therefore set well above the
# observed runtime (~80 min for 19 components on the dev VM) -- it is there to
# catch a genuine hang, not to ration throughput, and losing 80 minutes of
# finished work to a cap that was merely tight would be the worse failure.
PANEL_TIMEOUT = 600       # seconds (10 min)
CASCADE_TIMEOUT = 14400   # seconds (4 h)

# SPLIT QUEUES: panels overtake cascades.
#
# One queue per PASS, not one per study. A study is queued for its panel, and
# only joins the cascade queue once its panel exists. The two run on separate
# threads, so a panel starts within seconds of an upload even while a cascade
# from an earlier study is still going -- which matters when two practitioners
# upload minutes apart and the second would otherwise wait out the first study's
# whole cascade for a report that takes seconds to compute.
#
# Cascades stay strictly one at a time. That used to be a correctness
# requirement: two of them would each capture the other's fullscreen Tk window.
# With CLEANEEG_OFFSCREEN=1 nothing touches the screen and that cannot happen,
# but one at a time is still the right call on a 2-vCPU box.
#
# A panel running alongside a cascade is safe in BOTH modes: the panel pass
# never enters the cascade block, so it never captures anything.
panel_q = queue.Queue()
cascade_q = queue.Queue()

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


def panel_worker():
    """Write the brain panel, then hand the study to the cascade queue."""
    while True:
        path = panel_q.get()
        try:
            if not _wait_until_settled(path):
                continue
            free = _free_gb(path)
            if free < LOW_SPACE_GB:
                print("  *** LOW DISK SPACE: %.1f GB free on the upload drive ***" % free)
            print("PANEL START:", path,
                  " (panels waiting %d, cascades waiting %d, %.1f GB free)"
                  % (panel_q.qsize(), cascade_q.qsize(), free))
            t0 = time.time()
            rc = _run("module7.py", path, PANEL_TIMEOUT)
            print("  PANEL in %ds  rc=%s  %s" % (time.time() - t0, rc, path))
            if CASCADE_PASS:
                cascade_q.put(path)
        except Exception as exc:
            print("  ERROR in panel pass for", path, "->", repr(exc))
        finally:
            panel_q.task_done()


def cascade_worker():
    """Add the image cascade, one study at a time, never blocking a panel."""
    while True:
        path = cascade_q.get()
        try:
            print("CASCADE START:", path,
                  " (cascades waiting %d)" % cascade_q.qsize())
            t0 = time.time()
            rc = _run("run_cascade.py", path, CASCADE_TIMEOUT)
            print("  CASCADE in %ds  rc=%s  %s" % (time.time() - t0, rc, path))
        except Exception as exc:
            print("  ERROR in cascade pass for", path, "->", repr(exc))
        finally:
            cascade_q.task_done()


class NewFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if not path.lower().endswith(".edf"):
            return
        print("QUEUED:", path)
        panel_q.put(path)


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

    threading.Thread(target=panel_worker, daemon=True).start()
    threading.Thread(target=cascade_worker, daemon=True).start()
    print("panel worker started (panels run ahead of cascades)")
    print("cascade worker started (one cascade at a time)")

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
