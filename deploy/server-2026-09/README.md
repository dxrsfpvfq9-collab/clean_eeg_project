# Server update — September 2026

Two changes for the STS EEG screening server:

1. **Fix Global STD** in the Brain Panel (currently prints `1000.00`, z `2642.71`
   on every study).
2. **Produce an image cascade** alongside every brain panel.

`staged/` holds the exact files to copy. Every one is built from the **current
production source**, so it carries these two changes and nothing else — none of
the PLTS, discriminant, page-3 legend, or pre-ICA-filter work from the dev tree
comes along. Rebuild at any time with:

```bash
py deploy/server-2026-09/build_server_update.py
```

**Deploying?** `QUICK_STEPS.md` is all you need: back up six files, paste
seven in, restart the watchdog, check one study. `DEPLOY_PROCEDURE.md` and
`DEPLOY_STEPS_DEV.md` are the same thing with verification scripts at each
step, for when a result looks off. This file explains what changed and why.

---

## The files

| Staged file | Change | Ships |
|---|---|---|
| `files/edftotextbynameplotproc.py` | Global STD whitening fix | 1 hunk |
| `files/edftotextbycommandplotproc.py` | `selstring[12] = 1` — cascade on | 1 hunk |
| `files/create_report_pdf.py` | `save_gui_screenshot` raises window before capture | 1 hunk |
| `files/Montage_6.py` | Re-enable overview `savefig`; sort pages by component %; renumber components by magnitude | whole file |
| `files/dummy_gui.py` | Head-map scale/sign fixes; Cepstrum panel replaced by Periodicity | whole file |
| `files/Component_selector.py` | Same Periodicity panel + renumbered button grid, for the interactive GUI | whole file |
| `tomwatchdog_serialized.py` | One study at a time + wait for upload to finish | new file |

`Montage_6.py`, `dummy_gui.py` and `Component_selector.py` ship whole because
every change in them is display, and all three were checked to import nothing
production does not already have.

`Component_selector.py` drives the interactive review in `module61`, not the
cascade. It ships so one machine does not disagree with itself: without it the
GUI would still show the Cepstrum panel and FastICA numbering while the
cascades it produces show Periodicity and magnitude numbering, and its button
grid would contradict the PDFs it had just written.

---

## Change 1 — Global STD

**Cause.** sklearn ≥ 1.3 changed `FastICA`'s default whitening to
`unit-variance`, which forces every ICA source to std 1. `global_stdmeas` is the
std of those sources after the ×1000 reconstruction scaling, so it collapses to
a constant 1000. The EC_191 database was built under the pre-1.3 default
(arbitrary, data-dependent source variance), where the metric lands near 2.5 —
hence the z of 2642.

**Fix.** Pin `whiten="arbitrary-variance"` (spelled `whiten=True` on sklearn
< 1.3; the code picks the right spelling at runtime, so it is safe whatever the
server has installed).

**Evidence.** `1412 Grace SL 01.000.02 AGE 34 EC`, dev re-run against the
server's own panel PDF for that study:

| | production | after fix |
|---|---|---|
| Global STD value | 1000.00 | 2.54 |
| Global STD z | 2642.71 | −0.53 (normal range 1.91–3.42) |
| other 47 metrics | — | identical to printed precision |

That 47/48 match also confirms the dev and production pipelines agree
numerically, and that FastICA is deterministic here (`random_state=0` has been
set since the baseline).

**Effect on existing reports.** Every panel issued before this fix has a bogus
Global STD row. Nothing else in those reports is affected, and the total
out-of-bounds count on each of them is one too high.

---

## Change 2 — image cascades

Turning on `selstring[12]` produces `<edfname>.imagecascade.pdf` next to the
EDF, plus `<edfname>.ica.png` (the overview, left behind as a side artifact).

### Screen capture — how this site is already set up

Cascade pages are made with `ImageGrab.grab(bbox=...)`, which copies **raw
screen pixels** from the interactive desktop. A Windows service, a Scheduled
Task set to "run whether user is logged on or not", SSM Run Command, or session
0 in general has no such desktop — captures come back black, with **no error**.

