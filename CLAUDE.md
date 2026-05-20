# CLAUDE.md — Project guide for Claude Code

This is `clean_eeg_project 2025`, an EEG analysis pipeline that generates
the **BrainML (Machine Learning) Brain Panel Report** PDF. Owned by
Stress Therapy Solutions / BrainMaster Technologies.

## What it does

Reads a 19/20-channel EDF file, runs Butterworth band-power filtering and
ICA decomposition (montage 6, "ICALE"), computes 48 EEG quality metrics,
compares each against a reference database (`EC_191.out_file.icale.xlsx`,
192-file population), and generates a 3-page PDF report:

- **Page 1** — metrics table with color-coded bars and z-scores
- **Page 2** — plain-English findings summary
- **Page 3** — clinical paragraph + raw EEG waveforms + FFT power spectrum
  with per-channel peak-frequency legend and alpha-peak rails

## Entry points

| Command | Mode |
|---|---|
| `py module61.py` (via `run.bat`) | Directory + GUI mode. Production uses this. |
| `py module7.py "<path-to-edf>"` | Single-file unattended mode. Hardcoded `selstring[6]=1`, `selstring[8]=1`. Used by `tomwatchdog.py`. |
| `py tomwatchdog.py` | File-watcher daemon. Monitors `c:/inetpub/wwwroot/EEGScreening/Source/Practitioners` (hardcoded), spawns `module7.py` for each new EDF. |
| `py test_imagecascade.py "<path-to-edf>"` | One-off helper that mirrors module7 but also enables the IMG cascade output (`selstring[12]=1`). See "IMG cascade output mode" below. |
| `py test_plts.py "<path-to-edf>"` | One-off helper that mirrors module7 but also enables the PLTS multi-page artifact-traces output (`selstring[7]=1`). See "PLTS output mode" below. |

Output PDF lands next to the source EDF as `<name>.icale.rep.pdf`.

## Running tests

```
py -m pytest -v
```

7 tests in `tests/unit/` — smoke tests + tfcfilter sanity checks. ~1s runtime.

## Sample EDFs

