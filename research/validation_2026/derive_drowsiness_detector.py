"""Derive a working drowsiness detector formula from the n=98 validation
cohort z-scores.

Approach:
  1. Load the 93x48 z-score matrix (already produced by
     run_multivariate_exploration.py).
  2. Pull drowsiness labels by matching patient_key from the
     comparison_chart_new_data.xlsx.
  3. Build DIRECTION-AWARE OOB features: for each of the 48 metrics,
     create two binary indicators (z >= +2 = "high OOB", z <= -2 =
     "low OOB").  96 features total.
  4. Rank features by Cohen's d on the drowsiness label.
  5. Build a simple weighted-count formula using the top features
     with small integer weights (mirroring the paper's style).
  6. Evaluate via 5-fold cross-validation: AUC, sens/spec at the
     Youden cut, and confusion matrix.

Output:
  out/derive_drowsiness_detector.md
"""
import csv
import os
import re
import sys
from collections import Counter

import numpy as np
from openpyxl import load_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from panel_parser import NAME_STRINGS  # noqa: E402

OUT = os.path.join(HERE, "out")
ZMATRIX_CSV = os.path.join(OUT, "multivariate_zmatrix.csv")
COMPARISON_XLSX = os.path.join(OUT, "comparison_chart_new_data.xlsx")
STUDY_COHORT_CSV = os.path.join(OUT, "study_cohort.csv")

_NOT_DEMONSTRATED = re.compile(r"\bnot\b[^.]*?\bdemonstrated\b", re.IGNORECASE)


# --- Drowsiness label parser (same as moments_split_analysis.py) -------
def label_drowsiness(s):
    if s is None:
        return None
    t = str(s).strip().lower()
    if not t:
        return None
    if t in {"none", "no"}:
        return 0
    if _NOT_DEMONSTRATED.search(t):
        return 0
    if "demonstrated" in t or "noted" in t or "diminution" in t or "present" in t:
        return 1
    return None


