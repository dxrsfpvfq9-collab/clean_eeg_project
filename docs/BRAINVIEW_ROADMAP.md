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
| Theta/beta ratio tile | not computed | Add per-channel band power from the EDF to the batch (cheap) |
| Topographic z-maps | not available (EC_191 is per-file) | Per-channel band-power table in the batch → per-channel age norms → head maps |
| Network / connectivity view | Page 2 prototype (envelope coupling, DMN/SN/ECN templates) | Reference ranges; replace hand-placed nodes with the Yeo 7-network atlas; consider lagged phase synchrony |
| Longitudinal / drug-response tracking | `compare_studies.py prepost` | Auto-pair sessions by `client`; thresholds from test-retest (§2.4) |
| EC/EO reactivity | `compare_studies.py eceo` (validated on 147 pairs) | Age norms for attenuation from the database |
| Symptom questionnaires | scraping plan (`SCRAPING_PLAN.md`) | Join symptoms per client as outcome labels |
| Quality / artifact gating | Automatic (ICA + rejection) — ahead of BrainView, whose labeling makes the user pick clean EEG | Publish the artifact % per study as a quality grade |
| ERP / P300 | none (resting EDFs only) | Product decision: needs a stimulus task with event markers |

## 4. Order of work

1. Let the batch finish; check failures (`studies.status='error'`).
2. Per-channel band power + theta/beta into the batch; re-run with `--features-only`, which needs no new ICA. The EDF readout is fast.
3. Age/condition reference ranges for `study_features` + per-channel power.
4. Label join and the first "which features predict what" table.
5. Headline tiles (PAF, theta/beta, drowsiness, quality) on a report page.
