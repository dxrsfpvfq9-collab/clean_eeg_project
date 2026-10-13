# Deployment record — server update 2026-09

What actually went onto each server, when, and how it was checked. The
procedure itself is `QUICK_STEPS.md`; what each file changes is `README.md`.

## The file set

The 14 items in `QUICK_STEPS.md` ("Before you start"), identical on both
servers. `SHA256SUMS.txt` is the authority; all 19 entries verified against
`staged/` and `staged-optional/` on 2026-10-08 before the production copy.
Last code change in the set: `1be278c` (60 Hz `(line)` marking in the cascade
summary table, `files/Montage_6.py`, 56741 bytes).

## Development server — 2026-10-02 / 2026-10-03

- Project folder `C:\app\MyCleanEEG\CleanEEGProject`; watch dir
  `c:/app/STSEEGScreening/Source/Practitioners` (passed as the argument).
- Started with `py tomwatchdog_serialized.py "<watch dir>"`, with
  `CLEANEEG_NO_BRAIN=0` and `CLEANEEG_OFFSCREEN=1` set in the same console.
- 2026-10-03 run, four studies: every panel rc=0 (68 s, 270 s, 91 s, 158 s),
  cleaning percentages identical to the previous day's run. First full-length
  cascade (QA study E, 04.000.02, age 9, EC; 635 s recording, 20 components): `CASCADE OK`, 872 s
  (1,665 s the day before, under heavier contention).
- `(line)` marking verified on QA study E's real cascade: components 7 and 16 read
  `60.0 (line)`.
- The log file is written live. Explorer can show 0 bytes for it while the
  watchdog holds it open; Notepad or a refresh shows the real content.

## Production server — 2026-10-08

- Project folder is the same path as dev, `C:\app\MyCleanEEG\CleanEEGProject`.
  Watch dir is the built-in default,
  `c:/inetpub/wwwroot/EEGScreening/Source/Practitioners` (no argument).
- Seven replaced files backed up to `files\backup-2026-09` first.
- **Production has no `py` launcher.** Started with the interpreter the old
  watchdog used:

  ```
  set CLEANEEG_NO_BRAIN=0
  set CLEANEEG_OFFSCREEN=1
  c:\users\tcollura\appdata\local\programs\python\python312\python tomwatchdog_serialized.py
  ```

  The first start (15:23:27) followed a mistyped `set CLEANEEG_OFFSCREET=1`; it
  was stopped, the variable reset, and restarted at **15:24:17**. Uploads in that
  minute are not picked up automatically.
- Startup lines confirmed: `monitor dir:` is the inetpub path, `interpreter:`
  is the Python312 above, QuickEdit OFF, both workers started, logging to
  `logs\watchdog-2026-10-08.log`.

### First production study (EO, 20 components)

Panel `.icale.rep.pdf`, 3 pages:

- Global STD **2.52** (z −0.39) — the 1000.00 bug is gone on production.
- Moment 3 rows 432.65 / 1012.33 / 1236.88 / 1241.60 — in range, so
  `detect_artifact.py` landed.

Cascade `.imagecascade.pdf`, 42 pages (overview + table + 20 × 2):

- No black pages (dark-pixel fraction checked on every page) — offscreen
  rendering works on a GPU-less instance.
- Components numbered by size (57.6 % down to 0.3 %); Periodicity panel present;
  brain pages render (component 1: orbital frontal, BA 11 — a blink source).
- No component in 59–61 Hz, so no `(line)` rows — expected on a clean study.
- The cascade title de-identifies the name (`##### #########`).

## Follow-up: panel name masking — staged 2026-10-09, NOT yet on the servers

The panel used to print the last 30 characters of the file name unmasked, so
part of the patient name showed (`Name: <surname> 02.001.01 …`) — production
did this before the update; the cascade header never did. The panel now masks
the name the same way (`files/deidentify.py`, new `panel_label`), keeping the
30-character tail so the page-1 header still fits before the Date field:
`Name: ######## 02.001.01 AGE 12 EO`. Display only.

To roll it out, copy just these two over the deployed ones (back up first):

| File | Into | Bytes |
|---|---|---|
| `staged\files\create_report_pdf.py` | project `files\` | 60110 |
| `staged\files\deidentify.py` | project `files\` | 4497 |

No watchdog restart: each panel is a new process. Check the next panel's
header on all three pages.

## Watch for the first days

- `CASCADE in Ns` times in the log, against the upload rate. Panels never wait
  for cascades; if the cascade queue keeps growing, set `CASCADE_PASS = False`
  and render cascades on a workstation with `batch_imagecascade.py`.

## Rollback

Copy `files\backup-2026-09` back (`detect_artifact.py` to `process\`, the rest
to `files\`), Ctrl-C the new watchdog, and start the old one with the same
Python312 path: `...\python312\python tomwatchdog.py`.
