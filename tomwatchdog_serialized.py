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
# ALSO: the same upload can fire MORE THAN ONE creation event, and the original
# handler launched a process for each. Seen on the production console
# 2026-10-02: one .edf logged "on_created is called" twice and two module7
# processes wrote the same .icale.rep.pdf concurrently. See DEDUP_WINDOW below.
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
import re
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

# LOGGING: console AND file.
#
# Everything used to go to stdout only, so the record lived in the console
# scrollback and died with the window. That repeatedly cost us the one thing
# worth having after a failure -- the child process's traceback. Now every line
# from the watchdog and from each module7.py / run_cascade.py it spawns is
# timestamped and appended to logs\watchdog-YYYY-MM-DD.log, while still
# appearing live in the console.
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_log_fh = None
_log_lock = threading.Lock()

# The pipeline colours some of its own output (edftotextbynameplotproc highlights
# the STD RAW / STD RECON comparison). Those escapes are meaningful in a console
# and pure noise in a file, where they arrive as literal "ESC[93m" around every
# number. Strip them on the way to disk only, so the console keeps its colours.
_ANSI = re.compile("\x1b\\[[0-9;]*[A-Za-z]")


def _log_path():
    return os.path.join(LOG_DIR, "watchdog-%s.log" % time.strftime("%Y-%m-%d"))


def _emit(*parts, **kw):
    """Write one line to the console and to today's log file.

    Accepts several arguments like print() does: a worker thread must not be
    killable by a TypeError from its own logging call, which is exactly what
    happened when this took a single argument and a caller passed three.
    """
    stamp = kw.get("stamp", True)
    line = " ".join(str(p) for p in parts)
    global _log_fh
    text = ("%s  %s" % (time.strftime("%H:%M:%S"), line)) if stamp else line
    print(text)
    try:
        with _log_lock:
            want = _log_path()
            if _log_fh is None or getattr(_log_fh, "name", None) != want:
                if _log_fh is not None:
                    _log_fh.close()
                os.makedirs(LOG_DIR, exist_ok=True)
                _log_fh = open(want, "a", encoding="utf-8", errors="replace")
            _log_fh.write(_ANSI.sub("", text) + chr(10))
            _log_fh.flush()
    except Exception:
        pass          # a logging failure must never stop a study


# QUICKEDIT: selecting text in a Windows console window (conhost's QuickEdit
# mode) PAUSES every write to that console until the selection is cleared. Our
# print() then blocks, the relay thread stops draining the child's pipe, the
# pipe fills, and the child freezes mid-print at 0% CPU -- no error, no log
# line. Seen on the dev server 2026-10-02: a cascade sat dead for 10+ minutes
# because log text had been selected to copy; Esc released it. Turning QuickEdit
# off for this console makes a click or drag harmless. Copy log text from
# logs\watchdog-*.log instead (or re-enable it via the window's Properties).
def _disable_quickedit():
    if os.name != "nt":
        return "not Windows"
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-10)                 # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if not k32.GetConsoleMode(h, ctypes.byref(mode)):
            return "no console (input redirected?) - left as is"
        ENABLE_QUICK_EDIT_MODE = 0x0040
        ENABLE_EXTENDED_FLAGS = 0x0080            # required for the change to stick
        new = (mode.value | ENABLE_EXTENDED_FLAGS) & ~ENABLE_QUICK_EDIT_MODE
        if not k32.SetConsoleMode(h, new):
            return "SetConsoleMode failed - QuickEdit still ON"
        return "OFF (selecting text can no longer freeze the watchdog)"
    except Exception as e:
        return "could not change (%s)" % e


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

# DE-DUPLICATION: the filesystem fires more than one creation event per upload.
#
# Observed on the production console 2026-10-02: a single uploaded study logged
# "on_created is called" TWICE for the same .edf and the old watchdog launched
# two module7.py processes for it, which then wrote the same .icale.rep.pdf at
# the same time. (The second file of the same upload fired only once, so it is
# not every file -- a plain "ignore the second event" rule would be wrong.)
# Windows reports a create and then further change/create notifications while
# IIS is still writing, and watchdog surfaces them as separate events.
#
# Queueing twice was merely wasteful when the panel was the only pass. With
# cascades on it means a second ~80-minute render of a study already rendered,
# and two processes racing on one output file.
#
# A path is ignored if it was queued within DEDUP_WINDOW. The window must
# outlast the whole two-pass run, or a duplicate event arriving late (after the
# panel, while the cascade is going) would still queue -- hence it is derived
# from the cascade cap rather than being a small fixed number. A genuine
# re-upload of the same path after that is processed normally, which is what
# a practitioner replacing a bad recording expects.
DEDUP_WINDOW = max(CASCADE_TIMEOUT if CASCADE_PASS else 0, PANEL_TIMEOUT) + 600
_recent = {}
_recent_lock = threading.Lock()


