# Deployment procedure — Global STD fix + image cascades

Four hops, in this order. Each one is verified before the next begins.

```
 [1] local dev mirror  ──RDP──▶  [2] development server  (test)
                                            │
                                     dev signed off
                                            ▼
 [3] local prod mirror ──RDP──▶  [4] production server   (test, go live)
```

| Hop | Folder / machine | Tool |
|---|---|---|
| 1 | `C:\BrainPanel\CleanEEGProject - development` (this workstation) | `apply_local.ps1 -Target dev` |
| 2 | development server | `DEPLOY_STEPS_DEV.md`, copied through Remote Desktop |
| 3 | `C:\BrainPanel\CleanEEGProject - production` (this workstation) | `apply_local.ps1 -Target prod` |
| 4 | production server | `DEPLOY_STEPS_DEV.md` again, with the production differences listed at its end |

---

## Affected files

Eight files. Six replace existing ones, one is new, one is conditional.

| # | File | What changes | How much | Why |
|---|---|---|---|---|
| 1 | `files\edftotextbynameplotproc.py` | `FastICA(..., whiten=...)` pinned to arbitrary-variance | 1 hunk, 14 lines | **Global STD fix.** Only this metric moves. |
| 2 | `files\edftotextbycommandplotproc.py` | `selstring[12] = 1` | 1 hunk, 5 lines | Turns the cascade on in the unattended (watchdog) path. |
| 3 | `files\Montage_6.py` | Re-enables the overview `savefig` that was commented out in Dec 2024; sorts cascade pages by component % | whole file, 80 lines | Without the `savefig` the cascade dies with `FileNotFoundError` on `.ica.png`. |
| 4 | `files\dummy_gui.py` | Head-map contour scale/sign fixes; Cepstrum panel replaced by Periodicity | whole file | Cascade component pages only. |
| 4b | `files\Component_selector.py` | Same Periodicity panel; button grid renumbered by magnitude | whole file | Interactive `module61` review only; ships so the GUI and the cascades agree. |
| 5 | `files\create_report_pdf.py` | `save_gui_screenshot` forces the window topmost before capture | 1 hunk, 18 lines | Stops the terminal or another window being captured instead of the component view. The page-3 legend rework in dev is **not** included. |
| 6 | `tomwatchdog_serialized.py` | **New file.** One study at a time; waits for upload to finish; 25-min kill; low-disk warning | new | Two cascades at once capture each other's windows. Replaces `tomwatchdog.py` at runtime; the old file is left in place. |
| 7 | `process\detect_artifact.py` | `dtype=np.int32` pins in `detect_drowsiness` / `detect_moments` | 2 lines | **Only if the server's numpy is ≥ 2.0.** A no-op on 1.x. Lives in `staged-optional\`. |

Everything is built from the **production source** by `build_server_update.py`,
so nothing else from the dev tree rides along — no PLTS, no discriminant, no
pre-ICA line filter (which would move 39 of 48 metrics; see the README).

**Two files that must NOT move between mirrors:** `plot\plot_svc.py` and
`tomwatchdog.py` differ between the dev and production mirrors for reasons
unrelated to this deployment (different alpha peak-search windows; different
watched folder and launcher). `apply_local.ps1` never touches either. Do not
copy them by hand.

---

## Disk space — can the site hold 1,000+ cascades?

Yes, comfortably. Measured on the seven cascades rendered for this work:

| Per study | Size |
|---|---|
| `.imagecascade.pdf` | 12.5 – 14.2 MB |
| `.ica.png` (overview, left behind) | 0.2 – 0.4 MB |
| **Added per study** | **13.6 MB mean, 14.6 MB max** |
| Transient during render (19 PNG captures, deleted at the end) | ~12 MB |

Size is set by channel count, not recording length — one page pair per ICA
component at fixed screen resolution — so a 20-minute study costs the same as a
10-minute one. A 20-channel recording adds one more component pair, ~0.7 MB.

| Studies | Space used (max per study) |
|---|---|
| 1,000 | 14.6 GB |
| 2,000 | 29 GB |
| 5,000 | 73 GB |
| 6,800 | ~100 GB — the whole current free space |

So 1,000 cascades consume about **15 % of the 100 GB** you have free.
Keeping a 10 GB floor, the disk holds roughly **6,100 cascades** before it
becomes a concern. The serialized watchdog prints a `*** LOW DISK SPACE ***`
line before each study once free space drops under 10 GB, and keeps processing
— the panel is the essential output and is never withheld.