`C:\BrainPanel\edf file samples\` holds 7 EDFs used for verification:
- `raw_130399.edf` through `raw_693371.edf` — small/medium recordings
- `STLE qEEG 03.001.01 AGE 10 EC.edf` — eyes-closed reference
- `STLE qEEG 04.001.01 AGE 10 EO.edf` — eyes-open
- Plus matching `.icale.rep.pdf` outputs from the production server
  (filename ends in `.rep1.pdf`) for visual reference

The Dropbox folder `c:/Users/tcollura/Dropbox/STS EEG Quality Assurance
Reviews/` holds additional reference PDFs from production (e.g.
`Dennis C 02.000.02 AGE 74 EC.icale.rep.pdf`).

## IMG cascade output mode

A secondary output, separate from the standard `.icale.rep.pdf` 3-page
report. Produces a multi-page PDF dedicated to ICA-component inspection:
overview heatmap + summary table + one component-pair per ICA component
(component-viewer page followed by source-localization brain-view page).

**How to enable:**

- GUI: tick the **IMG** checkbox in the `module61.py` selection dialog
  (corresponds to `selstring[12] = 1`).
- Headless: `py test_imagecascade.py "<path-to-edf>"` — mirrors the
  `module7.py` setup but adds `selstring[12] = 1`.

**Output:** `<edfname>.imagecascade.pdf` next to the source EDF. The
overview PNG `<edfname>.ica.png` is also left behind as a side artifact.

**Page layout** (sorted by component % descending — largest contributor
first; the original FastICA component number is preserved in every label
so cross-reference back to the overview is unambiguous):

1. Overview — ICA mixing-matrix heatmap (left) + stacked component traces
   (right). Red X markers flag machine-detected artifact components.
2. Summary table — Comp #, %, Max Site, RSI, Machine, User, Lobe, Region,
   Brodmann Area, FFT Peak. One row per component.
3..end — for each component, a component-viewer page (waveforms, FFT,
   ribbon, cepstrum, etc.) followed by a brain source-localization page.

**Production divergence:** the IMG cascade in dev works and is sorted by
component %. **Production is still on the December-2024 broken state**:
the `fig.savefig(icaeditfilename, ...)` call in `files/Montage_6.py` was
commented out during the Dec-2024 server-operation edits, so attempting
IMG mode on production raises `FileNotFoundError: ... .ica.png`. To
enable on production, port the dev changes that landed in this commit.

**Known limitation — windows flash on screen:** during cascade rendering
a fullscreen Tk window flashes briefly for each component (~19 flashes
per EDF on a 19-channel recording). This is because `save_gui_screenshot`
(`files/create_report_pdf.py`) uses `ImageGrab.grab(bbox=...)` which only
captures visible screen pixels. Attempted headless capture via Win32
`PrintWindow` + off-screen positioning was reverted: PrintWindow captures
Tk-native widgets correctly but misses the bitmap blits matplotlib makes
into its own `tk.PhotoImage`, leaving the per-component pages mostly
blank. A composite approach (PrintWindow for Tk widgets + per-figure
Agg-render-and-paste) is feasible but was not pursued.

## PLTS output mode

A secondary output, separate from the standard `.icale.rep.pdf` 3-page
report. Produces a multi-page PDF that walks through the recording in
fixed-length time windows (`length` samples per page, default 2560 =
10 s), showing for each window:

- 19 EEG waveforms across the top, one per channel
- Per-channel power square, 13-band power bars, and entropy bar to the
  right of each waveform
- A multi-channel ribbon visualization
- An `Art:` wax/wane fill for total artifact density across channels
- 13 per-band wax/wane fills (LoD, D, T, A1, A, A2, LoB, B, HiB, G,
  HiG, 60Hz) with comodulation ellipses to their right
- An FFT power spectrum panel with per-channel peak-frequency labels
  (Alpha1, Alpha, Alpha2)

A 10-minute recording produces ~60 pages.

**How to enable:**

- GUI: tick the **PLTS** checkbox in the `module61.py` selection dialog
  (corresponds to `selstring[7] = 1`).
- Headless: `py test_plts.py "<path-to-edf>"` — mirrors the
  `module7.py` setup but adds `selstring[7] = 1`.

**Output:** `<edfname>.ica.plts.pdf` (note: `.ica.` not `.icale.` —
under montage 6, `Montage_6.py` internally calls `setup_electrode_names`
with montage=4 which yields the `.ica.plts.pdf` suffix; this is a
quirk, not a bug).

**Per-page autoscaling:** the original hand-tuned multipliers (`bar_mult=5`,
`bar_mult_powers=1.5`, `/100`, `/1000`, etc.) were calibrated for some
unknown reference and produced bars that overflowed their strips by
3-5× on high-artifact channels, and a black `Art:` wax/wane fill that
smeared upward into the EEG-waveform area. As of this commit, each
page pre-computes max values across all channels and bands, then scales
so the maximum fits within its allowed dimension. Relative magnitudes
between bands and channels are preserved.

**Peak-frequency column layout:** the FFT panel writes per-channel
labels and the Alpha1 / Alpha / Alpha2 peak values in stacked columns.
Originally the value columns sat 200 px to the right of the channel
label, which collided with wider labels like `ICA C19:`. Columns are
now 400+ px right with clear separation.

**Production parity:** the autoscale + column-layout changes are
display-only; numerical metrics are unchanged. The `draw_*` functions
in `plot/plot_svc.py` gained new optional scale parameters that
default to `1.0` (identity), so any other caller without the new args
gets unchanged output. Production has not been touched.

## Production reference

`C:\BrainPanel\CleanEEGProject - production\` is a separate snapshot of
this codebase as it runs on the production server. As of 2026-05-18 every
`.py` file in production is **byte-identical** to `d4f522c` (initial
commit baseline). All changes committed since then are display-only and
should preserve numerical output.

There's also `C:\BrainPanel\CleanEEGProject - development\` as a third
copy.

## Critical environment dependency: numpy 2.0 int32 vs int64

Production runs Python **3.12** with numpy <2.0. Dev runs Python **3.13**
with numpy 2.1.3.

**Why this matters:** `np.arange(0, n, 1)` in numpy <2.0 on Windows
defaults to **int32**. In numpy ≥ 2.0 it defaults to **int64**.

Inside `process/detect_artifact.py` functions `detect_drowsiness` (line
~783) and `detect_moments` (line ~796), the term `x_values**2` reaches
~2.5×10¹⁰ for a 10-min recording at 256 Hz. That **overflows int32 at
i=46341**. The EC_191 reference database was built from int32-overflow
values — its means and stds depend on the wrap-around arithmetic.

Both functions force `dtype=np.int32` explicitly with explanatory
comments. **Do not remove these pins** unless you also rebuild the
reference DB. Removing the pin gives "correct" arithmetic but produces
Moment 3 values 50-130× larger than the reference expects, making
z-scores meaningless on those rows.

## Other quirks worth knowing

- **`Global STD = 1000.00`** on every report is a known artifact: after
  ICA reconstruction at montage=6, the components are scaled by ×1000
  (`edftotextbynameplotproc.py:425`), so `np.std(myfilteredsigs[:])`
  always lands at ~1000. The reference DB's Global STD row was built
  from a different metric definition; the z-score (~2642) is meaningless.
- **`detect_band_with_rms`** in `process/detect_artifact.py` returns
  `artifact_mask = abs(abs_signal - threshold)` — a *float array of
  distances*, NOT a boolean mask. This is the input contract that ~15
  downstream functions depend on. Looks like a bug, isn't. Same for
  `rms_signal = sqrt(std(...))` on the line above — looks wrong but
  feeds visualization only and the downstream code is calibrated to it.
- **Many `numsamples`-shaped arrays use `for i in range(...)` then
  `np.arange(2560*(i-1), 2560*i)`** — this is potentially off-by-one when
  i=0 (gives `range(-2560, 0)`, wrapping to the tail of the array). Not
  yet investigated.
- **ICA random seed is not set**. Two runs of the same EDF on the same
  code can produce slightly different metric values because ICA
  initialization is stochastic.

## Architecture map

```
module7.py / module61.py        (entry points)
    │
    ├─ edftotextbycommandplotproc.py   (module7 mode)
    └─ edftotextbydirectoryplotproc.py (module61 GUI mode)
              │
              ▼
         edftotextbynameplotproc.py    (the workhorse — 1000 lines)
              │
              ├─ process/tfcfilters.py        (Butterworth filter bank, fs=256 hardcoded)
              ├─ process/detect_artifact.py   (40+ band detectors + ICA component screening)
              ├─ files/file_svc.py            (Excel report generation via openpyxl)
              ├─ plot/plot_svc.py             (matplotlib EEG waveform + FFT plotting)
              ├─ files/Montage_6.py           (ICA orchestration; calls dummy_gui/dummy_brain)
              │       ├─ files/Component_selector.py  (Tk component review)
              │       └─ process/Source_Localization.py  (PyVista 3D brain — used by montage 6)
              └─ files/create_report_pdf.py   (3-page PDF via reportlab + matplotlib PNG embeds)
