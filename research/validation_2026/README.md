# Brain Panel Validation Study 2026

Reconstructs and validates the discriminant study from Collura et al. (2026),
*"Using Machine Learning to Enhance the EEG Screening Review by Pre-Screening
the EEG"* (AIA62026679), against the full STS Quality-Assurance corpus
(~540 Brain Panel reports vs ~500 Doctor's Reports — roughly 5x the original
n=100).

## Goal

1. **Validate** the prior study: do the Brain Panel metrics still separate
   neurologist-labelled clinical outcomes on independent data?
2. **Verify the detection algorithms**: apply the six published weighted
   discriminant functions (`process/discriminant.py`, Table 4 of the paper)
   to the new data and compare sensitivity / specificity / accuracy against
   the published 89-95% / 79-91% / 78-91%.

## Design decisions (agreed with study owner)

- **Eyes-closed (EC) is the primary panel** for each patient. EO is indexed
  as a secondary sensitivity check but is not the main unit of analysis.
- **Label extraction is regex-first** (the Doctor's Reports use a fixed
  template), with an LLM fallback for non-template reports — Phase C.
- Panel features come from **parsing the saved `.icale.rep.pdf`**, not from
  re-running the pipeline. This matches exactly what the neurologist saw and
  avoids the un-seeded-ICA nondeterminism noted in `CLAUDE.md`.

## Pipeline

| Phase | Script | Output |
|---|---|---|
| A. Corpus index + pairing | `run_phase_ab.py` | `out/panels_index.csv`, `out/reports_index.csv`, `out/manifest_ec.csv` |
| B. Panel feature extraction | `run_phase_ab.py` | `out/panel_features.csv`, `out/manifest_ec_features.csv`, `out/study_cohort.csv` |
| C. Doctor-report labelling | `report_parser.py` (+ `build_spreadsheet.py`) | template fields L-S |
| Comparison chart | `build_spreadsheet.py` | `out/comparison_chart_new_data.xlsx` |
| D. Validation + re-derivation | *(not yet built)* | tables, figures, writeup |

Run:

```
py research/validation_2026/run_phase_ab.py        # Phases A+B -> study_cohort.csv
py research/validation_2026/build_spreadsheet.py   # Phase C + comparison chart
```

## Comparison chart

`build_spreadsheet.py` reproduces the first study's master spreadsheet
(`04_Comparison Chart BP to DR ... 07AUG.xlsx`) with the new cohort, same
column layout A-S: client id; the 6 Brain Panel OOB group counts
(D Std/Global, E PDR, F Phenotype, G Focal, H Diffuse, I State Shift) with
C = `=SUM(D:I)` total; K the panel's own machine "Findings"; and L-S the
Doctor's Report template fields (quality / artifact / artifact-free /
background / drowsiness / paroxysmal / comments / full text). 98 rows.

## Privacy note

Source filenames embed patient first-name + last-initial and age. All CSVs
land in `out/`, which is **git-ignored**. Each row also carries an anonymized
`patient_key` (hash of the matched ID tokens) intended as the only join key
that should ever leave this folder. Do not commit `out/`.

## Files

- `config.py`        — corpus root, file patterns, output dir.
- `panel_parser.py`  — `.icale.rep.pdf` -> 48 z-scores -> OOB group counts.
- `corpus_index.py`  — walk the tree, classify files, parse metadata/ID tokens,
                       pair EC panels to Doctor's Reports within session scope.
- `run_phase_ab.py`  — orchestrates Phases A and B, writes the CSVs + a summary.