**Production is already covered.** A console stays logged into the production
server from the development server, so production always has a live session and
the graphics render correctly. This is a verified working arrangement, not a
theory — keep it in place. Two things follow from it:

1. **Do not start the watchdog from SSM Run Command or as a service.** It must
   be launched inside that console session, or every cascade it renders is
   black. Same for any manual `module7.py` run you want cascades from.
2. **The development server itself is the weak link during verification.** Its
   desktop is live only while you are actually connected to it by RDP. If you
   start a cascade test on dev and then disconnect, that render can come back
   black — production is unaffected, because its session is held open by dev's
   client. Stay connected for the ~8 minutes a dev verification takes.

If a nested session ever *does* produce black pages, the usual cause is a
minimized RDP client: Windows can stop compositing a minimized remote session.
Setting `RemoteDesktop_SuppressWhenMinimized` (DWORD, value 2) under
`HKCU\Software\Microsoft\Terminal Server Client` on the machine running the
client keeps it rendering while minimized.

Two further constraints, independent of the session question:

- **Nothing may cover the component window.** `save_gui_screenshot` now forces
  it topmost and lets the compositor settle, which handles the common case, but
  a screen saver or lock screen will still poison the output. Disable both on
  any machine rendering cascades.
- **Studies cannot render concurrently** — see the watchdog note below.

Fallback if cascades on the server prove impractical for any other reason:
deploy change 1 only (`selstring[12] = 0`) and keep rendering cascades on a
workstation with `batch_imagecascade.py`.

### Throughput

A panel alone takes well under a minute. A panel plus a 19-component cascade
took **7–8.5 minutes per study** on the four 2026.09.08 studies. Plan the
server's ingest rate around ~8 minutes per upload, not seconds. Output grows
from ~1 MB per study to ~13–14 MB.

### Watchdog serialization (required)

`tomwatchdog.py` currently calls `subprocess.Popen` per created `.edf` with no
limit, so simultaneous uploads mean simultaneous `module7` processes. With
panel-only processing they just compete for CPU. **With cascades on, two at once
means two fullscreen Tk windows fighting over one screen, and both cascades
capture whichever window is on top — silently wrong output, not an error.**

`tomwatchdog_serialized.py` replaces it with a single worker thread over a
queue. It also waits for each upload's file size to stop changing before
starting (`on_created` fires when the file appears, not when the last byte
lands — an 8-minute cascade on a truncated EDF is 8 minutes wasted), and kills
any study that exceeds 25 minutes so one hung render cannot stall the queue.

### The pre-ICA line filter is deliberately NOT ported

The dev tree applies an `lp50 + notch60` filter before ICA whenever
`selstring[12] == 1`, to stop 60 Hz interference from eating ICA components.
**It must not go to production.** Montage 6 rebuilds the report signals *from*
the ICA decomposition, so filtering before ICA moves the panel itself. Measured
on `1412 Grace SL EC`, filtered vs unfiltered:

| | rows whose z moved > 0.01 |
|---|---|
| unfiltered (this deployment) | 1 / 48 — Global STD, the intended fix |
| lp50 + notch60 | **39 / 48** |

with individual shifts well past 2 sigma: Beta Max Front **+3.21**, PDR Max
Post. **+2.58**, Front Alpha Asym **−2.00**, PDR Synchrony −1.36. That would
silently invalidate every comparison against EC_191.

Leaving the filter out also means the cascade shows *the same decomposition the
panel was computed from*, which is what you want when the cascade is being used
to explain a panel. The side effect is that line-noisy recordings will show
spurious 60 Hz components in the cascade — which is arguably the honest picture,
since those same components are in the panel's own ICA.

---

## Check the server's numpy version first

```bash
py -c "import numpy; print(numpy.__version__)"
```

**If it reports 2.0 or higher, deploy `staged-optional/process/detect_artifact.py`
as well, and know that the server's existing panels already have four corrupt
rows.** `detect_drowsiness` and `detect_moments` rely on `x_values**2`
overflowing int32 at i ≥ 46341 — the wrap-around values are what EC_191 was
built from. numpy 2.0 changed `np.arange`'s default to int64, which stops the
overflow and inflates the Moment 3 rows by 50–130×, with no error or warning.

