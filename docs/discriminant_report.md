# Discriminant report mode — change summary and deployment notes

Written 2026-05-28.

This document records the addition of a new Brain Panel report variant
that includes the six **Optimal Detection Algorithms** ("discriminant
functions") from the forthcoming paper:

> Collura, T., Rosace, A., Turner, R., Ims, D., & Brubakee, B. (2026).
> Using machine learning to enhance the EEG screening review by
> pre-screening the EEG. *Artificial Intelligence and Applications*.
> Bon View Press. https://doi.org/10.47852/bonviewAIA62026679

It is intended to be self-contained: anyone (including a future Claude
session that doesn't have the original conversation) should be able to
read this doc and understand exactly what was added, how to deploy it,
how to verify it, and how to roll back if needed.

---

## What this change does

Adds a **new** 3-page report variant alongside the existing
`.icale.rep.pdf` output. The new report is byte-equivalent in layout
to the standard one on pages 1 and 3; page 2 gains a new
**Likelihood of Findings** block at the bottom that scores the EEG
against the six Optimal Detection Algorithms from Table 4 of the
paper.

Output filename: `<edfname>.icale.disc.rep.pdf` (the `.disc` segment
distinguishes it from `<edfname>.icale.rep.pdf`).

**The standard report is unaffected.** The new writer is gated behind
`selstring[13] = 1` and the GUI / `module7.py` / `module61.py` /
production flows never set this flag, so they continue producing the
standard report only.

---

## The six Optimal Detection Algorithms

From Table 4 of the paper (verified against
`6679 AIA Template 24APR2026.docx` in the author's Dropbox):

| Category | Std/Global | PDR | Focal | Diffuse | State Shift | Total | Sens | Spec | Acc |
|---|---|---|---|---|---|---|---|---|---|
| Clinical Abnormality | 0 | 3 | 2 | 2 | 1 | 0 | 89% | 76% | 78% |
| Drowsiness           | 0 | 2 | 0 | 1 | 3 | 0 | 93% | 79% | 87% |
| Artifact             | 3 | 0 | 0 | 2 | 0 | 1 | 92% | 83% | 88% |
| Paroxysmal           | 0 | 2 | 3 | 0 | 1 | 0 | 94% | 88% | 91% |
| PDR frequency        | 0 | 4 | 0 | 0 | 1 | 1 | 95% | 84% | 91% |
| EEG Quality          | 4 | 0 | 0 | 2 | 0 | 1 | 94% | 88% | 90% |

Each category score is:

```
score = w_std_global × N(Std/Global rows OOB)
      + w_pdr        × N(PDR rows OOB)
      + w_focal      × N(Focal rows OOB)
      + w_diffuse    × N(Diffuse rows OOB)
      + w_state_shift × N(State Shift rows OOB)
      + w_total      × N(Total OOB rows across all 48 metrics)
```

"OOB" = out-of-bounds = `|z| >= 2` (matches the `> 2` / `< -2`
thresholds used elsewhere in the report).

**Group → row mapping** (into the 48-row `name_strings` order in
`files/edftotextbynameplotproc.py:934`):

| Group | Row indices | Brain Panel metrics |
|---|---|---|
| Std/Global  | 0–1   | STD Raw, Global STD |
| PDR         | 2–10  | PDR Symmetry … PDR Burst Width |
| Phenotypes  | 11–16 | Beta Max Front … Midline Beta *(counted only in Total — Table 4 assigns no per-group weight)* |
| Focal       | 17–28 | Focal Delta Index … Front Gamma Asym |
| Diffuse     | 29–35 | Diffuse Delta … Fractal Dimension |
| State Shift | 36–47 | PDR Moment 1 … Delta Moment 3 |

**Risk bands** come from Appendix Figure B7 of the paper, which gives
0-2 / 3-4 / 5-7 / 8+ as the Very Low / Low / Moderate / High bands for
the **Clinical Abnormality** detector. Those boundaries (2, 4, 7) are
**proportionally scaled per category** by `cat_max_score /
clinical_abnormality_max_score` so each detector's bands span the
same fraction-of-max range as Clinical Abnormality's. Boundaries are
floored to integers.

**Maximum possible score per category** (if every relevant row went OOB):

| Category | Calculation | Max | Scaling factor |
|---|---|---|---|
| Clinical Abnormality | 3·9 + 2·12 + 2·7 + 1·12 | 77 | 1.000 |
| Drowsiness | 2·9 + 1·7 + 3·12 | 61 | 0.792 |
| Artifact | 3·2 + 2·7 + 1·48 | 68 | 0.883 |
| Paroxysmal | 2·9 + 3·12 + 1·12 | 66 | 0.857 |
| PDR frequency | 4·9 + 1·12 + 1·48 | 96 | 1.247 |
| EEG Quality | 4·2 + 2·7 + 1·48 | 70 | 0.909 |

**Resulting per-category bands:**

| Category | Very Low | Low | Moderate | High |
|---|---|---|---|---|
| Clinical Abnormality | 0–2 | 3–4 | 5–7 | 8+ |
| Drowsiness | 0–1 | 2–3 | 4–5 | 6+ |
| Artifact | 0–1 | 2–3 | 4–6 | 7+ |
| Paroxysmal | 0–1 | 2–3 | 4–6 | 7+ |
| PDR frequency | 0–2 | 3–4 | 5–8 | 9+ |
| EEG Quality | 0–1 | 2–3 | 4–6 | 7+ |

Display colors are uniform across categories: dark green = Very Low,
olive = Low, orange = Moderate, red = High.

---

## New files

Three new files in this repo. All are pure additions — no existing file
is replaced.

| File | Purpose | Lines |
|---|---|---|
| `process/discriminant.py` | Group index ranges, Table-4 weights, risk-band thresholds, score computation. Pure-Python; no rendering or matplotlib deps. | 129 |
| `files/create_report_pdf_discriminant.py` | Sibling of `files/create_report_pdf.py`. Pages 1 and 3 use identical layout; page 2 adds the Likelihood-of-Findings block + APA citation. | 678 |
| `test_discriminant.py` | Headless test runner mirroring `test_imagecascade.py` / `test_plts.py`. Sets `selstring[13]=1` and runs the standard pipeline. | 67 |

`files/create_report_pdf_discriminant.py` imports `allocate_data_5x19`
from `files/create_report_pdf.py` so the two writers share the only
non-trivial helper. The high/low Findings sentence lists are
duplicated verbatim into the new file — duplication was preferred over
extracting them, to keep the original writer's behavior frozen.

---

## Modified files

Two existing files in this repo received small edits.

### `files/edftotextbynameplotproc.py`

+3 lines, 0 removed.

```python
# Near the top, alongside the existing create_report_pdf import:
from files.create_report_pdf_discriminant import create_report_pdf_discriminant

# Near the bottom, right after the selstring[8] block:
if len(selstring) > 13 and selstring[13] == 1:
    create_report_pdf_discriminant(
        outputdir1, short_name, channel_labels_short, name_strings,
        range_strings, report_strings, mymetrics, montage, excel_file_path,
        n, numpages, myvisualsigs, channel_labels_pre)
```

The `len(selstring) > 13` guard means older callers that pass a
shorter `selstring` array still work unchanged. All current callers
(`module7.py`, `module61.py`, `edftotextbycommandplotproc.py`,
`edftotextbydirectoryplotproc.py`, `test_imagecascade.py`, `test_plts.py`)
allocate `selstring = np.zeros(16)`, so the guard is informational —
none of them ever set `selstring[13]`.

### `CLAUDE.md`

+47 lines, 0 removed.

- One row added to the "Entry points" table pointing at
  `test_discriminant.py`.
- New "## Discriminant report mode" section documenting how to enable
  the mode and the output filename pattern.

---

## How to enable the new report

### Headless (one-shot, for testing)

```
py test_discriminant.py "C:\BrainPanel\edf file samples\raw_130399.edf"
```

This runs the standard pipeline with `selstring[8]=1` *and*
`selstring[13]=1`, producing both `<edf>.icale.rep.pdf` and
`<edf>.icale.disc.rep.pdf` side-by-side for comparison.

### From a script

```python
import numpy as np
import files.edftotextbynameplotproc

selstring = np.zeros(16)
selstring[6]  = 1   # ICALE montage
selstring[8]  = 1   # standard report (optional but recommended)
selstring[13] = 1   # discriminant report -- the new flag

files.edftotextbynameplotproc.edf_to_text_by_name_plot_proc(
    dirtouse1, outputdir1, 1, 2560, 6,
    selstring, outname, database_name, excel_file_path,
)
```

### From the GUI (`module61.py`)

The GUI does not currently expose a checkbox for `selstring[13]`. If
you want it in the GUI, the change is small (add one entry to the
selection dialog in `module61.py` and the matching unpacker in
`files/edftotextbydirectoryplotproc.py`). This was intentionally not
done in this change to keep the production GUI surface unchanged.

---

## How to verify it locally

```
cd "C:\BrainPanel\clean_eeg_project 2025"
py -m pytest -v
```

Expected: 7 / 7 tests pass (~5 seconds). The discriminant change does
not add new tests; it relies on visual inspection of the rendered PDF.

Then run on a sample EDF:

```
py test_discriminant.py "C:\BrainPanel\edf file samples\raw_130399.edf"
```

Open `C:\BrainPanel\edf file samples\raw_130399.icale.disc.rep.pdf`
and confirm:

1. **Page 1** — looks identical to `raw_130399.icale.rep.pdf` (the
   standard report). All 48 metric rows, color bars, Z-score circles.
2. **Page 2** — disclaimers at the top, **Findings:** list (red/green
   sentences) in the middle, **Likelihood of Findings (Collura et
   al., 2026 — Optimal Detection Algorithms)** block at the bottom,
   followed by the APA citation in small grey text.
3. **Page 3** — looks identical to the standard report (background-
   rhythm paragraph + FFT plot + raw waveforms).

The discriminant block on page 2 should show:

- A horizontal divider line above the title.
- The "OOB row counts" line (Std/Global / PDR / Focal / Diffuse /
  State Shift / Phenotypes / Total).
- The "Risk bands: 0-2 Very Low | 3-4 Low | 5-7 Moderate | 8+ High"
  legend.
- A 7-row table with one line-spacing gap between the legend and the
  grey header row.
- The Likelihood column is color-coded by risk band.
- A two-part footnote: one explaining the score formula, the other
  giving the full APA citation with DOI.

---

## Expected cohort behavior (sanity check)

Run on the 7 sample EDFs in `C:\BrainPanel\edf file samples\`, the
discriminant scores should look approximately like this (verified
2026-05-28):

```
EDF                                    OOB (G/P/F/D/S/Ph/Tot)    Clin  Drow  Artf  Parx  PDRf  EEGQ
----------------------------------------------------------------------------------------------------
raw_130399                             1/1/7/5/8/2/24            35(H) 31(H) 37(H) 31(H) 36(H) 38(H)
raw_136896                             1/1/3/0/2/0/7             11(H)  8(H) 10(H) 13(H) 13(H) 11(H)
raw_277778                             1/0/7/4/8/1/21            30(H) 28(H) 32(H) 29(H) 29(H) 33(H)
raw_592938                             1/1/6/5/12/1/26           37(H) 43(H) 39(H) 32(H) 42(H) 40(H)
raw_693371                             1/2/6/5/12/1/27           40(H) 45(H) 40(H) 34(H) 47(H) 41(H)
STLE qEEG 03.001.01 AGE 10 EC          1/1/1/0/0/0/3              5(M)  2(L)  6(M)  5(M)  7(M)  7(H)
STLE qEEG 04.001.01 AGE 10 EO          1/0/0/0/0/0/1              0(V)  0(V)  4(M)  0(V)  1(V)  5(M)

V=Very Low  L=Low  M=Moderate  H=High
```

(Reflects proportional per-category bands as of 2026-05-28.)

If the OOB counts or scores differ on a server, that means upstream
metric values are different — most likely the numpy 2.0 / int32 issue
(see CLAUDE.md "Critical environment dependency"). ICA randomness can
also cause small per-run drift on the same EDF; that is expected.

---

## Deploying to the production server

The production server lives at `C:\BrainPanel\CleanEEGProject -
production\` and runs Python 3.12 with numpy < 2.0 (see CLAUDE.md).
As of the most recent production audit (2026-05-18) every `.py` file
there is byte-identical to commit `d4f522c`, so the deployment of
this change is straightforward.

### Files to copy from dev → production

| Source (dev) | Destination (production) | New / Modified |
|---|---|---|
| `process/discriminant.py` | `process/discriminant.py` | New |
| `files/create_report_pdf_discriminant.py` | `files/create_report_pdf_discriminant.py` | New |
| `test_discriminant.py` | `test_discriminant.py` *(optional)* | New |
| `files/edftotextbynameplotproc.py` | `files/edftotextbynameplotproc.py` | Modified |

`CLAUDE.md` is project documentation; copy it if you want, but it is
not required for the code to run.

`test_discriminant.py` at the project root is only needed if you want
to be able to invoke the discriminant report on a single file from the
command line. The pipeline itself does not depend on it.

### Step-by-step

Run these on the **production** server, with the dev folder reachable
(e.g. via a network share, USB drive, or git pull if production is
also a git checkout — currently it is not).

```
cd "C:\BrainPanel\CleanEEGProject - production"

REM 1. Back up the one file we are modifying
copy "files\edftotextbynameplotproc.py" "files\edftotextbynameplotproc.py.bak"

REM 2. Copy in the new files
copy "C:\path\to\dev\process\discriminant.py" "process\discriminant.py"
copy "C:\path\to\dev\files\create_report_pdf_discriminant.py" "files\create_report_pdf_discriminant.py"
copy "C:\path\to\dev\test_discriminant.py" "test_discriminant.py"

REM 3. Overwrite the modified file
copy "C:\path\to\dev\files\edftotextbynameplotproc.py" "files\edftotextbynameplotproc.py"
```

Then verify the diff is what you expect:

```
diff "files\edftotextbynameplotproc.py.bak" "files\edftotextbynameplotproc.py"
```

You should see exactly **three added lines** (the import near the top,
and the 2-line `if` block near the bottom). Nothing else should
change.

### Verification on production

```
py test_discriminant.py "C:\BrainPanel\edf file samples\STLE qEEG 03.001.01 AGE 10 EC.edf"
```

(or any sample EDF available on the production server). Expected:

1. The pipeline runs to completion with no `ModuleNotFoundError` or
   `ImportError`.
2. Both `<edf>.icale.rep.pdf` and `<edf>.icale.disc.rep.pdf` appear
   next to the EDF.
3. The standard `.icale.rep.pdf` is **byte-identical** (or
   metric-identical on page 1) to a previous run on the same EDF.
   This proves the modification to `edftotextbynameplotproc.py` did
   not perturb the standard flow.
4. The new `.icale.disc.rep.pdf` page 1 matches the standard page 1.
5. The new `.icale.disc.rep.pdf` page 2 has the Likelihood-of-Findings
   block at the bottom (see "How to verify it locally" above for the
   detailed checklist).

### Rollback

If anything looks wrong:

```
move "files\edftotextbynameplotproc.py.bak" "files\edftotextbynameplotproc.py"
del "process\discriminant.py"
del "files\create_report_pdf_discriminant.py"
del "test_discriminant.py"
```

That fully reverts production to the pre-change state. The standard
GUI flow does not import the new module, so even if you only restore
`edftotextbynameplotproc.py` and leave the new files in place,
nothing in the pipeline calls them and the standard report continues
to work.

---

## Files NOT touched

For the record, these files were intentionally **not** modified:

- `files/create_report_pdf.py` — the original report writer is frozen
- `module7.py`, `module61.py`, `tomwatchdog.py` — entry points are frozen
- `process/detect_artifact.py`, `process/tfcfilters.py` — metric
  computation is frozen
- `files/Montage_6.py`, `files/Component_selector.py`,
  `process/Source_Localization.py` — ICA / source-localization stack
  is frozen
- `files/file_svc.py` — Excel output is frozen
- `plot/plot_svc.py` — matplotlib plotting helpers are frozen
- All test code in `tests/unit/` — no new tests added, existing 7/7
  still pass
- The production reference at `C:\BrainPanel\CleanEEGProject -
  production\` — separate snapshot, not modified

---

## Design decisions worth knowing

A few choices that aren't obvious from reading the code:

### Why a sibling writer instead of modifying `create_report_pdf.py`

The original writer is 1100+ lines of intricate matplotlib + reportlab
code that has been carefully tuned against the production reference
PDFs. Modifying it in place would risk perturbing pages 1 and 3
through innocuous-looking edits (whitespace, font metrics,
matplotlib defaults). A sibling writer that re-implements the body
with the new block added is more verbose but lets the original
writer stay frozen.

The cost is duplicated code (the high/low Findings sentence lists,
the page 1 metrics-table build). The benefit is full insulation of
the production code path.

### Why `selstring[13]` and not a new function argument

`selstring` is the existing convention for toggling output modes in
this codebase (`selstring[7]` = PLTS, `selstring[8]` = standard
report, `selstring[12]` = IMG cascade). Adding `selstring[13]` for
the discriminant report is consistent. The `len(selstring) > 13`
guard means callers that pass shorter arrays still work — though as
noted, every current caller uses `np.zeros(16)`.

### Why Phenotypes (rows 11–16) get no per-group weight

Table 4 of the paper has columns for Std/Global, PDR, Focal,
Diffuse, State Shift, and Total — no Phenotypes column. The
Phenotypes rows still contribute to the Total OOB count, so they
participate in any category whose formula has a non-zero Total
weight (Artifact, PDR frequency, EEG Quality). They have no
independent weight in any category.

### Why findings are auto-shrunk

On a heavily abnormal EDF (e.g. `raw_130399` with 24/48 OOB rows),
the Findings list at the default 8pt/15pt spacing would extend past
the area reserved for the discriminant block. Rather than truncate
silently, the writer now picks a smaller font/spacing when needed
(8/15 → 8/12 → 7/10 → 7/9) and only truncates with a visible
"... plus N additional finding(s)" note as a last resort. The
discriminant block itself is anchored at a fixed vertical position
so its layout doesn't depend on how many findings there are.

### Why risk bands are proportionally scaled per category

Each Optimal Detection Algorithm has a different maximum possible
score (77 for Clinical Abnormality, 96 for PDR frequency, 61 for
Drowsiness, etc.). Applying the same numeric bands `0-2 / 3-4 / 5-7
/ 8+` uniformly to all six categories was the initial implementation
but understated the risk on lower-max categories — for example, a
score of 5 on Drowsiness (max 61) signals more concern than a score
of 5 on PDR frequency (max 96), but uniform bands would treat them
identically. The current implementation scales each category's
boundaries by `cat_max / 77`, floored to integers. This preserves
the paper's risk-stratification semantics across all six detectors.
The Bands column in the table makes the per-category boundaries
visible so the reader can see exactly where a given score falls.

### Why the journal name uses the full "Artificial Intelligence and Applications"

The paper's journal is "Artificial Intelligence and Applications"
(Bon View Press), DOI prefix `10.47852/bonview`. An earlier
iteration of this code used the shortened "Artificial Intelligence
Applications" but was corrected to match the journal's actual
title.

### Why the DOI link is included even though it doesn't resolve yet

The paper was "in press" as of 2026-05-28 when this work was done.
The DOI will resolve once the paper is published online. Including
the DOI now means the citation will be functional retroactively for
any report PDF generated before the paper goes live.

---

## Known limitations / open questions

- **GUI doesn't expose the flag.** `selstring[13]` can only be set
  from a script. If you want a GUI checkbox, add one to the dialog in
  `module61.py` and the unpacker in `files/edftotextbydirectoryplotproc.py`.
- **Phenotypes group mapping is an interpretation.** The paper does
  not explicitly say which Brain Panel rows fall under "Phenotypes"
  (because Table 4 doesn't reference them). The mapping in
  `process/discriminant.py` (rows 11–16) was inferred from the
  page-1 layout group labels in `create_report_pdf.py`. If the
  paper's authors clarify a different mapping, only the index range
  in `GROUP_INDEXES` needs to change.
- **Risk bands are proportionally scaled from the Clinical
  Abnormality bands.** Appendix Figure B7 gives the 0-2 / 3-4 / 5-7 /
  8+ bands for the Clinical Abnormality detector only. The
  implementation scales those three boundary points (2, 4, 7) by
  `cat_max_score / 77` per category, floored to integers, so each
  detector's bands span the same fraction-of-max range. If the paper
  publishes per-category band calibrations later, the
  `_category_bands` function in `process/discriminant.py` is the one
  place to update.
- **No new automated tests.** The 7 unit tests in `tests/unit/` still
  pass but they don't exercise the discriminant module. Visual
  inspection of the PDF on the 7 sample EDFs is the verification
  strategy.

---

## Where to look if something breaks

- **`ImportError: No module named 'process.discriminant'`** —
  `process/discriminant.py` is missing on the target machine. Copy it
  over.
- **`ImportError: cannot import name 'create_report_pdf_discriminant'`** —
  `files/create_report_pdf_discriminant.py` is missing. Copy it over.
- **The new report renders but page 2 has overlap or off-page text** —
  Find the `_draw_discriminant_block` function in
  `files/create_report_pdf_discriminant.py` (~line 573). The
  coordinates `table_y_top = 278`, divider at `y=345`, etc., are all
  defined there.
- **Scores all show 0** — `compute_oob_counts` in
  `process/discriminant.py` is probably receiving an array of zeros.
  Check that the calling site (`_draw_discriminant_block` in
  `files/create_report_pdf_discriminant.py`) is passing in
  `z_scores_all` correctly, and that the per-row z-score computation
  inside the page-1 loop is appending to it.
- **Scores don't match expected** — verify the OOB row counts on the
  page-2 "OOB row counts:" line. If those counts match expectations,
  the discriminant math is by-the-paper. If the counts disagree with
  the page-1 table, the metric z-scores themselves are different
  (almost certainly an upstream issue — numpy 2.0 int32, ICA seed
  drift, or a montage / channel-ordering mismatch).
- **DOI link doesn't work** — expected for now; the paper is in
  press. Will resolve once published.

---

## Resuming this work in a future session

If you (or a future Claude session) want to pick this up later:

1. **Read this document first.** It is self-contained.
2. **Read `CLAUDE.md` "## Discriminant report mode" section.** Same
   info in a condensed form.
3. **Look at the three new files:**
   - `process/discriminant.py` (small, ~130 lines, easy to read)
   - `files/create_report_pdf_discriminant.py` (long, ~680 lines —
     mostly a copy of the original writer with the new block in
     `_draw_discriminant_block` at the bottom)
   - `test_discriminant.py` (small, ~70 lines)
4. **Run** `py test_discriminant.py "<any sample EDF>"` and open the
   resulting `.icale.disc.rep.pdf` to see the current state.
5. **The git history is unrelated** — none of this has been committed
   yet (as of 2026-05-28). If you want a clean checkpoint:
   `git add docs/discriminant_report.md process/discriminant.py
   files/create_report_pdf_discriminant.py test_discriminant.py
   files/edftotextbynameplotproc.py CLAUDE.md && git commit`.

---

## Quick reference card

```
ENABLE FLAG:        selstring[13] = 1
HEADLESS RUNNER:    py test_discriminant.py "<path-to-edf>"
OUTPUT FILE:        <edfname>.icale.disc.rep.pdf
NEW FILES:          process/discriminant.py
                    files/create_report_pdf_discriminant.py
                    test_discriminant.py
MODIFIED FILES:     files/edftotextbynameplotproc.py  (+3 lines)
                    CLAUDE.md                          (+47 lines, docs only)
PAPER:              Collura et al. (2026), AIA, doi.org/10.47852/bonviewAIA62026679
SAMPLE COHORT:      7 EDFs in C:\BrainPanel\edf file samples\
TEST SUITE:         py -m pytest -v   (7/7 passing)
```
