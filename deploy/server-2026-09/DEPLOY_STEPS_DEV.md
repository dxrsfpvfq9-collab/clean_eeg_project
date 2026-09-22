# Development server — step by step

Follow in order, in one sitting. Steps 8–10 take about ten minutes and **you
must stay connected to the dev server for them** — its desktop only composites
while your RDP session is live, and a cascade rendered after you disconnect
comes back black.

Production is not affected by your dev connection: its session is held open by
the console logged in from dev.

Rollback is step 13 and takes under a minute at any point.

---

## 1. Start the RDP session with drive redirection

In the Remote Desktop client, before connecting: **Local Resources → More →
Drives**, tick your `C:` drive. Then connect to the dev server.

Redirected drives appear on the server as `\\tsclient\C`.

Also confirm no screen saver and no lock-screen timeout on this box
(`Settings → Personalization → Lock screen → Screen saver settings`). A screen
saver firing mid-render poisons the captures.

---

## 2. Copy the deployment folder to the server

In PowerShell **on the dev server**:

```powershell
robocopy "\\tsclient\C\BrainPanel\clean_eeg_project 2025\deploy\server-2026-09" "C:\deploy-2026-09" /E
```

Robocopy exits non-zero on success — anything under 8 is fine, 8 or above is a
real failure.

Working from a local copy rather than straight off `\\tsclient` keeps the
checksum check honest and survives a redirection hiccup.

---

## 3. Find the project root

If you already know it, skip ahead. Otherwise, with the watchdog running:

```powershell
Get-CimInstance Win32_Process -Filter "name='python.exe'" | Select-Object ProcessId, CommandLine | Format-List
```

That shows the command line the watchdog and any module7 children were launched
with. Failing that:

```powershell
Get-ChildItem C:\ -Recurse -Filter module61.py -ErrorAction SilentlyContinue | Select-Object -First 5 FullName
```

Set it once and use it for the rest of the session:

```powershell
$PROJ = "C:\<the directory containing module7.py>"
Test-Path "$PROJ\module7.py"     # must print True
```

---

## 4. Back up

```powershell
robocopy $PROJ "$PROJ.bak-2026-09" /E
```

Confirm it exists before going further:

```powershell
Test-Path "$PROJ.bak-2026-09\files\Montage_6.py"
```

---

## 5. Check numpy and sklearn

```powershell
cd $PROJ
py -c "import sys, numpy, sklearn; print(sys.version.split()[0], numpy.__version__, sklearn.__version__)"
```

Expect Python 3.12 and numpy 1.x.

