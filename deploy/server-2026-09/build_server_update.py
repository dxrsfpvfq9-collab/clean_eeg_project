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
                                files/color_strip.py (new; strip speed-up)
  4. OpenGL-free brain pages -> process/brain_render.py
                                mne_data/.../fsaverage/surf/{lh,rh}.{pial,white,sulc}

Also rewrites SHA256SUMS.txt from what it staged.

Run:  py deploy/server-2026-09/build_server_update.py
"""
import hashlib
import os
import shutil
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


def patch(relpath, old, new, base="prod"):
    """Apply one exact-text replacement to relpath.

    base="prod" (default) patches the production source -- use it for the FIRST
    hunk in a file. base="staged" patches what is already staged, so several
    hunks can accumulate in one file; patching from prod each time would discard
    the previous hunk.
    """
    root = PROD if base == "prod" else STAGED
    text, crlf = read(os.path.join(root, relpath.replace("/", os.sep)))
    if base == "staged":
        # The staged copy already carries production's line endings.
        crlf = read(os.path.join(PROD, relpath.replace("/", os.sep)))[1]
    if text.count(old) != 1:
        sys.exit("ANCHOR not found exactly once in %s [%s] (%d matches)"
                 % (relpath, base, text.count(old)))
    write(relpath, text.replace(old, new, 1), crlf)


def copy_dev(relpath, dev_relpath=None):
    """Ship the dev version whole (verified: no new imports, cascade-only)."""
    text, _ = read(os.path.join(DEV, (dev_relpath or relpath).replace("/", os.sep)))
    prod_path = os.path.join(PROD, relpath.replace("/", os.sep))
    crlf = read(prod_path)[1] if os.path.exists(prod_path) else True
    write(relpath, text, crlf)


def copy_bin(relpath):
    """Byte-for-byte copy from dev (binary data: no line-ending handling)."""
    out = os.path.join(STAGED, relpath.replace("/", os.sep))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shutil.copyfile(os.path.join(DEV, relpath.replace("/", os.sep)), out)
    print("  staged  " + relpath)


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
# Verified on QA study A (EC): 47 of 48 metrics reproduce the production
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
# decomposition, so it moves the panel: measured on QA study A (EC), 39 of 48
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
#  IMAGE CASCADE: deliberately OFF here. module7.py is now the PANEL pass only,
#  so the report reaches the practitioner in seconds instead of after the ~8 min
#  cascade render. The watchdog runs run_cascade.py as a second pass to add
#  <edfname>.imagecascade.pdf. Keeping them in separate processes also means a
#  cascade failure -- including a native VTK/OpenGL abort, which Python cannot
#  trap -- can no longer destroy the panel, because the panel is already written.
#  Set to 1 only if you deliberately want both in one pass.
    selstring[12] = 0
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

# 2c-ter. color_strip.py -- NEW file, imported by BOTH dummy_gui.py and
#     Component_selector.py above. Draws each colour strip (waveform bar, Bath
#     Water Graph, Log FFT Waterfall) as one LineCollection instead of ~50,000
#     single-segment plot() calls per component page: page 15.6 s -> 1.9 s and
#     capture 3.2 s -> 0.3 s in a local profile, pixel-identical output. Must
#     ship with them or both fail to import.
copy_dev("files/color_strip.py")

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
    # OFFSCREEN PAGES: process/offscreen_tk.py composites the page itself, so
    # there is nothing on screen to grab -- and nothing that can be covered,
    # blanked by a lock screen, or lost when an RDP client disconnects. Without
    # this branch the offscreen flag has no effect HERE and every component page
    # is a photograph of the desktop, which is what the dev server produced on
    # 2026-09-29 while its brain pages (which never call this) were perfect.
    render = getattr(window, "render_offscreen", None)
    if render is not None:
        return render()

    print("[offscreen] OFF - grabbing the desktop for this component page")

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

# 2g. Restore the COLOUR CODING on the page-3 FFT peak-frequency labels. Each
#     channel's spectrum is drawn in the next colour of the cycle, and the
#     Alpha1 / Alpha / Alpha2 numbers printed for that channel are meant to
#     carry the same colour, so a reader can tie a number to its trace. The
#     production baseline passes no `color=`, so every number renders black and
#     the association is lost.
#
#     Two hunks. First capture the Line2D returned by ax.plot and read its
#     colour. Then replace the whole legend block with the dev version, which
#     also moves the labels and the three alpha-peak rails into AXES-RELATIVE
#     coordinates (0..1). In the production code their y positions are data
#     coordinates (y_min + 900 + 30*j), so on a loud spectrum the block drifts
#     up out of the panel and on a quiet one it collides with the traces. In
#     axes coordinates they sit in the same visual place whatever the
#     amplitude. The peak tick marks use a blended transform -- data x, so a
#     tick still lines up with its frequency, axes y, so it stays at a fixed
#     height. Font drops 17 -> 14 to match the dev layout the block was tuned
#     for.
#
#     The block is extracted verbatim from both trees rather than retyped, so
#     it cannot drift from what dev actually renders.
COLOR_OLD = """        ax.plot(start+40*freq_s[:len(freq_s)//4], y_min+100+avg_amp_sc[:len(avg_amp_sc)//4]/5, linewidth=0.5)"""
COLOR_NEW = """        # Keep the Line2D so the peak-frequency numbers below can be printed in
        # the same colour as this channel's spectrum -- that colour is the only
        # thing tying a number to its trace.
        line, = ax.plot(start+40*freq_s[:len(freq_s)//4], y_min+100+avg_amp_sc[:len(avg_amp_sc)//4]/5, linewidth=0.5)
        line_color = line.get_color()"""
patch("files/create_report_pdf.py", COLOR_OLD, COLOR_NEW, base="staged")

LEGEND_OLD = """        
        ax.text(start+1750, y_min + 900 - 30 * j, tstring1, fontsize=17)   #-1000, + 500

        tstring = "Alpha1:"
        ax.text(start-10, y_min + 930, tstring)  
        tstring = "Alpha:"
        ax.text(start-10, y_min + 950, tstring)
        tstring = "Alpha2:"
        ax.text(start-10, y_min + 970, tstring)

        if peak_index != 0:
            value=(7*10+peak_index)/10
            tstringv = f"{value:.1f}"
            ax.text(start+2150, y_min + 900 - 30 * j, tstringv, fontsize=17)
            ax.plot([start+7*40+4*peak_index, start+7*40+4*peak_index], [y_min+950, y_min+965], color = "Black", linewidth=1.0)
        else:
            value = 0
        #print('Val: ', value)
        if peak_indexl != 0:
            valuel=(7*10+peak_indexl)/10
            tstringl = f"{valuel:.1f}"
            ax.text(start+1950, y_min + 900 - 30 * j, tstringl, fontsize=17)
            ax.plot([start+7*40+4*peak_indexl, start+7*40+4*peak_indexl], [y_min+930, y_min+945], color = "Black", linewidth=1.0)
        else:
            valuel = 0
        #print('low Peak: ', valuel)
        if peak_indexh != 0:
            valueh=(10*10+peak_indexh)/10
            tstringh = f"{valueh:.1f}"
            ax.text(start+2350, y_min + 900 - 30 * j, tstringh, fontsize=17)
            ax.plot([start+10*40+4*peak_indexh, start+10*40+4*peak_indexh], [y_min+970, y_min+985], color = "Black", linewidth=1.0)
        else:
            valueh = 0
"""
LEGEND_NEW = """
        # Position the per-channel peak-frequency legend in AXES-relative
        # coordinates (0..1) so the layout is independent of the FFT
        # amplitude — labels always render at the same visual location
        # regardless of how loud the spectrum is. The numbers below were
        # chosen to reproduce the production reference layout (compact
        # upper-right block, ~14pt-equivalent text).
        label_top = 0.94
        label_bottom = 0.55
        label_spacing = (label_top - label_bottom) / max(n - 1, 1)
        label_y = label_top - label_spacing * j
        label_fontsize = 14

        ax.text(0.60, label_y, tstring1, fontsize=label_fontsize, color=line_color, transform=ax.transAxes)

        # "Alpha1:/Alpha:/Alpha2:" column labels for the three peak-marker
        # rails. Use axes-relative coords so they sit at a fixed visible
        # position regardless of FFT amplitude. Drawn inside the j-loop
        # (redundantly), each iteration overlays the same text at the same
        # spot — wasteful but harmless.
        marker_y_low  = 0.85   # Alpha1 (low-alpha peak) rail center
        marker_y_mid  = 0.90   # Alpha   (mid-alpha peak) rail center
        marker_y_high = 0.95   # Alpha2  (high-alpha peak) rail center
        marker_half_h = 0.018  # half-height of each tick mark in axes-y
        marker_label_fontsize = 12
        # blended transform: data-X (so ticks line up with spectrum freq),
        # axes-Y (so they stay at a fixed visible height).
        marker_trans = ax.get_xaxis_transform()

        ax.text(0.01, marker_y_low,  "Alpha1:", fontsize=marker_label_fontsize, transform=ax.transAxes)
        ax.text(0.01, marker_y_mid,  "Alpha:",  fontsize=marker_label_fontsize, transform=ax.transAxes)
        ax.text(0.01, marker_y_high, "Alpha2:", fontsize=marker_label_fontsize, transform=ax.transAxes)

        if peak_index != 0:
            value=(7*10+peak_index)/10
            tstringv = f"{value:.1f}"
            ax.text(0.80, label_y, tstringv, fontsize=label_fontsize, color=line_color, transform=ax.transAxes)
            x_peak = start+7*40+4*peak_index
            ax.plot([x_peak, x_peak], [marker_y_mid - marker_half_h, marker_y_mid + marker_half_h], color="Black", linewidth=1.5, transform=marker_trans)
        else:
            value = 0
        #print('Val: ', value)
        if peak_indexl != 0:
            valuel=(7*10+peak_indexl)/10
            tstringl = f"{valuel:.1f}"
            ax.text(0.72, label_y, tstringl, fontsize=label_fontsize, color=line_color, transform=ax.transAxes)
            x_peakl = start+7*40+4*peak_indexl
            ax.plot([x_peakl, x_peakl], [marker_y_low - marker_half_h, marker_y_low + marker_half_h], color="Black", linewidth=1.5, transform=marker_trans)
        else:
            valuel = 0
        #print('low Peak: ', valuel)
        if peak_indexh != 0:
            valueh=(10*10+peak_indexh)/10
            tstringh = f"{valueh:.1f}"
            ax.text(0.88, label_y, tstringh, fontsize=label_fontsize, color=line_color, transform=ax.transAxes)
            x_peakh = start+10*40+4*peak_indexh
            ax.plot([x_peakh, x_peakh], [marker_y_high - marker_half_h, marker_y_high + marker_half_h], color="Black", linewidth=1.5, transform=marker_trans)
        else:
            valueh = 0
"""
patch("files/create_report_pdf.py", LEGEND_OLD, LEGEND_NEW, base="staged")

# 2e. Serialize the watchdog. Today it fires subprocess.Popen per upload with
#     no limit. Panel-only, concurrent studies merely compete for CPU; with
#     cascades on, two at once means two fullscreen Tk windows fighting over
#     one screen and BOTH cascades capture the wrong window. The replacement
#     runs a single worker thread over a queue: one study renders at a time.
copy_dev("tomwatchdog_serialized.py")

# 2f. The cascade pass itself, invoked by the watchdog after the panel.
copy_dev("run_cascade.py")


# 2g. Brain pages WITHOUT OpenGL. dummy_brain (in the dummy_gui.py staged
#     above) now draws the source-localization page through
#     process/brain_render.py -- numpy + matplotlib Agg -- instead of
#     PyVista/VTK, which aborts the process on the GPU-less AWS servers. That is
#     what CLEANEEG_NO_BRAIN=1 existed to avoid; with this shipped it should be
#     UNSET (or 0) on the servers so the brain pages come back.
#     Imports only numpy/scipy/matplotlib, which the pipeline already needs.
copy_dev("process/brain_render.py")

# 2h. Offscreen page compositor. Ships INERT: nothing uses it unless
#     CLEANEEG_OFFSCREEN=1 is set, in which case dummy_gui binds its widget
#     names to it and the component page is composited with Agg + PIL instead
#     of being built as a Tk window and photographed off the desktop. That is
#     what lets a cascade survive a sleeping workstation, a dropped RDP client
#     or a locked screen -- none of which the screen-grab path tolerates.
copy_dev("process/offscreen_tk.py")

# 2h. Cascade labels are de-identified: Montage_6.py (staged above) masks likely
#     names in the study file name with '#' before printing it on the overview
#     and component pages. Pure-stdlib helper; display only.
copy_dev("files/deidentify.py")

#     The renderer draws the fsaverage cortex from these six FreeSurfer surfaces
#     (~25 MB), read relative to the project root. The workstation mirrors of
#     both servers already carry them, byte-identical to dev -- the old
#     interactive viewer reads lh/rh.white -- but they are shipped anyway so the
#     brain pages do not depend on that. A missing surface fails the cascade
#     (a Python exception, caught) and never the panel.
SURF = "mne_data/MNE-fsaverage-data/fsaverage/surf/"
for _h in ("lh", "rh"):
    for _kind in ("pial", "white", "sulc"):
        copy_bin(SURF + _h + "." + _kind)


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


# ---------------------------------------------------------------------------
# SHA256SUMS.txt -- what verify_copy.ps1 (and apply_local.ps1) check against
# ---------------------------------------------------------------------------
rows = []
for tree in ("staged", "staged-optional"):
    base = os.path.join(HERE, tree)
    for dirpath, _dirs, files in os.walk(base):
        if "__pycache__" in dirpath:
            continue
        for name in files:
            full = os.path.join(dirpath, name)
            rel = tree + "/" + os.path.relpath(full, base).replace(os.sep, "/")
            with open(full, "rb") as fh:
                rows.append((rel, hashlib.sha256(fh.read()).hexdigest()))
rows.sort(key=lambda r: (r[0].startswith("staged-optional/"), r[0].lower()))
with open(os.path.join(HERE, "SHA256SUMS.txt"), "w", newline="\n") as fh:
    for rel, digest in rows:
        fh.write(digest + " " + rel + "\n")
print("  wrote   SHA256SUMS.txt (%d files)" % len(rows))

print("\nStaged tree:          " + STAGED)
print("Optional (numpy>=2):  " + os.path.join(HERE, "staged-optional"))