This is not hypothetical: it is what the first end-to-end test of this
deployment produced when the production tree ran under numpy 2.1.3.

| metric | expected | under numpy 2.1.3 | z |
|---|---|---|---|
| PDR Moment 3 | 477.45 | 32356.28 | −0.71 → **+97.75** |
| Beta Moment 3 | 1503.10 | 61175.22 | +0.20 → **+96.01** |
| Theta Moment 3 | 900.35 | 65167.49 | −0.81 → **+107.46** |
| Delta Moment 3 | 1450.42 | 61198.70 | +0.10 → **+108.21** |

On numpy < 2.0 the pinned file is a no-op — `np.arange` already returns int32
there — so deploying it costs nothing and removes the trap from any future
Python or numpy upgrade. `verify_panel.py` catches this failure if it happens.

---

## Change 3 — cascade display

Neither of these touches a metric; both were confirmed against a full panel
re-run in which all 48 rows were byte-identical.

**Periodicity panel.** The Cepstrum panel on each cascade component page is
replaced by one titled *Periodicity*. It takes the signature events the
template-correlation strip already detects — the red dots — treats their times
as a point process, and transforms it, so the panel answers whether the
signature RECURS rhythmically or at random. Note this is the rhythm of the
recurrence, not the component's own carrier: a 10 Hz component can throw its
signature every ~820 ms. The panel prints a verdict, the mean recurrence
interval ±1 SD, and the event count.

The verdict compares the spectral peak against 200 surrogate trains carrying
the same event count and the same 35-sample refractory, thresholded at
alpha/n_components so the 1% false-positive rate applies to the STUDY rather
than to each component — at 19 components a per-component 1% would have fired
on roughly one study in five. Seeded, so the verdict reproduces run to run.

**Component renumbering.** Components are numbered by magnitude everywhere —
largest is 1 — in the mixing matrix, the stacked traces, the cascade pages,
the summary table, the Machine Selected readout and the selector's button
grid. The arrays keep FastICA's ordering, so the reconstruction and every
metric are untouched, and `icabutton[]` is still keyed by original index so
the existing `icabutton[orig-1]` lookups keep working.

One consequence to expect: **a report issued before this change numbers the
same study's components differently.** Old and new cascades for one recording
cannot be cross-referenced by component number.

## Verification already done

**This section predates Change 3.** The end-to-end run below exercised the
Global STD fix and the cascade, not the Periodicity panel or the renumbering.
Those were checked separately — a full panel re-run on `1419 Oliver Y. EC`
produced 48 of 48 rows identical — but re-run `verify_panel.py` on the dev
server once the rebuilt bundle is in place, so one run covers everything.

The staged tree was tested end-to-end before hand-off: a copy of the production
source with `staged/` overlaid, driven through `module7.py` exactly as the
watchdog drives it, on `1412 Grace SL 01.000.02 AGE 34 EC` — a study the server
had already processed.

- Panel: `PASS: only Global STD changed.` All 47 other metrics identical to the
  server's own PDF.
- Cascade: `GraceEC.imagecascade.pdf`, 13.6 MB, produced in the same run;
  `.ica.png` written (the `savefig` fix) and the per-component temp PNGs
  cleaned up afterwards.
- Runtime: ~6 minutes for panel + cascade on this study.

The one caveat is the numpy version above — the first attempt ran production's
unpinned `detect_artifact.py` under numpy 2.1.3 and failed the check on the four
Moment 3 rows. That is a property of the test machine's numpy, not of these
changes; with the pinned file overlaid the same test passes.

---

## Deployment

### 1. Development server