def _claim(path):
    """True if this path is ours to process; False if it is a duplicate event."""
    key = os.path.normcase(os.path.abspath(path))
    now = time.time()
    with _recent_lock:
        for k, t in list(_recent.items()):
            if now - t > DEDUP_WINDOW:
                del _recent[k]
        prev = _recent.get(key)
        if prev is not None:
            return False
        _recent[key] = now
    return True

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
    _emit("  TIMEOUT waiting for upload to finish: " + str(path))
    return False


def _free_gb(path):
    try:
        return shutil.disk_usage(os.path.dirname(path)).free / (1024 ** 3)
    except OSError:
        return float("nan")


def _run(script, path, timeout, tag):
    """Run one pipeline pass, killing the whole tree if it overruns.

    The child's stdout and stderr are relayed line by line so its output --
    above all, its traceback -- reaches the log file instead of only the
    console. A reader thread does the pumping so the wait() timeout still
    applies; iterating the pipe on this thread would block past the cap.

    Each relayed line carries the worker's tag ("P" panel, "C" cascade). The
    two workers run concurrently, so without it their output interleaves
    line by line and a multi-line numpy print from one is split by the other.
    """
    proc = subprocess.Popen([sys.executable, script, path],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            bufsize=1, universal_newlines=True, errors="replace")

    def _pump():
        try:
            for line in proc.stdout:
                _emit("    %s| %s" % (tag, line.rstrip(chr(10))), stamp=False)
        except Exception:
            pass

    t = threading.Thread(target=_pump, daemon=True)
    t.start()
    try:
        proc.wait(timeout=timeout or None)
        t.join(timeout=10)
    except subprocess.TimeoutExpired:
        _emit("  TIMED OUT after %ds, killing %s for: %s" % (timeout, script, path))
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
                _emit("  *** LOW DISK SPACE: %.1f GB free on the upload drive ***" % free)
            _emit("PANEL START: %s  (panels waiting %d, cascades waiting %d, %.1f GB free)"
                  % (path, panel_q.qsize(), cascade_q.qsize(), free))
            t0 = time.time()
            rc = _run("module7.py", path, PANEL_TIMEOUT, "P")
            _emit("  PANEL in %ds  rc=%s  %s" % (time.time() - t0, rc, path))
            if CASCADE_PASS:
                cascade_q.put(path)
        except Exception as exc:
            _emit("  ERROR in panel pass for %s -> %r" % (path, exc))
        finally:
            panel_q.task_done()


def cascade_worker():
    """Add the image cascade, one study at a time, never blocking a panel."""
    while True:
        path = cascade_q.get()
        try:
            _emit("CASCADE START: %s  (cascades waiting %d)" % (path, cascade_q.qsize()))
            t0 = time.time()
            rc = _run("run_cascade.py", path, CASCADE_TIMEOUT, "C")
            _emit("  CASCADE in %ds  rc=%s  %s" % (time.time() - t0, rc, path))
        except Exception as exc:
            _emit("  ERROR in cascade pass for %s -> %r" % (path, exc))
        finally:
            cascade_q.task_done()


class NewFileHandler(FileSystemEventHandler):
    def _offer(self, event, how):
        if event.is_directory:
            return
        path = getattr(event, "dest_path", None) or event.src_path
        if not path.lower().endswith(".edf"):
            return
        # watchdog marks the events it invents itself. On Windows a new
        # directory makes the emitter os.walk() it and emit a SYNTHETIC create
        # for every file already inside (read_directory_changes.py ~90), and the
        # real notification for that same file arrives as well -- which is the
        # whole source of the doubling. Logging which kind arrived turns a
        # confusing repeat into a one-line explanation.
        if getattr(event, "is_synthetic", False):
            how += "/synthetic"
        if not _claim(path):
            _emit("DUPLICATE %s event ignored: %s" % (how, path))
            return
        _emit("QUEUED (%s): %s" % (how, path))
        panel_q.put(path)

    def on_created(self, event):
        self._offer(event, "created")

    def on_moved(self, event):
        # Some uploaders write to a temp name and rename into place, in which
        # case the .edf never gets a creation event at all. Harmless to watch
        # both now that duplicates are filtered.
        self._offer(event, "moved")


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
    print("console QuickEdit:", _disable_quickedit())

    threading.Thread(target=panel_worker, daemon=True).start()
    threading.Thread(target=cascade_worker, daemon=True).start()
    print("panel worker started (panels run ahead of cascades)")
    print("cascade worker started (one cascade at a time)")

    observer = Observer()
    observer.schedule(NewFileHandler(), MONITOR_DIR, recursive=True)
    observer.start()
    _emit("logging to " + _log_path())
    _emit("observer created and started")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
