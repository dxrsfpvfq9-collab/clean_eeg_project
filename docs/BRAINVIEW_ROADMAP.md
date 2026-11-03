# Source database and the road to BrainView-class reports

_Started 2026-10-29._ How the QA-corpus source database is built, what it holds,
and how it gets us from "a report we can produce" to "a report we know how to
interpret", capability by capability against BrainView (Medeia, Inc.).

## 1. The database (`tools/source_batch.py`)

| | |
|---|---|
| Corpus | `Dropbox\STS EEG Quality Assurance Reviews`, 1,709 EDFs (no `.clean`/`.unclean`/`.reviewed`), **newest recording first** |
| Per study | copy EDF to `C:\BrainPanel\source_db\work` → `run_cascade.py` with `CLEANEEG_SIDECAR_ONLY=1` (one ICA pass, no windows, ~25 s) → sidecar kept in `npz\`, analysis loaded into `sources.db`, optional 2-page `pdf\<id>.sources.pdf` |
| Writes to Dropbox | **nothing** — the production panels there are only read |
| Runtime | ~12 h for the corpus; resumable (`ok` studies skipped), 15-min kill per file |
| Privacy | the store holds file paths (they carry names), so it lives outside the repo and Dropbox. Studies are keyed by `id` (hash of the relative path); `client` is a hash of the EDF patient field, so one client's sessions group without the name |

`CLEANEEG_SIDECAR_ONLY` reproduces the full on-screen cascade's sidecar exactly
(QA study F EC: every array identical, max |diff| 0). It is the **cascade**
decomposition — pre-ICA line filter on, as on the servers — not the panel's.

Tables (`sources.db`):

- `studies` — id, rel_path, folder, masked label, client, EC/EO, age, recording start, status/error, code version
- `components` — per ICA component: %, FFT peak and band, accept/line, max site, peak MNI + region + Brodmann area, node count, DMN/SN/ECN template scores
- `nodes` — secondary sLORETA peaks per component (option 1)
- `edges` — partial envelope coupling per band, every pair, with the study's surrogate threshold (option 2)
- `groups` — coupled groups per band with their network template match
- `study_features` — one row per study: artifact %, band shares, posterior alpha %, dominant posterior source Hz (PAF proxy), DMN/SN/ECN %, edge counts
- `chan_power` — per 10-20 site, straight from the EDF (no ICA): absolute and relative band power, theta/beta, alpha peak, 60 Hz share (`tools/edf_power.py`)
- `edf_features` — one row per study: theta/beta at Cz/Fz/mean, posterior alpha peak and relative alpha, frontal theta, F4/F3 alpha asymmetry, worst 60 Hz share
- `ref_models` / `ref_z` — age-by-condition reference models per feature and every study's z + age-adjusted percentile (`tools/reference_ranges.py`)
- `labels` / `report_pdr` — Doctor's-Report outcomes per study (+ alpha-anchored `pdr_slow`) and the reader's stated PDR Hz (`tools/label_join.py`)
- `panel` — the 48 values and z-scores of the study's existing production `.icale.rep.pdf`

```
py tools/source_batch.py --pdf            # run / resume the corpus
py tools/source_batch.py --list           # what would run, newest first
py tools/source_batch.py --features-only  # re-analyse stored sidecars after an analysis change
```

## 2. Learning to interpret: what the database is for

1. **Reference distributions by age and condition** for every source/network
   feature — the prerequisite for printing "high" or "low" beside any number on
   the source pages. The corpus is a screening population, not screened
   normals, so these are *reference* ranges, and the report must say so.
2. **Join the Doctor's Report labels** (`research/validation_2026/dr_report_parser.py`,
   `labels.py`; matched by `rel_path`) and test which features carry clinical
   signal — drowsiness, PDR frequency, paroxysmal. Base rates are low in the
   2026 set (0 % clinical abnormality, 4 % paroxysmal), so the older archive
   years matter.
3. **Panel ↔ source cross-reading.** Both live in one database per study, so
   "this out-of-range panel row usually comes with this source picture" can be
   measured rather than guessed.
4. **Test-retest.** `client` groups sessions; same-day EC/EO pairs and
   `.reviewed` re-runs bound how much a feature moves with no real change —
   needed before any pre/post claim.

## 3. BrainView capability map

| BrainView offers | We have | Next step |
|---|---|---|
| Age-regressed normative z-scores (ages 4–85) | Panel: EC_191 (not age-regressed); age models for the 48 rows already fitted (`EC_AGE`/`EO_AGE`, n=491, `age_regression.py`) | Wire the age models into a panel variant; fit the same models on `study_features` |
| eLORETA 3-D source maps | Cascade brain pages; one-page source summary | Reference ranges per region (§2.1) so a map can say "unusually strong for age" |
| Peak alpha frequency tile | EDF-based PAF (`compare_studies.eceo`), cascade dominant posterior source | Age norms for PAF from the database; headline tile |
| Theta/beta ratio tile | `edf_features.tbr_cz` / per site in `chan_power` | Age norms, headline tile |
| Topographic z-maps | per-site band power in `chan_power` | Per-site age norms → head maps |
| Network / connectivity view | Page 2 prototype (envelope coupling, DMN/SN/ECN templates) | Reference ranges; replace hand-placed nodes with the Yeo 7-network atlas; consider lagged phase synchrony |
| Longitudinal / drug-response tracking | `compare_studies.py prepost` | Auto-pair sessions by `client`; thresholds from test-retest (§2.4) |
| EC/EO reactivity | `compare_studies.py eceo` (validated on 147 pairs) | Age norms for attenuation from the database |
| Symptom questionnaires | scraping plan (`SCRAPING_PLAN.md`) | Join symptoms per client as outcome labels |
| Quality / artifact gating | Automatic (ICA + rejection) — ahead of BrainView, whose labeling makes the user pick clean EEG | Publish the artifact % per study as a quality grade |
| ERP / P300 | none (resting EDFs only) | Product decision: needs a stimulus task with event markers |

## 4. Order of work

1. Let the batch finish; check failures (`studies.status='error'`).
2. ~~Per-channel band power + theta/beta into the batch~~ — done (`--edf-power`, 2026-11-03).
3. ~~Age/condition reference ranges for `study_features` + per-channel power~~ — done (`tools/reference_ranges.py`, 2026-11-03; plots in `<store>/reference_ranges.pdf`).
4. ~~Label join and the first "which features predict what" table~~ — done (`tools/label_join.py`, 2026-11-03; `research/validation_2026/out/SOURCE_DB_LABEL_JOIN.md`). Headlines: EDF alpha peak tracks the reader's PDR (rho 0.60, median 0.45 Hz) and flags reader-confirmed PDR slowing (AUC 0.84 inverted); theta/beta and frontal theta are higher in clinically abnormal EC studies (AUC 0.65-0.68); drowsiness is weak (best |AUC-0.5| <= 0.09); paroxysmal has too few positives (10-12).
5. ~~Headline tiles on a report page~~ — prototype done (`tools/edf_report.py`, 2026-11-03): tiles for PAF, theta/beta, posterior alpha, frontal theta, asymmetry, fast activity and quality; per-site z head maps; findings; source pages appended from the sidecar. No drowsiness tile -- no feature tracked the reader's drowsiness call (label join).