**Follow `DEPLOY_STEPS_DEV.md`** — the full RDP walkthrough, with the exact
commands, the order that keeps a before/after panel pair intact, and rollback.
The rest of this section is the summary: back up the project, copy `staged\`
over it (plus `staged-optional\` if numpy is 2.x), verify with
`verify_copy.ps1`.

### 2. Verify the panel did not move

Pick a study the server has already processed, keep its existing
`.icale.rep.pdf`, re-run it, and compare:

```bash
py module7.py "<path-to-that>.edf"
py verify_panel.py "<old>.icale.rep.pdf" "<new>.icale.rep.pdf"
```

Expected: `PASS: only Global STD changed.` Anything else — stop and
investigate before promoting.

Also confirm `<edfname>.imagecascade.pdf` was created and that its pages show
the component views rather than black or the wrong window.

### 3. Switch the watchdog

Stop `tomwatchdog.py`, start `tomwatchdog_serialized.py` in the SAME console
session the current watchdog runs in — the one kept logged in from the
development server. Upload two studies back to back and confirm the log shows
the second one `QUEUED` and only starting after the first reports `DONE`, and
that both cascades contain component views rather than black pages.

### 4. Production

Repeat 1–3. Rollback is restoring the six files from the backup — none of the
changes touch data files, the reference database, or on-disk formats.

---

## Doing it over AWS CLI / SSM

### What SSM can and cannot do here

SSM Run Command executes through the SSM Agent, which runs as
`NT AUTHORITY\SYSTEM` in **session 0 — a non-interactive session with no
desktop**. `aws ssm start-session` gives a PowerShell prompt, not a desktop,
and has the same limitation.

| Task | Run Command | Notes |
|---|---|---|
| Copy files | yes | no native copy; use S3 or base64, below |
| Check numpy, checksums, backups | yes | |
| Start/stop the watchdog | yes | but see the desktop caveat |
| Panel-only re-run + `verify_panel.py` | probably | montage 6 still builds a Tk window before destroying it; usually fine headless, but if it hangs or errors, run it in RDP instead |
| **Cascade render** | **no** | `ImageGrab` copies the *interactive* desktop, which a session-0 process is not attached to. Output is black, with no error. |

So: **use SSM for transfer, inspection and the panel check; do the cascade work
in a real RDP console session.** SSM can still get you that session without
opening inbound ports — see "RDP through SSM" below.

### One-time setup

On this workstation:

```bash
msiexec /i https://awscli.amazonaws.com/AWSCLIV2.msi
```

Then the Session Manager plugin (needed for `start-session` / port forwarding),
from `https://s3.amazonaws.com/session-manager-downloads/plugin/latest/windows/SessionManagerPluginSetup.exe`.

Configure credentials yourself — `aws configure` (or `aws configure sso`). The
IAM principal needs `ssm:DescribeInstanceInformation`, `ssm:SendCommand`,
`ssm:GetCommandInvocation`, `ssm:StartSession`, `ssm:TerminateSession`, and
`s3:PutObject`/`s3:GetObject` if you use the S3 relay.

On each instance: SSM Agent (preinstalled on AWS Windows Server AMIs), an IAM
instance profile containing `AmazonSSMManagedInstanceCore`, and outbound 443 to
the `ssm`, `ssmmessages` and `ec2messages` endpoints. No inbound rules needed.

Confirm both servers are reachable:

```bash
aws ssm describe-instance-information --query "InstanceInformationList[].{Id:InstanceId,Name:ComputerName,Ping:PingStatus,Ver:PlatformVersion}" --output table
```

An instance missing here is a prerequisite problem, not a transient one.

### Quoting

Windows PowerShell mangles the inline JSON in `--parameters`. Put the request in
a file and use `--cli-input-json file://req.json`, or run the AWS CLI from Git
Bash. This is the single biggest time sink when driving Run Command by hand.

### Getting the files across

**Option A — S3 relay (recommended).** Verifiable, repeatable, no size limits.
Needs `s3:GetObject` on the instance profile.

```bash
aws s3 cp deploy/server-2026-09/staged s3://<your-bucket>/cleaneeg/2026-09/staged --recursive
```

Then on the instance, via `AWS-RunPowerShellScript`:

```powershell
$dst = "C:\BrainPanel\CleanEEGProject"
Copy-Item $dst "$dst.bak-2026-09" -Recurse -Force
aws s3 cp s3://<your-bucket>/cleaneeg/2026-09/staged $dst --recursive
```

