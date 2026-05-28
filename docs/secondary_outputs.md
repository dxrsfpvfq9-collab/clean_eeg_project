# Secondary output modes

Practical guide to the three optional outputs that can be produced alongside
the standard `<edfname>.icale.rep.pdf` Brain Panel report:

| Mode | Output file | Headless runner | Selstring flag |
|---|---|---|---|
| **IMG cascade** | `<edfname>.imagecascade.pdf` | `py test_imagecascade.py "<path>"` | `selstring[12] = 1` |
| **PLTS** | `<edfname>.ica.plts.pdf` | `py test_plts.py "<path>"` | `selstring[7] = 1` |
| **Discriminant** | `<edfname>.icale.disc.rep.pdf` | `py test_discriminant.py "<path>"` | `selstring[13] = 1` |

All three are off by default — `module7.py` (the watchdog entry point) only
sets `selstring[6]=1` (ICA-LE montage) and `selstring[8]=1` (standard
report). The three test runners are headless one-off drivers that mirror
`module7.py` but add the relevant flag.

In the `module61.py` GUI flow, each mode has a checkbox in the file
selection dialog.

This document covers the **operational** side. For the design
discussion behind each, see:

- IMG cascade — `CLAUDE.md` § "IMG cascade output mode"
- PLTS — `CLAUDE.md` § "PLTS output mode"
- Discriminant — `docs/discriminant_report.md` (full design doc)

---

## When to use which

| If you want to... | Use |
|---|---|
| Generate the standard 3-page Brain Panel report only | (default — no flag, just `module7.py` or watchdog) |
| Inspect what the ICA decomposition found per component | **IMG cascade** |
| Walk through the recording window-by-window with all band traces | **PLTS** |
| Get the standard report PLUS the six Optimal Detection Algorithms | **Discriminant** |

The three modes are independent. Any combination of flags can be set;
the standard report still produces when `selstring[8] = 1`.

---

## IMG cascade

**Output:** `<edfname>.imagecascade.pdf`, plus `<edfname>.ica.png` as a
side artifact.

Multi-page PDF dedicated to ICA-component inspection. Pages, sorted by
component % descending:

1. **Overview** — ICA mixing-matrix heatmap (left) + stacked component
   traces (right). Red X markers flag machine-detected artifact components.
2. **Summary table** — one row per component: Comp #, %, Max Site, RSI,
   Machine, User, Lobe, Region, Brodmann Area, FFT Peak.
3. **Per-component pages** — component-viewer page (waveforms, FFT,
   ribbon, cepstrum, etc.) followed by a brain source-localization page,
   for each component.

The original FastICA component number is preserved in every label, so
sorting by % doesn't lose the cross-reference back to the overview.

**Production status:** the dev version works. Production is still on the
December-2024 broken state (the `fig.savefig(icaeditfilename, ...)` call
in `files/Montage_6.py` was commented out during Dec-2024 server-operation
edits, which leaves `<edfname>.ica.png` missing and crashes the cascade
with `FileNotFoundError`). To deploy: substitute `files/Montage_6.py`
from this repo into production. The fix is in commit `9470374`.

**Known limitation:** during rendering, a fullscreen Tk window flashes
briefly for each component (~19 flashes on a 19-channel recording).
This is because `save_gui_screenshot` uses `ImageGrab.grab(bbox=...)`
which only captures visible screen pixels. A headless-capture attempt
via Win32 `PrintWindow` was reverted because it missed matplotlib's
`tk.PhotoImage` bitmap blits. Composite approach feasible but not done.

---

## PLTS

**Output:** `<edfname>.ica.plts.pdf` (note: `.ica.` not `.icale.` — under
montage 6, `Montage_6.py` internally calls `setup_electrode_names` with
montage=4 which yields the `.ica.plts.pdf` suffix; quirk, not a bug).

Multi-page PDF that walks through the recording in fixed-length time
windows (default 2560 samples = 10 s, ~60 pages for a 10-minute
recording). Each page shows:

- 19 EEG waveforms across the top, one per channel
- Per-channel power square, 13-band power bars, and entropy bar to the
  right of each waveform
- Multi-channel ribbon visualization
- `Art:` wax/wane fill for total artifact density across channels
- 13 per-band wax/wane fills (LoD, D, T, A1, A, A2, LoB, B, HiB, G, HiG,
  60 Hz) with comodulation ellipses
- FFT power spectrum panel with per-channel peak-frequency labels
  (Alpha1, Alpha, Alpha2)

**Recent improvements** (commit `4129d77`):

- **Per-page autoscaling.** The original multipliers (`bar_mult=5`,
  `bar_mult_powers=1.5`, `/100`, `/1000`, etc.) were hand-tuned for an
  unknown reference and produced bars that overflowed their strips by
  3-5× on high-artifact channels, and a black `Art:` fill that smeared
  upward into the waveform area. Now each page pre-computes max values
  across all channels and bands, then scales so the max fits within its
  allowed dimension. Relative magnitudes between bands and channels are
  preserved.