```

## Files that should NOT be re-added to git

Stale duplicates from Dropbox sync conflicts and old manual backups,
removed in commit `8a9ca7b`. The `.gitignore` pattern `*conflicted copy*`
blocks Dropbox from re-introducing them. If you ever see one of these
appear, it's a sync mishap, not real code:

- `files/Montage_6 (Tom Collura's conflicted copy 2024-04-26).py`
- `files/edftotextbynameplotproc (Tom Collura's conflicted copy ...).py`
- `files/file_svc (Tom Collura's conflicted copy 2024-04-26).py`
- `process/detect_artifact (Tom Collura's conflicted copy ...).py`
- `files/create_report_pdf - Copy.py` / `... - Copy (2).py` / `... (3).py`

To recover content from one: `git show d4f522c:"<path>" > recovered.py`.

## Open issues (informational, not blocking)

- **Global STD always 1000** — see quirks above. Should be redefined or
  removed from the report. Needs paired reference-DB update.
- **PDR Burst Width sometimes NaN** — happened on `raw_136896` and
  `raw_277778`. Upstream root cause not traced; current code generally
  produces a real value once the artifact_mask contract is intact.
- **Off-by-one risk** in `range(0,n)` + `np.arange(2560*(i-1), 2560*i)`
  patterns across `detect_artifact.py` and `Montage_6.py`.
- **No ICA random seed** — stochastic metric variation across runs.
- **Hardcoded paths**: `tomwatchdog.py:54` watches `c:/inetpub/...`;
  `edftotextbycommandplotproc.py:38` uses `EC_191.out_file.icale.xlsx`.
  Anyone running on a different machine needs these to exist locally.

## Substituting a single file into production

When making a small fix to a single module:
1. Back up the production file first (e.g. `cp foo.py foo.py.bak`).
2. Confirm `diff` against the dev copy shows only your intended change.
3. Run one verification EDF through `module61.py` on production.
4. Page 1 metrics should be identical to the previous run on the same
   EDF (numerical regressions show up immediately).
5. Page 3 layout may differ — production uses older matplotlib which
   renders text positioning differently from dev's matplotlib.
