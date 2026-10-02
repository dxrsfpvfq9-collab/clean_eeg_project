# Quick steps — copy/paste version

Do this on the development server first, then on production.

The server now processes each study in **two passes**: `module7.py` writes the
brain panel in seconds, then `run_cascade.py` adds the image cascade over the
following minutes. The practitioner sees the panel straight away, and a cascade
failure can no longer destroy the panel, because the panel is already written.

## Before you start

Open this folder on your workstation in Explorer:

```
C:\BrainPanel\clean_eeg_project 2025\deploy\server-2026-09\staged
```

| Copy this | Into | Bytes |
|---|---|---|
| `files\Component_selector.py` | project `files\` | 61584 |
| `files\Montage_6.py` | project `files\` | 55286 |
| `files\color_strip.py` | project `files\` | 1767 |
| `files\deidentify.py` | project `files\` | 3967 |
| `files\create_report_pdf.py` | project `files\` | 60041 |
| `files\dummy_gui.py` | project `files\` | 56801 |
| `files\edftotextbycommandplotproc.py` | project `files\` | 4384 |
| `files\edftotextbynameplotproc.py` | project `files\` | 58024 |
| `process\brain_render.py` | project `process\` | 21032 |
| `process\offscreen_tk.py` | project `process\` | 15246 |
| `mne_data\` (whole folder, 6 surface files) | project folder — merge | ~25 MB |
| `run_cascade.py` | project folder | 2661 |
| `tomwatchdog_serialized.py` | project folder | 16336 |

`SHA256SUMS.txt` is the authority if a size here disagrees with it.

"Project folder" is the directory containing `module7.py` — on the development
server that is `C:\app\MyCleanEEG\CleanEEGProject`.

## On the server (in your Remote Desktop session)

**1. Back up the six files being replaced.**
In the project's `files\` folder, make a folder called `backup-2026-09` and copy
these into it: `Component_selector.py`, `Montage_6.py`, `create_report_pdf.py`,
`dummy_gui.py`, `edftotextbycommandplotproc.py`, `edftotextbynameplotproc.py`.

**2. Paste the new files in.**
Eight into `files\` (six overwrite; `deidentify.py` and `color_strip.py` are
new — `dummy_gui.py` and `Component_selector.py` fail to import without
`color_strip.py`), `brain_render.py` + `offscreen_tk.py` into `process\`, and
`run_cascade.py` + `tomwatchdog_serialized.py` into the project folder next to
`module7.py`. Copy the `mne_data` folder into the project folder too; if one is
already there, let it merge and overwrite — the six surface files are identical
to what the server mirrors already hold.

**3. Swap the watchdog.**
Ctrl-C the running `tomwatchdog.py`. Then, in that same console window:

```
set CLEANEEG_NO_BRAIN=0
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

**4. Upload one study and check the result.**

The panel appears within seconds; the cascade follows. The console shows:

```
QUEUED: ...
PROCESSING: ...  (queue depth 0, N GB free)
  PANEL in 6s  rc=0
CASCADE OK: ...imagecascade.pdf (20956093 bytes)
  CASCADE in 66s  rc=0
  DONE in 73s  ...
```

(Those timings are a short sample recording on a workstation. A full-length
study on the server takes longer — the panel still in seconds, the cascade in
minutes.)

Then check, next to the EDF:

- `.icale.rep.pdf` — page 1, the `Global STD` row reads about **2.5**, not 1000.
- `.imagecascade.pdf` — exists, and its pages show component graphs, not black.
  Components are numbered by size, largest first, and each page carries a
  *Periodicity* panel. After each component page comes its **brain page**:
  shaded cortex from six sides with the source in red–yellow, plus three slices.
- Still on page 1: the four **Moment 3** rows are in the hundreds to low
  thousands. If they are in the tens of thousands, that server's numpy is 2.x —
  also paste `staged-optional\process\detect_artifact.py` into `process\` and
  re-run.

That is the whole deployment. Production is identical, with the watchdog started
with no argument, in the console session kept logged in from the dev server.

## How long a study takes

The panel is seconds. The cascade is minutes to tens of minutes, and it is much
slower on a cloud VM over Remote Desktop than on a workstation — the dev server
exceeded 25 minutes on one study. The watchdog allows the cascade 90 minutes
(`CASCADE_TIMEOUT`) and the panel 10 (`PANEL_TIMEOUT`); a pass past its cap is
killed so one bad study cannot stall the queue.

Watch the `CASCADE in Ns` line on the first few studies to learn the real number
for that machine. If cascades take longer than studies arrive, the queue grows
without bound — panels keep flowing regardless, because they are the first pass,
but cascades will fall behind. If that happens, set `CASCADE_PASS = False` and
render cascades on a workstation with `batch_imagecascade.py` instead.

## If something is wrong

Copy the six files from `backup-2026-09` back into `files\`, Ctrl-C the new
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