# --- Load z-matrix from CSV --------------------------------------------
def load_zmatrix():
    """Return (Z [n,48], patient_keys [n])."""
    Z = []
    keys = []
    with open(ZMATRIX_CSV, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            keys.append(row[0])
            Z.append([float(v) if v else np.nan for v in row[1:]])
    return np.array(Z), keys


# --- Load drowsiness labels by matching client_id -> patient_key -------
def load_drowsiness_labels(patient_keys):
    """Pull drowsiness labels from comparison_chart_new_data.xlsx for the
    given patient_keys.  Returns list[int|None] aligned with patient_keys.
    """
    # Build client_id -> drowsiness mapping from the comparison chart.
    wb = load_workbook(COMPARISON_XLSX, data_only=True)
    ws = wb.active
    client_to_drow = {}
    for r in ws.iter_rows(min_row=4, values_only=True):
        if r[1] is None:
            continue
        client_id = str(r[1]).strip()
        # Column 15 is Drowsiness/Sleep on the new spreadsheet.
        drow_text = r[15] if len(r) > 15 else None
        client_to_drow[client_id] = label_drowsiness(drow_text)

    # Build patient_key -> client_id via study_cohort.csv
    pk_to_client = {}
    with open(STUDY_COHORT_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            client_file = row["ec_panel_file"].replace(".icale.rep.pdf", "").strip()
            pk_to_client[row["patient_key"]] = client_file

    # Resolve each patient_key
    labels = []
    matched = 0
    for pk in patient_keys:
        client = pk_to_client.get(pk)
        if client is None:
            labels.append(None)
            continue
        # Direct match
        if client in client_to_drow:
            labels.append(client_to_drow[client])
            matched += 1
            continue
        # Token-prefix match
        first_token = client.split()[0] if client else ""
        hit = None
        for cid, lab in client_to_drow.items():
            if (cid.startswith(first_token + " ") or
                    cid.startswith(first_token + "-") or
                    cid == first_token):
                hit = lab
                break
        labels.append(hit)
        if hit is not None:
            matched += 1
    return labels, matched


# --- Direction-aware OOB features --------------------------------------
def build_features(Z):
    """For each metric: high (z>=+2) and low (z<=-2) indicators."""
    high = (Z >= 2.0).astype(float)
    low  = (Z <= -2.0).astype(float)
    return high, low


# --- Cohen's d for binary outcome --------------------------------------
def cohens_d(x, y):
    """x: continuous values, y: binary label."""
    pos = y == 1
    neg = y == 0
    if pos.sum() < 3 or neg.sum() < 3:
        return float("nan")
    mp = x[pos].mean()
    mn = x[neg].mean()
    sp = (x[pos].var(ddof=1) * (pos.sum() - 1) +
          x[neg].var(ddof=1) * (neg.sum() - 1)) / (pos.sum() + neg.sum() - 2)
    sp = max(sp, 1e-12)
    return (mp - mn) / np.sqrt(sp)


# --- AUC via Mann-Whitney --------------------------------------------
def roc_auc(scores, y):
    mask = ~np.isnan(scores) & ~np.isnan(y)
    s, lab = scores[mask], y[mask].astype(int)
    if len(set(lab)) < 2:
        return float("nan")
    order = np.argsort(s, kind="stable")
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(s) + 1)
    # Average ties
    uniq, inv = np.unique(s, return_inverse=True)
    for ui in range(len(uniq)):
        m = inv == ui
        ranks[m] = ranks[m].mean()
    n_pos = int(np.sum(lab == 1))
    n_neg = int(np.sum(lab == 0))
    u = np.sum(ranks[lab == 1]) - n_pos * (n_pos + 1) / 2
    return u / (n_pos * n_neg)


# --- Youden-optimal cut ------------------------------------------------
def best_youden(scores, y):
    mask = ~np.isnan(scores) & ~np.isnan(y)
    s, lab = scores[mask], y[mask].astype(int)
    best = (-np.inf, None, None, None, None)
    for t in sorted(set(s.tolist())):
        pred = s >= t
        tp = int(np.sum(pred & (lab == 1)))
        fp = int(np.sum(pred & (lab == 0)))
        fn = int(np.sum(~pred & (lab == 1)))
        tn = int(np.sum(~pred & (lab == 0)))
        sens = tp / (tp + fn) if (tp + fn) else 0
        spec = tn / (tn + fp) if (tn + fp) else 0
        acc  = (tp + tn) / (tp + fp + fn + tn)
        j = sens + spec - 1
        if j > best[0]:
            best = (j, t, sens, spec, acc)
    return best


# --- K-fold CV ---------------------------------------------------------
def kfold_indices(n, k, seed=42):
    rng = np.random.default_rng(seed)
    idx = np.arange(n)
    rng.shuffle(idx)
    folds = np.array_split(idx, k)
    return folds


# --- Score a formula on the panel --------------------------------------
def score_formula(high, low, weights):
    """weights: list of (idx, side, w) where side in {'high','low'}."""
    n = high.shape[0]
    s = np.zeros(n)
    for idx, side, w in weights:
        feat = high[:, idx] if side == "high" else low[:, idx]
        s += w * feat
    return s


# ------- MAIN ----------------------------------------------------------
def main():
    print("Loading z-matrix...")
    Z, patient_keys = load_zmatrix()
    print(f"  Z: {Z.shape}")

    print("Loading drowsiness labels...")
    labels, matched = load_drowsiness_labels(patient_keys)
    y = np.array([np.nan if v is None else float(v) for v in labels])
    print(f"  matched {matched}/{len(patient_keys)} keys to comparison chart")
    print(f"  n+ = {int(np.sum(y == 1))},  n- = {int(np.sum(y == 0))},  "
          f"unlabelled = {int(np.sum(np.isnan(y)))}")

    # Restrict to labelled rows
    mask = ~np.isnan(y)
    Z_l = Z[mask]
    y_l = y[mask].astype(int)
    keys_l = [patient_keys[i] for i in range(len(patient_keys)) if mask[i]]
    n_l = len(y_l)
    print(f"  using {n_l} labelled rows for derivation")

    # Build direction-aware OOB features
    high, low = build_features(Z_l)

    # Rank each (metric, direction) by Cohen's d on drowsiness
    print("\nTop direction-aware features by Cohen's d (vs drowsiness):")
    feats = []
    for i in range(48):
        d_hi = cohens_d(high[:, i], y_l)
        d_lo = cohens_d(low[:, i], y_l)
        # high-OOB rate among positives - among negatives
        rate_hi_pos = high[y_l == 1, i].mean()
        rate_hi_neg = high[y_l == 0, i].mean()
        rate_lo_pos = low[y_l == 1, i].mean()
        rate_lo_neg = low[y_l == 0, i].mean()
        feats.append({
            "metric": NAME_STRINGS[i], "idx": i,
            "d_high": d_hi, "d_low": d_lo,
            "rate_hi_pos": rate_hi_pos, "rate_hi_neg": rate_hi_neg,
            "rate_lo_pos": rate_lo_pos, "rate_lo_neg": rate_lo_neg,
        })

    # Show top 12 by max(|d_high|, |d_low|) and only print direction-aware
    # features with positive selection (d > 0 means OOB enriches drowsy).
    feats_sorted = sorted(
        feats, key=lambda r: -max(
            abs(r["d_high"]) if not np.isnan(r["d_high"]) else 0,
            abs(r["d_low"])  if not np.isnan(r["d_low"])  else 0,
        ))

    out_lines = ["# Deriving a working drowsiness detector\n\n"]
    out_lines.append(
        "Source: 93-row z-score matrix from `out/multivariate_zmatrix.csv` "
        "(extracted from the 98-EDF validation cohort by "
        "`run_multivariate_exploration.py`).  Drowsiness labels parsed "
        "from `comparison_chart_new_data.xlsx`.\n\n")
    out_lines.append("---\n\n## Direction-aware feature ranking\n\n")
    out_lines.append(
        "For each of the 48 Brain Panel metrics, two binary indicators are "
        "built: **z ≥ +2** (high OOB) and **z ≤ −2** (low OOB).  The 96 "
        "resulting features are ranked by Cohen's d on the drowsiness label "
        "(n+ = {} drowsy, n- = {} not drowsy).  Positive d means the feature "
        "is **enriched in drowsy recordings**; negative d means it is "
        "enriched in non-drowsy.\n\n".format(
            int(np.sum(y_l == 1)), int(np.sum(y_l == 0))))
    out_lines.append("### Top 15 features that ENRICH drowsy recordings (positive selection)\n\n")
    out_lines.append("| Metric | Direction | Cohen's d | rate(drowsy) | rate(not-drowsy) |\n")
    out_lines.append("|---|---|---|---|---|\n")

    # Build sorted lists of positive-d (selects drowsy) and negative-d features
    pos_selectors = []  # (metric, side, d, rate_pos, rate_neg, idx)
    for r in feats:
        if not np.isnan(r["d_high"]) and r["d_high"] > 0 and r["rate_hi_pos"] > r["rate_hi_neg"]:
            pos_selectors.append((r["metric"], "high",
                                  r["d_high"], r["rate_hi_pos"],
                                  r["rate_hi_neg"], r["idx"]))
        if not np.isnan(r["d_low"]) and r["d_low"] > 0 and r["rate_lo_pos"] > r["rate_lo_neg"]:
            pos_selectors.append((r["metric"], "low",
                                  r["d_low"], r["rate_lo_pos"],
                                  r["rate_lo_neg"], r["idx"]))
    pos_selectors.sort(key=lambda r: -r[2])

    print()
    print(f"{'Metric':<22} {'Dir':<5} {'d':>6} {'rate(drowsy)':>14} {'rate(awake)':>14}")
    for metric, side, d, rp, rn, idx in pos_selectors[:15]:
        out_lines.append(f"| {metric} | z {'≥ +2' if side=='high' else '≤ −2'} | "
                         f"{d:+.2f} | {rp:.2f} ({int(rp*int(np.sum(y_l==1)))}/{int(np.sum(y_l==1))}) | "
                         f"{rn:.2f} ({int(rn*int(np.sum(y_l==0)))}/{int(np.sum(y_l==0))}) |\n")
        print(f"{metric:<22} {side:<5} {d:>+6.2f} {rp:>14.3f} {rn:>14.3f}")
    out_lines.append("\n")

    # Build candidate formulas using small integer weights on the top features.
    # We try a few hand-crafted simple formulas and report their AUCs.

    name_to_idx = {n: i for i, n in enumerate(NAME_STRINGS)}

    def f_lookup(name, side):
        return (name_to_idx[name], side)

    candidates = []

    # Candidate 1: top-5 high-OOB features with equal weights
    top5 = [(m, s, 1) for m, s, _d, _, _, _ in pos_selectors[:5]]
    candidates.append(("Top-5 simple (eq. weights)", top5))

    # Candidate 2: top-3 with weight 2, next 2 with weight 1
    top3 = [(m, s, 2) for m, s, _d, _, _, _ in pos_selectors[:3]]
    next2 = [(m, s, 1) for m, s, _d, _, _, _ in pos_selectors[3:5]]
    candidates.append(("Top-3 (w=2) + next-2 (w=1)", top3 + next2))

    # Candidate 3: only the top feature
    top1 = [(m, s, 1) for m, s, _d, _, _, _ in pos_selectors[:1]]
    candidates.append(("Top-1 only", top1))

    # Candidate 4: Diffuse-fast composite from multivariate analysis
    candidates.append(("Diffuse-fast composite", [
        ("PDR Sinusoidal", "high", 2),
        ("Diffuse Hibeta", "high", 2),
        ("Diffuse Beta",   "high", 1),
        ("Beta Moment 1",  "high", 1),
        ("Midline Beta",   "high", 1),
    ]))

    # Candidate 5: as 4 but penalize PDR Synchrony OOB (paper notes drowsy has low sync)
    candidates.append(("Diffuse-fast + PDR Sync penalty", [
        ("PDR Sinusoidal", "high", 2),
        ("Diffuse Hibeta", "high", 2),
        ("Diffuse Beta",   "high", 1),
        ("Beta Moment 1",  "high", 1),
        ("Midline Beta",   "high", 1),
        ("PDR Synchrony",  "high", -2),  # penalty
    ]))

    out_lines.append("---\n\n## Candidate formulas\n\n")
    out_lines.append(
        "Each formula is a weighted sum of direction-aware OOB indicators "
        "for selected metrics.  Evaluation is in-sample AUC + Youden-optimal "
        "operating point on the n={} labelled rows, plus 5-fold "
        "cross-validated AUC.\n\n".format(n_l))
    out_lines.append(
        "| Formula | Components | In-sample AUC | Youden sens/spec/acc | 5-fold CV AUC |\n")
    out_lines.append("|---|---|---|---|---|\n")

    print()
    print(f"{'Formula':<36} {'In-sample AUC':>13} {'Sens/Spec/Acc':>20} {'CV AUC':>9}")

    folds = kfold_indices(n_l, 5, seed=42)

    def cv_auc(weights_named):
        aucs = []
        for fold_test in folds:
            test_mask = np.zeros(n_l, dtype=bool)
            test_mask[fold_test] = True
            high_train = high[~test_mask]
            low_train  = low[~test_mask]
            high_test  = high[test_mask]
            low_test   = low[test_mask]
            y_test     = y_l[test_mask]
            weights_idx = [(name_to_idx[m], s, w) for m, s, w in weights_named]
            s_test = score_formula(high_test, low_test, weights_idx)
            aucs.append(roc_auc(s_test, y_test.astype(float)))
        return float(np.nanmean(aucs)), float(np.nanstd(aucs))

    for name, weights_named in candidates:
        weights_idx = [(name_to_idx[m], s, w) for m, s, w in weights_named]
        s = score_formula(high, low, weights_idx)
        auc = roc_auc(s, y_l.astype(float))
        _j, t, sens, spec, acc = best_youden(s, y_l.astype(float))
        cv_mean, cv_std = cv_auc(weights_named)
        cmp_str = ", ".join(
            f"{w:+d}·{m}({s})" for m, s, w in weights_named)
        print(f"{name:<36} {auc:>13.2f}  {sens*100:.0f}%/{spec*100:.0f}%/{acc*100:.0f}% (>={t:.0f})  "
              f"{cv_mean:.2f}±{cv_std:.2f}")
        out_lines.append(
            f"| {name} | {cmp_str} | **{auc:.2f}** | "
            f"{sens*100:.0f}% / {spec*100:.0f}% / {acc*100:.0f}% (cut ≥ {t:.0f}) | "
            f"{cv_mean:.2f} ± {cv_std:.2f} |\n")

    out_lines.append("\n---\n\n## Recommended formula\n\n")
    # Pick the best CV AUC candidate
    best_candidate = None
    best_cv = -np.inf
    for name, weights_named in candidates:
        cv_mean, _ = cv_auc(weights_named)
        if cv_mean > best_cv:
            best_cv = cv_mean
            best_candidate = (name, weights_named)

    cand_name, cand_weights = best_candidate
    out_lines.append(f"**Best by 5-fold CV: {cand_name}** (CV AUC ≈ {best_cv:.2f}).\n\n")
    out_lines.append("Formula:\n\n```\nDrowsiness_score = ")
    parts = []
    for m, s, w in cand_weights:
        side_str = "(z ≥ +2)" if s == "high" else "(z ≤ −2)"
        parts.append(f"{w:+d}·N[{m} {side_str}]")
    out_lines.append("\n               ".join(parts))
    out_lines.append("\n```\n\n")
    out_lines.append(
        f"Each term is a 0/1 indicator (= 1 if that metric's z-score is "
        f"out of bounds in the specified direction).  Score range: "
        f"{min(0, sum(w for _, _, w in cand_weights if w < 0))} to "
        f"{sum(w for _, _, w in cand_weights if w > 0)}.\n\n")
    weights_idx = [(name_to_idx[m], s, w) for m, s, w in cand_weights]
    s = score_formula(high, low, weights_idx)
    auc = roc_auc(s, y_l.astype(float))
    _j, t, sens, spec, acc = best_youden(s, y_l.astype(float))
    out_lines.append(
        f"In-sample performance: AUC {auc:.2f}, "
        f"Youden cut score ≥ {t:.0f} gives sens {sens*100:.0f}%, "
        f"spec {spec*100:.0f}%, acc {acc*100:.0f}%.\n\n")
    out_lines.append(
        f"5-fold CV AUC: {best_cv:.2f}.\n\n")

    out_lines.append("### Comparison with the published Drowsiness detector\n\n")
    # Published formula on direction-blind |z|>=2 OOB counts grouped
    # 3·State Shift + 2·PDR + 1·Diffuse
    GROUP_RANGES = {
        "std_global": list(range(0, 2)),
        "pdr":         list(range(2, 11)),
        "focal":       list(range(17, 29)),
        "diffuse":     list(range(29, 36)),
        "state_shift": list(range(36, 48)),
    }
    oob = (np.abs(Z_l) >= 2).astype(int)
    g_counts = {g: oob[:, idxs].sum(axis=1) for g, idxs in GROUP_RANGES.items()}
    pub_score = (3 * g_counts["state_shift"]
                 + 2 * g_counts["pdr"]
                 + 1 * g_counts["diffuse"])
    pub_auc = roc_auc(pub_score.astype(float), y_l.astype(float))
    out_lines.append(
        f"Published `3·State Shift + 2·PDR + 1·Diffuse`: "
        f"AUC **{pub_auc:.2f}** on the same labelled data.  "
        f"(For reference: AUC = 0.5 = chance, AUC < 0.5 = anti-predictive.)\n\n")

    out_lines.append("### Caveats\n\n")
    out_lines.append(
        "- Derivation cohort: n_l = {} labelled drowsiness rows from the "
        "n=98 validation cohort.  This is small for stable feature ranking; "
        "results should be re-checked on a third independent cohort before "
        "deployment.\n".format(n_l))
    out_lines.append(
        "- 5-fold CV AUC is the honest generalization estimate; the "
        "in-sample AUC will always be higher.\n")
    out_lines.append(
        "- Drowsiness labels are regex-extracted from the doctor's "
        "narrative.  A hand-adjudicated relabel of 15-20 borderline cases "
        "(especially 'may be demonstrated' and 'intermittently noted') "
        "could shift the feature ranking.\n")
    out_lines.append(
        "- Each candidate uses small integer weights for interpretability "
        "and to match the paper's style.  A logistic-regression fit with "
        "continuous weights could squeeze out a few more AUC points but "
        "would lose the simple 'how many of these N flags fired?' read.\n")

    out_path = os.path.join(OUT, "derive_drowsiness_detector.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(out_lines)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
