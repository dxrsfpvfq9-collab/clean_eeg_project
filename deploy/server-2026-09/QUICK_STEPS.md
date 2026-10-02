# Quick steps — copy/paste version

Do this on the development server first, then on production.

The server now processes each study in **two passes**: `module7.py` writes the
brain panel within minutes, then `run_cascade.py` adds the image cascade
afterwards. The practitioner gets the panel without waiting for the cascade, and a cascade
failure can no longer destroy the panel, because the panel is already written.

## Before you start

Open this folder on your workstation in Explorer:

```
C:\BrainPanel\clean_eeg_project 2025\deploy\server-2026-09\staged
```

| Copy this | Into | Bytes |
|---|---|---|
| `files\Component_selector.py` | project `files\` | 61595 |
| `files\Montage_6.py` | project `files\` | 55286 |
| `files\color_strip.py` | project `files\` | 1767 |
| `files\deidentify.py` | project `files\` | 3967 |
| `files\create_report_pdf.py` | project `files\` | 60041 |
| `files\dummy_gui.py` | project `files\` | 56814 |
| `files\edftotextbycommandplotproc.py` | project `files\` | 4384 |
| `files\edftotextbynameplotproc.py` | project `files\` | 58024 |
| `process\brain_render.py` | project `process\` | 21032 |
| `process\offscreen_tk.py` | project `process\` | 15246 |
| `mne_data\` (whole folder, 6 surface files) | project folder — merge | ~25 MB |
| `run_cascade.py` | project folder | 2661 |
| `tomwatchdog_serialized.py` | project folder | 19338 |
| `staged-optional\process\detect_artifact.py` | project `process\` | 60659 |

`detect_artifact.py` sits in `staged-optional\` for historical reasons (it was
first staged only as numpy-2 insurance) but now goes on **every** server: it
silences the per-epoch alpha debug prints that flood the panel log. Its only
other change from production is an `int32` pin that is a no-op on numpy < 2.0 —
all 48 metrics verified identical against the previous version.

`SHA256SUMS.txt` is the authority if a size here disagrees with it.

"Project folder" is the directory containing `module7.py` — on the development
server that is `C:\app\MyCleanEEG\CleanEEGProject`.

## On the server (in your Remote Desktop session)

**1. Back up the seven files being replaced.**
In the project's `files\` folder, make a folder called `backup-2026-09` and copy
these into it: `Component_selector.py`, `Montage_6.py`, `create_report_pdf.py`,
`dummy_gui.py`, `edftotextbycommandplotproc.py`, `edftotextbynameplotproc.py` —
and from `process\`, `detect_artifact.py`.

**2. Paste the new files in.**
Eight into `files\` (six overwrite; `deidentify.py` and `color_strip.py` are
new — `dummy_gui.py` and `Component_selector.py` fail to import without
`color_strip.py`), `brain_render.py` + `offscreen_tk.py` into `process\` along
with `staged-optional\process\detect_artifact.py` (overwrite), and
`run_cascade.py` + `tomwatchdog_serialized.py` into the project folder next to
`module7.py`. Copy the `mne_data` folder into the project folder too; if one is
already there, let it merge and overwrite — the six surface files are identical
to what the server mirrors already hold.

**3. Swap the watchdog.**
Ctrl-C the running `tomwatchdog.py`. Then, in that same console window:

```
set CLEANEEG_NO_BRAIN=0
set CLEANEEG_OFFSCREEN=1
```

- development server:
  `py tomwatchdog_serialized.py "c:/app/STSEEGScreening/Source/Practitioners"`
- production server:
  `py tomwatchdog_serialized.py`

**The brain pages are ON — do not set `CLEANEEG_NO_BRAIN=1`.** An earlier
version of these steps told you to, because the old brain pages rendered through
VTK, which needs OpenGL 3.2+ and kills the process on the GPU-less AWS
instances. They are now drawn in software (`process\brain_render.py`, numpy +
matplotlib), so the variable must be 0 or unset. The `set` above covers this
console window; if you ran `setx CLEANEEG_NO_BRAIN 1 /M` before, undo it from
an elevated prompt:

```
setx CLEANEEG_NO_BRAIN 0 /M
```

**The component pages must be drawn off-screen — set `CLEANEEG_OFFSCREEN=1`.**
Without it the cascade builds each component page as a window and photographs
the desktop, so it needs a live, unlocked, connected screen: a disconnected
Remote Desktop session, a lock screen or a sleeping display gives black or wrong
pages with no error. With it the page is composited in memory
(`process\offscreen_tk.py`) and the screen is never read. The `set` above
covers this console window only; start the watchdog from the same window.

**4. Upload one study and check the result.**

The panel comes first; the cascade follows. Panels and cascades run side by
side, so a new upload's panel never waits behind an earlier study's cascade;
cascades themselves run one at a time. The console (and
`logs\watchdog-YYYY-MM-DD.log` next to the watchdog) shows something like:

```
14:02:11  QUEUED (created): ...\study.edf
14:02:17  PANEL START: ...\study.edf  (panels waiting 0, cascades waiting 0, 39.4 GB free)
    P| [offscreen] ON - component page composited with Agg, screen not read
    P| ...