- **Peak-frequency column layout.** Per-channel labels and the Alpha1/
  Alpha/Alpha2 peak values now use 400+ px column gaps (was 200 px),
  preventing collisions with wide labels like `ICA C19:`.

**Production parity:** the autoscale + column-layout changes are
display-only. The `draw_*` functions in `plot/plot_svc.py` gained
optional scale parameters defaulting to `1.0`, so any other caller
without the new args gets unchanged output. Numerical metrics are
unaffected. Production has not been touched.

---

## Discriminant

**Output:** `<edfname>.icale.disc.rep.pdf` — a 3-page report with the
same layout as the standard `.icale.rep.pdf` plus a new
**Likelihood of Findings** block on the lower half of page 2.

Implements the six weighted-count Optimal Detection Algorithms from
Collura et al. (2026), Table 4 / Appendix B Figure B7:

- Clinical Abnormality (89% sens / 76% spec)
- Drowsiness (93% sens / 79% spec)
- Artifact (92% sens / 83% spec)
- Paroxysmal / Epileptiform (94% sens / 88% spec)
- PDR Frequency Abnormality (95% sens / 84% spec)
- EEG Quality Concern (94% sens / 88% spec)

Each category score is a weighted sum of out-of-bounds (|z| ≥ 2) row
counts across the five Brain Panel groups (Std/Global, PDR, Focal,
Diffuse, State Shift) plus the total OOB count. Risk bands are
proportionally scaled per category from the paper's Clinical Abnormality
bands (0-2 / 3-4 / 5-7 / 8+).

**Concurrency with standard report.** If `selstring[8] = 1` and
`selstring[13] = 1` are both set (which `test_discriminant.py` does for
side-by-side comparison), both reports are written. The standard
`.icale.rep.pdf` flow is unaffected by the new code path.

**Files added** by commit `78d99d8`:

- `process/discriminant.py` — pure-Python group index ranges, per-category
  weights, risk bands. No rendering deps.
- `files/create_report_pdf_discriminant.py` — sibling of
  `create_report_pdf.py`. Pages 1 and 3 are identical to the standard
  writer; page 2 has the new block. The two writers share
  `allocate_data_5x19` imported from the original.
- `test_discriminant.py` — headless runner.

**Full design doc:** `docs/discriminant_report.md` (600 lines, includes
weight tables, deployment notes, rollback procedure).

---

## Documented known bug

`CLAUDE.md` was updated (commit `160381e`) to document the **PDR FFT
Width** detector behavior:

`detect_pdr_freq_epoch` in `process/detect_artifact.py` looks for FFT
bins within an absolute `tolerance = 80` of the half-peak amplitude to
find FWHM crossings. For sharp eyes-closed alpha peaks (amplitudes
5000-10000), the spectrum transitions through `half_peak` between
adjacent bins without either landing within ±80 — `indexes` ends up
empty, both edge variables default to 0, and the function returns 0.
For flat eyes-open spectra, many bins across 0-65 Hz satisfy the
tolerance, so the detector picks edges far from the true peak and
returns unphysically wide values (9+ Hz).

The EC_191 reference DB was built from the same algorithm across 192
files, so the z-score is statistically valid against *that distribution*
but the underlying metric is not physically meaningful. Same family of
"input contract" oddity as `detect_band_with_rms`. Display-only;
`mymetricsa[index, 16]` has no downstream consumers.

---

## Quick reference

| Goal | Command |
|---|---|
| Standard 3-page report | `py module7.py "<path>"` |
| Watchdog daemon | `py tomwatchdog.py` |
| GUI directory mode | `run.bat` |
| Standard + ICA cascade | `py test_imagecascade.py "<path>"` |
| Standard + PLTS | `py test_plts.py "<path>"` |
| Standard + discriminant | `py test_discriminant.py "<path>"` |
| All tests | `py -m pytest -v` |

| Where to look | For what |
|---|---|
| `CLAUDE.md` | Architecture, gotchas, mode-specific design notes |
| `README.md` | Project overview, install, basic run commands |
| `docs/git_workflow.md` | Git/GitHub setup and day-to-day workflow |
| `docs/discriminant_report.md` | Discriminant deep design doc (weights, deployment) |
| `docs/secondary_outputs.md` | (this file — practical guide to all three modes) |

---

## Substituting one file into production (recap)

The procedure that's worked for every dev → production deploy so far:

1. Back up the production file: `copy foo.py foo.py.bak`
2. `diff` against the dev version — confirm only the intended changes
   appear
3. Substitute the file
4. Run one verification EDF through `module61.py` on production
5. Page 1 metrics should be identical to the previous run on the same
   EDF (numerical regressions surface immediately)
6. Page 3 layout may differ — production matplotlib renders text
   positioning differently from dev's
7. Rollback if needed: `move foo.py.bak foo.py`

This applies for any of the secondary-output deployments (IMG cascade,
PLTS, discriminant) just as it does for the standard-report fixes.
