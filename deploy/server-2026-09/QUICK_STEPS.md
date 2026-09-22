# Quick steps — copy/paste version

Do this on the development server first, then on production.

## Before you start

Open this folder on your workstation in Explorer:

```
C:\BrainPanel\clean_eeg_project 2025\deploy\server-2026-09\staged
```

It contains:

```
files\Montage_6.py
files\create_report_pdf.py
files\dummy_gui.py
files\Component_selector.py
files\edftotextbycommandplotproc.py
files\edftotextbynameplotproc.py
tomwatchdog_serialized.py
```

## On the server (in your Remote Desktop session)

**1. Back up the six files being replaced.**
In the project folder, make a folder called `backup-2026-09`, and copy these
six files from `files\` into it:
`Montage_6.py`, `create_report_pdf.py`, `dummy_gui.py`,
`Component_selector.py`, `edftotextbycommandplotproc.py`,
`edftotextbynameplotproc.py`.

**2. Paste the new files in.**
Copy the six `.py` files from `staged\files\` on your workstation and paste
them into the project's `files\` folder on the server. Say yes to overwrite.
Copy `tomwatchdog_serialized.py` and paste it into the project folder itself
(next to `module7.py`).

**3. Swap the watchdog.**
In the console window where `tomwatchdog.py` is running, press Ctrl-C.
Then, in that same window:

- development server:
  `py tomwatchdog_serialized.py "c:/app/STSEEGScreening/Source/Practitioners"`
- production server:
  `py tomwatchdog_serialized.py`

It prints `monitor dir:` and `interpreter:` — glance at both.

**4. Upload one study and look at the result.**
Wait ~8 minutes. A fullscreen window will flash about 19 times while the
cascade is captured — leave it alone. Then check next to the EDF:

- `.icale.rep.pdf` — page 1, the `Global STD` row should read about **2.5**,
  not 1000.
- `.imagecascade.pdf` — should exist, ~13 MB, and its pages should show
  component graphs, not black. Components are now numbered by size, so
  component 1 is the largest, and each page carries a *Periodicity* panel
  where the Cepstrum used to be.
- Still on page 1: the four **Moment 3** rows should be in the hundreds to low
  thousands. If they are in the tens of thousands, that server's numpy is 2.x —
  also paste `staged-optional\process\detect_artifact.py` into `process\` and
  re-run the study.

That's the whole deployment. Production is the same four steps, starting the
watchdog with no argument, in the console session that's kept logged in from
the dev server.

## If something is wrong

Copy the six files from `backup-2026-09` back into `files\`, Ctrl-C the new
watchdog, start the old one: `py tomwatchdog.py`.

## What the longer documents are for

`DEPLOY_STEPS_DEV.md` and `DEPLOY_PROCEDURE.md` do the same thing with scripts
that verify each step (checksums, a metric-by-metric before/after comparison).
Use them if a result in step 4 looks off and you want to pin down why.
`README.md` explains what each file changes and why.