14:06:39    PANEL in 262s  rc=0  ...\study.edf
14:06:39  CASCADE START: ...\study.edf  (cascades waiting 0)
    C| [offscreen] ON - component page composited with Agg, screen not read
    C| ...
    C| CASCADE OK: ...\study.imagecascade.pdf (30961075 bytes)
15:29:43    CASCADE in 4984s  rc=0  ...\study.edf
```

Lines starting `P|` come from the panel pass and `C|` from the cascade pass;
the two interleave while both run. **Check for `[offscreen] ON`.** If it reads
`[offscreen] OFF`, the variable was not set in the window the watchdog was
started from — Ctrl-C, `set CLEANEEG_OFFSCREEN=1`, and start it again.

**Don't copy log text out of the console — use `logs\watchdog-*.log`.** In a
Windows console, selecting text (QuickEdit) pauses all output to that window,
and that pause blocks the running panel or cascade until the selection is
cleared: no error, 0% CPU, no new files. The watchdog now turns QuickEdit off
for its own window at startup (it prints `console QuickEdit: OFF ...`) and
writes to the console from a separate thread, so even a Ctrl+A selection only
pauses the window — the study keeps running and the log keeps every line. When
the selection clears, the window says how many lines it skipped. Press **Esc**
to clear a selection (title starts with **Select**). Do not press Ctrl+C in
that window when nothing is selected: it stops the watchdog and the running study.

(Those timings are from the development server, before the October 2026
colour-strip speed-up; see "How long a study takes" below.)

Then check, next to the EDF:

- `.icale.rep.pdf` — page 1, the `Global STD` row reads about **2.5**, not 1000.
- `.imagecascade.pdf` — exists, and its pages show component graphs, not black.
  Components are numbered by size, largest first, and each page carries a
  *Periodicity* panel. After each component page comes its **brain page**:
  shaded cortex from six sides with the source in red–yellow, plus three slices.
- Still on page 1: the four **Moment 3** rows are in the hundreds to low
  thousands. If they are in the tens of thousands, `detect_artifact.py` from
  step 2 did not land in `process\` and that server's numpy is 2.x — copy it
  and re-run.

That is the whole deployment. Production is identical, with the watchdog started
with no argument, in the console session kept logged in from the dev server.

## How long a study takes

The panel takes about 2–5 minutes on the development server for a 3–10 minute
recording. The cascade is much longer and far slower on a cloud VM than on a
workstation: about 80 minutes for a 10-minute, 20-component study on the
development server before the October 2026 colour-strip speed-up
(`files\color_strip.py`), which made each component roughly 4× faster in a
local profile (the component page itself about 8×). The watchdog allows the panel 10 minutes (`PANEL_TIMEOUT`) and
the cascade 4 hours (`CASCADE_TIMEOUT`); a pass past its cap is killed. The
cascade cap is there to catch a genuine hang, not to ration throughput.

Watch the `CASCADE in Ns` line on the first few studies to learn the real number
for that machine. If cascades take longer than studies arrive, the queue grows
without bound — panels keep flowing regardless, because they are the first pass,
but cascades will fall behind. If that happens, set `CASCADE_PASS = False` and
render cascades on a workstation with `batch_imagecascade.py` instead.

## If something is wrong

Copy the files from `backup-2026-09` back (`detect_artifact.py` to `process\`, the rest to `files\`), Ctrl-C the new
watchdog, and start the old one: `py tomwatchdog.py`.

To keep the panel fix but stop cascades entirely, set `CASCADE_PASS = False`
near the top of `tomwatchdog_serialized.py` and restart it. Panels are
unaffected — `module7.py` no longer renders cascades at all.

## What the longer documents are for

- `README.md` — what each file changes and why.
- `MESA_OPENGL.md` — superseded: the brain pages no longer need OpenGL at all.
- `DEPLOY_STEPS_DEV.md`, `DEPLOY_PROCEDURE.md` — the same deployment with
  verification scripts (checksums, metric-by-metric before/after), for pinning
  down a problem if step 4 looks off.
