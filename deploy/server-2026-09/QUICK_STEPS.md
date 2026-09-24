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
| `files\Component_selector.py` | project `files\` | 61752 |
| `files\Montage_6.py` | project `files\` | 52988 |
| `files\create_report_pdf.py` | project `files\` | 57227 |
| `files\dummy_gui.py` | project `files\` | 54917 |
| `files\edftotextbycommandplotproc.py` | project `files\` | 4384 |
| `files\edftotextbynameplotproc.py` | project `files\` | 58024 |
| `run_cascade.py` | project folder | 2661 |
| `tomwatchdog_serialized.py` | project folder | 7384 |

"Project folder" is the directory containing `module7.py` — on the development
server that is `C:pp\MyCleanEEG\CleanEEGProject`.

## On the server (in your Remote Desktop session)

**1. Back up the six files being replaced.**
In the project's `files\` folder, make a folder called `backup-2026-09` and copy
these into it: `Component_selector.py`, `Montage_6.py`, `create_report_pdf.py`,
`dummy_gui.py`, `edftotextbycommandplotproc.py`, `edftotextbynameplotproc.py`.

**2. Paste the new files in.**
Six into `files\` (overwrite), and `run_cascade.py` + `tomwatchdog_serialized.py`
into the project folder next to `module7.py`.

**3. Swap the watchdog.**
Ctrl-C the running `tomwatchdog.py`. Then, in that same console window:

```
set CLEANEEG_NO_BRAIN=1
```

- development server:
  `py tomwatchdog_serialized.py "c:/app/STSEEGScreening/Source/Practitioners"`
- production server:
  `py tomwatchdog_serialized.py`

`CLEANEEG_NO_BRAIN=1` skips the 3D source-localization pages. **The servers
need it.** Those pages render through VTK, which requires OpenGL 3.2+; the AWS
instances have no GPU and Remote Desktop provides only OpenGL 1.1, so VTK does
not raise an error — it kills the process. With the variable set, the cascade is
the overview, the summary table, and one page per component, and the table's
Lobe/Region/Area columns read `n/a`.

`set` lasts only for that console window. Once a study has processed cleanly,
make it permanent from an elevated prompt:

```
setx CLEANEEG_NO_BRAIN 1 /M
```

Do **not** set it on a workstation with a real graphics card — full cascades
including brain views work there.

**4. Upload one study and check the result.**

The panel appears within seconds; the cascade follows. The console shows:

```
QUEUED: ...
PROCESSING: ...  (queue depth 0, N GB free)
  PANEL in 6s  rc=0
[CLEANEEG_NO_BRAIN set: skipping 3D source-localization pages]
CASCADE OK: ...imagecascade.pdf (5584212 bytes)
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
  *Periodicity* panel.
- Still on page 1: the four **Moment 3** rows are in the hundreds to low
  thousands. If they are in the tens of thousands, that server's numpy is 2.x —
  also paste `staged-optional\process\detect_artifact.py` into `process\` and
  re-run.

That is the whole deployment. Production is identical, with the watchdog started
with no argument, in the console session kept logged in from the dev server.

## If something is wrong

Copy the six files from `backup-2026-09` back into `files\`, Ctrl-C the new
watchdog, and start the old one: `py tomwatchdog.py`.

To keep the panel fix but stop cascades entirely, set `CASCADE_PASS = False`
near the top of `tomwatchdog_serialized.py` and restart it. Panels are
unaffected — `module7.py` no longer renders cascades at all.

## What the longer documents are for

- `README.md` — what each file changes and why.
- `MESA_OPENGL.md` — how to get the 3D brain pages working on a server with
  software OpenGL, if you ever want them there.
- `DEPLOY_STEPS_DEV.md`, `DEPLOY_PROCEDURE.md` — the same deployment with
  verification scripts (checksums, metric-by-metric before/after), for pinning
  down a problem if step 4 looks off.
