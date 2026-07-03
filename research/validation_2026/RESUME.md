# Resume point — 2026-06-12

## Where we are

Validating Collura et al. 2026 discriminants on new data, and fixing the
Global STD metric bug found along the way.

### DONE
- Phases A-D built and run (see README + out/). Headline: the 6 published
  discriminants do NOT replicate out-of-sample (AUC 0.36-0.73); only EEG
  quality partially replicates (~0.73); drowsiness is inverted.
- Comparison spreadsheet matching the original study: `out/comparison_chart_new_data.xlsx`.
- New reference database from current files: `out/EC_NEW.out_file.icale.xlsx`
  (47/48 metrics stable vs EC_191; Global STD was the one broken row).
- **Global STD bug FIXED** in `files/edftotextbynameplotproc.py:364`
  (FastICA `whiten='arbitrary-variance'`, version-robust). Verified: Global
  STD 1000->~2.5, z 2642->sensible, exactly 0 of 47 other metrics change.
  File is CLEAN and DEPLOYABLE (diff = only the whiten fix). NOT yet deployed
  to production.
- **Corrected Global STD recomputed for all 98 cohort EDFs** ->
  `out/_gstd_new.tsv` (patient_key <tab> corrected Global STD; rows are in the
  same order as `out/study_cohort.csv` / `out/_cohort_edfs.txt`). Range
  1.65-7.58, median 2.52 (matches DB distribution).

## NEXT STEP (resume here): re-run Phase D with corrected Global STD

The only thing left for the recompute+re-validate task. Plan:
1. DB stats for Global STD z: EC_191.out_file.icale.xlsx row index 10
   (0-based) -> AVG~2.67, STD~0.38. (Verify exact values; the pipeline z =
   (value-AVG)/STD. Sanity: value 2.52 -> z -0.39.)
2. Write `run_phase_d_refixed.py`: for each cohort row (match by ROW ORDER to
   _gstd_new.tsv, NOT patient_key which may collide), parse the saved PDF's 48
   z-scores, REPLACE only index 1 (Global STD) z with the corrected z from
   _gstd_new.tsv, recompute OOB via process/discriminant.compute_oob_counts,
   re-run the published discriminants + AUC/sens/spec/acc vs ground truth
   (labels.py).
3. Compare to pre-fix Phase D (out/phase_d_results.md). The detectors that use
   std_global -- Artifact (3x) and EEG Quality (4x) -- are the ones that can
   change now that Global STD varies instead of being a constant always-OOB.
   All other metrics' z-scores are unchanged (verified 0/47), so only the
   std_global OOB count moves.

## Then (later, separate tasks)
- Deploy the fix to production (backup first; one verification EDF).
- Rebuild EC_NEW database now that Global STD computes correctly.
- Optional writeup; cohort expansion (EO/v2023) + label spot-check.

## Gotchas captured
- module7.py needs CWD = repo root (relative `import files...`).
- _cohort_edfs.txt has Windows CRLF; strip `\r` when reading paths in bash.
- Batch helper for Global STD only: temporarily add, before the
  `if montage == 6:` line, an env-guarded `print(np.std(myfilteredsigs)); exit`
  (it equals global_stdmeas; montage_6 doesn't modify myfilteredsigs). Remove
  after to keep the file deployable.
