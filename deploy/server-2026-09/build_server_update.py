"""Build the server update file set for the 2026-09 deployment.

Generates, into ./staged/, the exact files to copy onto the development
server and then production. Every file is derived from the CURRENT
PRODUCTION SOURCE (byte-identical to git baseline d4f522c apart from CRLF
line endings), so the staged tree carries the two requested changes and
nothing else.

  1. Global STD fix          -> files/edftotextbynameplotproc.py
  2. Image cascades enabled  -> files/edftotextbycommandplotproc.py
                                files/Montage_6.py
                                files/dummy_gui.py
                                files/create_report_pdf.py
                                tomwatchdog_serialized.py
  3. Cascade display work    -> files/Montage_6.py
     (Periodicity panel,        files/dummy_gui.py
      component renumbering)    files/Component_selector.py

Run:  py deploy/server-2026-09/build_server_update.py
"""
import os
import sys

PROD = r"C:\BrainPanel\CleanEEGProject - production"
HERE = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.dirname(os.path.dirname(HERE))
STAGED = os.path.join(HERE, "staged")


def read(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8", errors="surrogateescape")
    return text.replace("\r\n", "\n"), (b"\r\n" in raw)


def write(relpath, text, crlf):
    out = os.path.join(STAGED, relpath.replace("/", os.sep))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    data = text.replace("\n", "\r\n") if crlf else text
    with open(out, "wb") as fh:
        fh.write(data.encode("utf-8", errors="surrogateescape"))
    print("  staged  " + relpath)


def patch(relpath, old, new):
    """Apply one exact-text replacement to the production copy of relpath."""
    text, crlf = read(os.path.join(PROD, relpath.replace("/", os.sep)))
    if text.count(old) != 1:
        sys.exit("ANCHOR not found exactly once in %s (%d matches)"
                 % (relpath, text.count(old)))
    write(relpath, text.replace(old, new, 1), crlf)


def copy_dev(relpath, dev_relpath=None):
    """Ship the dev version whole (verified: no new imports, cascade-only)."""
    text, _ = read(os.path.join(DEV, (dev_relpath or relpath).replace("/", os.sep)))
    prod_path = os.path.join(PROD, relpath.replace("/", os.sep))
    crlf = read(prod_path)[1] if os.path.exists(prod_path) else True
    write(relpath, text, crlf)


# ---------------------------------------------------------------------------
# CHANGE 1 -- Global STD fix
# ---------------------------------------------------------------------------
# Production reports print "Global STD 1000.00 / z 2642.71" on every study.
# Cause: sklearn >= 1.3 changed FastICA's default whitening to 'unit-variance',
# which forces every ICA source to std 1. global_stdmeas is the std of those
# sources after the x1000 reconstruction scaling, so it collapses to a constant
# 1000 and its z-score is meaningless. The EC_191 reference database was built
# under the pre-1.3 default (arbitrary, data-dependent source variance), where
# the metric lands at ~2.5.
#
# Verified on 1412 Grace SL EC: 47 of 48 metrics reproduce the production
# report to printed precision; Global STD alone changes,
# 1000.00 (z 2642.71) -> 2.54 (z -0.53), inside the 1.91-3.42 normal range.
GSTD_OLD = "       ica = FastICA(n_components=n, max_iter = 1000, random_state=0)"
GSTD_NEW = '''\
#  WHITENING MODE FIX (Global STD): the reference database EC_191 was built with
#  the pre-sklearn-1.3 default whitening, which yields ICA sources of arbitrary
#  (data-dependent) variance.  sklearn >= 1.3 changed the default to
#  'unit-variance' (sources forced to std 1), which made global_stdmeas
#  (= std of the x1000 sources) collapse to a constant ~1000 and its z-score
#  meaningless (~2642).  Pinning arbitrary-variance restores Global STD to the
#  ~2.5 scale the database expects.  Only Global STD is affected; every other
#  metric uses the post-normalization signals and is unchanged (verified 47/48
#  bit-reproduce the production report).
#  Version-robust: sklearn < 1.3 spells this behavior whiten=True.
       import sklearn as _sk
       _whiten_mode = "arbitrary-variance" if tuple(
           int(x) for x in _sk.__version__.split(".")[:2]) >= (1, 3) else True
       ica = FastICA(n_components=n, max_iter = 1000, random_state=0, whiten=_whiten_mode)'''

patch("files/edftotextbynameplotproc.py", GSTD_OLD, GSTD_NEW)


# ---------------------------------------------------------------------------
# CHANGE 2 -- image cascades alongside every brain panel
# ---------------------------------------------------------------------------
# 2a. Turn the cascade on in the unattended (watchdog) entry path.
#
# NOTE ON THE PRE-ICA LINE FILTER: the dev tree applies lp50+notch60 before ICA
# whenever selstring[12]==1. That filter is deliberately NOT ported. It changes
# the ICA decomposition, and montage 6 rebuilds the report signals FROM that
# decomposition, so it moves the panel: measured on 1412 Grace SL EC, 39 of 48
# z-scores shifted, several past 2 sigma (Beta Max Front +3.21, PDR Max Post.
# +2.58, Front Alpha Asym -2.00). That would silently invalidate every
# comparison against EC_191. Leaving it out keeps the panel numerically
# identical to today's production AND makes the cascade show the same
# decomposition the panel was computed from.
CASC_OLD = """    selstring[6] = 1
    selstring[8] = 1
"""
CASC_NEW = """    selstring[6] = 1
    selstring[8] = 1
#  IMAGE CASCADE: produce <edfname>.imagecascade.pdf alongside the brain panel.
#  Adds ~7-8 min per study (one screen-captured page per ICA component) and
#  REQUIRES an interactive desktop session -- see the deploy README section
#  "Screen capture". Set this to 0 to return to panel-only processing.
    selstring[12] = 1
"""
patch("files/edftotextbycommandplotproc.py", CASC_OLD, CASC_NEW)

# 2b. Re-enable the overview savefig commented out during the Dec-2024 server
#     edits. Without it the cascade dies with FileNotFoundError on
#     <edfname>.ica.png. Also carries the descending-% page ordering. Every
#     change in this file is cascade display; the selstring[9] rhythm path
#     still receives unsorted arrays.
copy_dev("files/Montage_6.py")

# 2c. Head-map contour fixes for the per-component cascade pages (un-scale the
#     x1000 mixing, clamp cubic-interpolation overshoot, one symmetric
#     normalization so sign matches the bar graph). Cascade pages only.
copy_dev("files/dummy_gui.py")

# 2c-bis. Component_selector.py -- the INTERACTIVE component review (module61
#     GUI path). It ships for consistency, not because the cascade needs it:
#     Montage_6/dummy_gui carry the Periodicity panel and the magnitude
#     renumbering, and without this file the same machine would show the old
#     Cepstrum panel and FastICA numbering in the GUI while its own cascade
#     PDFs show the new ones -- including a button grid that disagrees with the
#     PDFs it just produced. Verified to import nothing production lacks.
copy_dev("files/Component_selector.py")

# 2d. save_gui_screenshot(): ImageGrab copies raw SCREEN pixels, so anything
#     covering the component window lands in the PDF instead. Force the window
#     topmost/raised/focused and let the compositor settle before grabbing.
#     ONLY the screenshot helper is taken from dev -- the page-3 legend rework
#     in the dev copy of this file is NOT ported, so the panel PDF keeps its
#     current production appearance.
SHOT_OLD = """def save_gui_screenshot(window):
    window.update_idletasks()
"""
SHOT_NEW = """def save_gui_screenshot(window):
    # ImageGrab captures raw SCREEN pixels for the window's region, so whatever
    # is visually on top of that region is what gets saved. Force THIS window to
    # the very top (topmost + raised + focused) and let the window manager
    # composite the raise before grabbing. Display-only; affects no metric.
    import time
    try:
        window.attributes('-topmost', True)
    except Exception:
        pass
    try:
        window.deiconify()
        window.lift()
        window.focus_force()
    except Exception:
        pass
    window.update_idletasks()
    window.update()
    time.sleep(0.25)   # let the compositor bring the window forward
    window.update()
"""
patch("files/create_report_pdf.py", SHOT_OLD, SHOT_NEW)

# 2e. Serialize the watchdog. Today it fires subprocess.Popen per upload with
#     no limit. Panel-only, concurrent studies merely compete for CPU; with
#     cascades on, two at once means two fullscreen Tk windows fighting over
#     one screen and BOTH cascades capture the wrong window. The replacement
#     runs a single worker thread over a queue: one study renders at a time.
copy_dev("tomwatchdog_serialized.py")


# ---------------------------------------------------------------------------
# OPTIONAL -- numpy version insurance (staged separately, deploy only if needed)
# ---------------------------------------------------------------------------
# process/detect_artifact.py pins dtype=np.int32 in detect_drowsiness and
# detect_moments. On numpy < 2.0 this is a NO-OP: np.arange already returned
# int32 on Windows, which is what EC_191 was built from. On numpy >= 2.0 arange
# defaults to int64, x_values**2 stops overflowing at i>=46341, and the Moment 3
# rows silently blow up.
#
# This is not theoretical -- it is what the first end-to-end test of this
# deployment produced when the production tree ran under numpy 2.1.3:
#     PDR Moment 3      477.45 ->  32356.28   (z  -0.71 -> +97.75)
#     Beta Moment 3    1503.10 ->  61175.22   (z  +0.20 -> +96.01)
#     Theta Moment 3    900.35 ->  65167.49   (z  -0.81 -> +107.46)
#     Delta Moment 3   1450.42 ->  61198.70   (z  +0.10 -> +108.21)
# No error, no warning -- just four meaningless rows on every panel.
#
# Check the server first:  py -c "import numpy; print(numpy.__version__)"
#   numpy < 2.0  -> not needed now; deploying it changes nothing and protects
#                   you from a future upgrade.
#   numpy >= 2.0 -> REQUIRED, and the server's existing panels already have
#                   corrupt Moment 3 rows.
_opt = STAGED
STAGED = os.path.join(HERE, "staged-optional")
copy_dev("process/detect_artifact.py")
STAGED = _opt

print("\nStaged tree:          " + STAGED)
print("Optional (numpy>=2):  " + os.path.join(HERE, "staged-optional"))