- **numpy 1.x** — the main `staged\` set is all you need.
- **numpy 2.0 or higher** — you must also deploy `staged-optional\`, and be
  aware this server's existing panels already have four corrupt Moment 3 rows.
  See the README section "Check the server's numpy version first".

If `py` is not on PATH, `run2.bat` in the project points at
`C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe` —
use that explicitly and substitute it for `py` throughout.

---

## 6. Copy the staged files in

```powershell
robocopy "C:\deploy-2026-09\staged" $PROJ /E
```

If step 5 said numpy 2.x, also:

```powershell
robocopy "C:\deploy-2026-09\staged-optional" $PROJ /E
```

This overwrites six files and adds `tomwatchdog_serialized.py`. It does not
touch the reference databases, the watched upload folder, or any output.

---

## 7. Verify the copy landed intact

```powershell
cd C:\deploy-2026-09
.\verify_copy.ps1 -ProjectRoot $PROJ
```

On numpy 1.x, `process/detect_artifact.py` will report MISSING — that is
expected, since you deliberately skipped the optional file. Add `-SkipOptional`
to silence it:

```powershell
.\verify_copy.ps1 -ProjectRoot $PROJ -SkipOptional
```

Everything else must say OK. A MISMATCH means the copy rewrote line endings —
recopy in binary rather than continuing.

---

## 8. Pick a verification study and save its current panel

Choose a study this server has already processed, so there is a genuine before
and after. Any `.edf` in the practitioners tree with a matching
`.icale.rep.pdf` next to it will do.

The dev server's upload tree is `C:\app\STSEEGScreening\Source\Practitioners`
(that is what its `tomwatchdog.py` watches; production uses
`C:\inetpub\wwwroot\EEGScreening\Source\Practitioners`).

```powershell
$EDF = "C:\app\STSEEGScreening\Source\Practitioners\<...>\<study>.edf"
$OLD = "C:\deploy-2026-09\before.icale.rep.pdf"
Copy-Item ($EDF -replace '\.edf$', '.icale.rep.pdf') $OLD
Test-Path $OLD     # must print True
```

**Do this before step 9.** Re-running overwrites the panel in place, and
without the copy you have nothing to compare against.

---

## 9. Re-run the study

```powershell
cd $PROJ
py module7.py "$EDF"
```

Expect roughly eight minutes, and a fullscreen window flashing once per ICA
component — that is the cascade capturing. **Do not minimize the RDP client,
cover the window, or disconnect.** Leave the machine alone until the prompt
returns.

---

## 10. Check the panel did not move

```powershell
py C:\deploy-2026-09\verify_panel.py $OLD ($EDF -replace '\.edf$', '.icale.rep.pdf')
```

Required result:

```
Global STD    1000.00    2.54    2642.71    -0.34   <- expected
PASS: only Global STD changed. Panel is otherwise identical.
```

Anything reporting UNEXPECTED — stop and go to step 13. If the unexpected rows
are the four Moment 3 rows specifically, that is the numpy issue from step 5,
not a problem with these changes.

---

## 11. Check the cascade

```powershell
Get-Item ($EDF -replace '\.edf$', '.imagecascade.pdf') | Select-Object Name, Length
```

Expect roughly 12–14 MB. Open it and page through:

- Page 1 is the overview heatmap plus stacked component traces.
- Page 2 is the summary table, sorted by component % descending.
- After that, two pages per component — the component view, then the brain view.
- Components are numbered by magnitude, so page 3 is the largest component and
  the table's Comp. # column runs 1..n in descending % order.
- Each component page shows a *Periodicity* panel where the Cepstrum was.

**Look for black or wrong-window pages.** That is the one failure mode that
produces a plausible-looking file full of garbage, and it is the reason this
step is not just a file-size check.

---

## 12. Switch the watchdog

Stop the running `tomwatchdog.py` — Ctrl-C in the console session it lives in,
or:

```powershell
Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -like "*tomwatchdog*" } | ForEach-Object { Stop-Process -Id $_.ProcessId }
```

Start the replacement **in that same console session** — not over SSM, not as a
service, or every cascade it renders will be black:

```powershell
cd $PROJ
py tomwatchdog_serialized.py "c:/app/STSEEGScreening/Source/Practitioners"
```

The argument is the folder to watch. **On the dev server it is required**,
because the script's built-in default is production's
`c:/inetpub/wwwroot/EEGScreening/Source/Practitioners`. The first lines it
prints are `monitor dir:` and `interpreter:` — check both before uploading.

Then upload two studies back to back and watch the log. It must show:

```
QUEUED: ...study A...
QUEUED: ...study B...
PROCESSING: ...study A...  (queue depth 1)
  DONE in ...s  rc=0  ...study A...
PROCESSING: ...study B...  (queue depth 0)
```

Study B must not start until A reports DONE. If both run at once, the old
watchdog is still alive somewhere — find and stop it.

---

## 13. Rollback

```powershell
robocopy "$PROJ.bak-2026-09" $PROJ /E
```

Then restart the original `tomwatchdog.py`. Nothing here touches data files,
reference databases, or on-disk formats, so this is a complete undo.

---

## When dev is signed off

Repeat 1–12 against production with these differences:

- The upload tree is `C:\inetpub\wwwroot\EEGScreening\Source\Practitioners`.
- Start the watchdog with **no argument** — that path is its default.
- Production's console is the one kept logged in from this dev server, so the
  watchdog goes back into *that* session rather than a new one.
- The full sequence, including the two local mirror folders, is in
  `DEPLOY_PROCEDURE.md`.