Two things to keep in mind:

- The panel-only footprint today is ~1 MB per study plus the 6–7 MB EDF. The
  cascade multiplies the per-study output by about 14×. Any backup, sync or
  archive job that copies the upload tree will grow by the same factor.
- Checking is one line on the server: `Get-PSDrive C | Select-Object Free`.

---

## Hop 1 — local dev mirror

On this workstation, in PowerShell:

```powershell
cd "C:\BrainPanel\clean_eeg_project 2025\deploy\server-2026-09"
.\apply_local.ps1 -Target dev
```

This backs up the six files it replaces into
`CleanEEGProject - development\_backup-2026-09\`, overlays `staged\`, and runs
the checksum check. Required last line: `All staged files verified.`

Leave `staged-optional\` out at this hop — you do not yet know the dev server's
numpy version. If step 5 on the server says 2.x, come back and run
`.\apply_local.ps1 -Target dev -WithOptional` so the mirror matches the server.

The mirror is now the exact tree to push. Because `apply_local.ps1` only
touches the seven files, everything else in that folder stays as it was.

---

## Hop 2 — development server

Follow **`DEPLOY_STEPS_DEV.md`** start to finish. Its steps, in brief:

1. RDP in with drive redirection; confirm no screen saver / lock timeout.
2. `robocopy` this deploy folder to `C:\deploy-2026-09` on the server.
3. Find the project root, set `$PROJ`.
4. Back up the whole project folder.
5. Check Python / numpy / sklearn versions.
6. Copy `staged\` (and `staged-optional\` if numpy 2.x) over the project.
7. `verify_copy.ps1` — every file OK.
8. Pick an already-processed study; **save its existing panel PDF aside**.
9. Re-run it with `module7.py` (~8 min, stay connected, do not cover the window).
10. `verify_panel.py` old vs new — must print `PASS: only Global STD changed.`
11. Open the cascade PDF and page through it looking for black pages.
12. Stop `tomwatchdog.py`; start `tomwatchdog_serialized.py "c:/app/STSEEGScreening/Source/Practitioners"` in the same console; upload two studies and confirm the second waits.
13. Rollback = `robocopy` from the step-4 backup.

**Sign-off for dev** is steps 10, 11 and 12 all passing. Then leave it running
and watch the next few real uploads land correctly before moving on.

---

## Hop 3 — local prod mirror

Only after dev is signed off.

```powershell
cd "C:\BrainPanel\clean_eeg_project 2025\deploy\server-2026-09"
.\apply_local.ps1 -Target prod
```

Add `-WithOptional` if — and only if — production's numpy turns out to be 2.x.
Required last line: `All staged files verified.`

---

## Hop 4 — production server

Same thirteen steps as hop 2, with these differences:

- **Upload tree** is `C:\inetpub\wwwroot\EEGScreening\Source\Practitioners`.
- **Watchdog** starts with **no argument** — that path is its default:
  `py tomwatchdog_serialized.py`. Check its first two printed lines
  (`monitor dir:`, `interpreter:`) before uploading anything.
- **Console session.** Production's live desktop is the console kept logged in
  from the dev server. The watchdog goes back into *that* session. Do not start
  it from anywhere else.
- **Verification study.** Use one production has already processed, so the
  before/after comparison is production-vs-production. Do not compare against a
  dev-server panel — the two servers' `plot_svc.py` differ.
- **Timing.** Each upload now takes ~8 minutes to fully process instead of
  under a minute. If practitioners are told when to expect results, that
  message needs updating.

---

## After go-live

For the first day, check three things on production:

1. `Get-PSDrive C | Select-Object Free` — falling by ~14 MB per study, nothing
   more.
2. The watchdog console — every upload shows `QUEUED → PROCESSING → DONE rc=0`,
   and no `TIMED OUT` or `LOW DISK SPACE` lines.
3. Open one or two of the day's cascades. Black pages mean the console session
   was lost — reconnect from dev and re-run those studies.

Every panel issued before this deployment carries the bogus Global STD row
(`1000.00`, z `2642.71`). Nothing else on those panels is wrong, and their total
out-of-bounds count is one too high. Whether to re-issue any of them is a
separate decision.

---

## Rollback at any hop

- **Local mirrors:** copy `_backup-2026-09\` back over the folder.
- **Servers:** `robocopy "$PROJ.bak-2026-09" $PROJ /E`, then restart the
  original `tomwatchdog.py`.

No data files, reference databases or on-disk formats are touched by any of
the seven files, so rollback is a complete undo.