(If the AWS CLI is not on the instance, use `Read-S3Object -BucketName ... -KeyPrefix ... -Folder ...` from AWS Tools for PowerShell, which ships with the Windows AMIs.)

**Option B — base64 inline, no S3.** Each staged file is 12–17 KB as gzipped
base64, comfortably inside Run Command's request size. Send **one file per
command** — all seven at once is ~76 KB and may exceed it.

Locally, per file:

```bash
gzip -9 -c "deploy/server-2026-09/staged/files/Montage_6.py" | base64 -w0 > payload.b64
```

On the instance, with `$b64` set to that string:

```powershell
$bytes = [Convert]::FromBase64String($b64)
$in  = New-Object IO.MemoryStream(,$bytes)
$gz  = New-Object IO.Compression.GzipStream($in, [IO.Compression.CompressionMode]::Decompress)
$out = New-Object IO.FileStream("C:\BrainPanel\CleanEEGProject\files\Montage_6.py", "Create")
$gz.CopyTo($out); $out.Close()
```

**Option C — RDP through SSM.** No inbound ports, and it gives you the
interactive desktop the cascade needs:

```bash
aws ssm start-session --target i-0123456789abcdef0 --document-name AWS-StartPortForwardingSession --parameters "portNumber=3389,localPortNumber=13389"
```

Then `mstsc /v:localhost:13389` and use clipboard or drive redirection for the
files. Leave this session connected while cascades render.

### Verifying the copy

`SHA256SUMS.txt` in this folder lists the expected hashes. On the instance:

```powershell
Get-FileHash C:\BrainPanel\CleanEEGProject\files\Montage_6.py -Algorithm SHA256 | Format-List
```

Compare against the matching line. Do this before running anything — a
half-written file fails in confusing ways much later.

### Running the checks

numpy version, and the panel re-run, are both fine over Run Command:

```bash
aws ssm send-command --instance-ids i-0123456789abcdef0 \
  --document-name AWS-RunPowerShellScript \
  --parameters 'commands=["cd C:\\BrainPanel\\CleanEEGProject; py -c \"import numpy,sklearn; print(numpy.__version__, sklearn.__version__)\""]' \
  --query "Command.CommandId" --output text
```

Retrieve output with the returned id:

```bash
aws ssm get-command-invocation --command-id <id> --instance-id i-0123456789abcdef0 --query "StandardOutputContent" --output text
```

`get-command-invocation` truncates at roughly 24,000 characters. The pipeline is
extremely chatty, so send its stdout to a file on the instance and `Get-Content`
only the tail, or add `--output-s3-bucket-name` to the `send-command`.

Then the acceptance check (also fine headless — it only reads two PDFs):

```powershell
py verify_panel.py "<old>.icale.rep.pdf" "<new>.icale.rep.pdf"
```

The cascade check does not belong here. Do it in the RDP session from Option C,
and confirm the pages show component views rather than black.

### The watchdog stays in the console session

Do not start `tomwatchdog_serialized.py` over Run Command — it would inherit
session 0 and every cascade it renders would be black. Start it the way the
watchdog is started today: inside the console session that is kept logged into
production from the development server. SSM is for the file copy, the numpy
check, checksums and the panel comparison; the watchdog and anything that
renders a cascade belong in that console.

Practically this means SSM saves you the file transfer but not the trip into
RDP, so it is worth setting up only if you would rather script the copy than
drag it through a redirected drive.

---

## Not included

Deliberately left out; mentioning them so the decision is on the record.

- **Page-3 peak-frequency legend rework** from the dev copy of
  `create_report_pdf.py`. A visual improvement, unrelated to either request, so
  the panel keeps its current production appearance.
- **PLTS and discriminant report modes.** The dev
  `edftotextbynameplotproc.py` imports `create_report_pdf_discriminant` at
  module scope; shipping that file whole would require porting
  `files/create_report_pdf_discriminant.py` and `process/discriminant.py` too.
  This is exactly why the Global STD fix ships as a single hunk against the
  production file rather than as a whole-file copy.
