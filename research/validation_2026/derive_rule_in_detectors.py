"""Derive high-specificity 'rule-in' detectors for each clinical outcome.

A rule-in detector is a single flag (or an OR of several flags) that
fires rarely in the negative class.  When it fires, the recording is
almost certainly positive for the outcome.

Approach:
  1. Load the 93x48 z-score matrix.
  2. Pull all five outcome labels from comparison_chart_new_data.xlsx.
  3. Build 96 direction-aware OOB features (z >= +2 and z <= -2 per metric).
  4. For each outcome, score each feature by its false-positive rate
     (rate among negatives).  Keep only features with FPR <= 5%.
  5. Among those, sort by positive rate so the most-firing ones come
     first.
  6. Build OR-rule: fire if any of the top-N features fires.  Report
     sens / spec / PPV / NPV at each rule depth (1 flag, 2 flags, ...).

Output: out/derive_rule_in_detectors.md
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


# ---- Label parsers ----------------------------------------------------
def label_drowsiness(s):
    if s is None: return None
    t = str(s).strip().lower()
    if not t: return None
    if t in {"none", "no"}: return 0
    if _NOT_DEMONSTRATED.search(t): return 0
    if any(w in t for w in ["demonstrated", "noted", "diminution", "present"]):
        return 1
    return None


def label_artifact_moderate(s):
    """1 if Moderate/Severe, 0 if Mild/Minimal."""
    if s is None: return None
    t = str(s).strip().lower()
    if not t: return None
    if any(w in t for w in ["severe", "marked", "moderate"]):
        return 1
    if any(w in t for w in ["mild", "minimal", "minor", "none"]):
        return 0
    return None


def label_quality_concern(s):
    """1 if Fair/Poor, 0 if Good/Excellent."""
    if s is None: return None
    t = str(s).strip().lower()
    if not t: return None
    if any(w in t for w in ["poor", "inadequate", "limited", "fair", "marginal"]):
        return 1
    if any(w in t for w in ["good", "excellent", "adequate"]):
        return 0
    return None


def label_abnormal(s):
    if s is None: return None
    t = str(s).strip().lower()
    if not t: return None
    for neg in ["no overt abnormal", "no abnormalities noted",
                "no abnormalities", "no abnormal", "no other overt",
                "no other abnormal"]:
        if neg in t: return 0
    for pos in ["epileptiform", "spike wave", "spike-wave",
                "sharp wave", "sharp/slowing", "interictal",
                "ictal", "encephalopathy", "abnormal",
                "slowing of background", "intermittent slowing",
                "isolated spike", "intermittent left"]:
        if pos in t: return 1
    return None


def label_paroxysmal(s):
    if s is None: return None
    t = str(s).strip().lower()
    if not t: return None
    if t in {"none", "none.", "no", "no."}: return 0
    if any(w in t for w in ["spike", "sharp", "epileptiform", "discharge",
                            "paroxysm", "burst"]):
        return 1
    return None


# ---- Loaders ----------------------------------------------------------
def load_zmatrix():
    Z, keys = [], []
    with open(ZMATRIX_CSV, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            keys.append(row[0])
            Z.append([float(v) if v else np.nan for v in row[1:]])
    return np.array(Z), keys


def load_labels(patient_keys):
    """Return dict[outcome -> list[int|None]] aligned with patient_keys."""
    wb = load_workbook(COMPARISON_XLSX, data_only=True)
    ws = wb.active
    # New-spreadsheet column indices: quality=11, artifact=12, drow=15,
    # paroxysmal=16, comments=17.
    client_to_labels = {}
    for r in ws.iter_rows(min_row=4, values_only=True):
        if r[1] is None: continue
        client_id = str(r[1]).strip()
        client_to_labels[client_id] = {
            "drowsiness":    label_drowsiness(r[15]),
            "artifact_mod":  label_artifact_moderate(r[12]),
            "quality_concern": label_quality_concern(r[11]),
            "abnormal":      label_abnormal(r[17]),
            "paroxysmal":    label_paroxysmal(r[16]),
        }
    pk_to_client = {}
    with open(STUDY_COHORT_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pk_to_client[row["patient_key"]] = (
                row["ec_panel_file"].replace(".icale.rep.pdf", "").strip()
            )
    out = {k: [] for k in ["drowsiness", "artifact_mod",
                            "quality_concern", "abnormal", "paroxysmal"]}
    for pk in patient_keys:
        client = pk_to_client.get(pk, "")
        rec = client_to_labels.get(client)
        if rec is None and client:
            first = client.split()[0]
            for cid, r2 in client_to_labels.items():
                if cid.startswith(first + " ") or cid.startswith(first + "-"):
                    rec = r2; break
        for k in out:
            out[k].append(None if rec is None else rec[k])
    return out


# ---- Feature engineering ----------------------------------------------
def build_features(Z):
    high = (Z >= 2.0).astype(int)
    low  = (Z <= -2.0).astype(int)
    return high, low


def feature_descriptors():
    """Yield (name, side, lambda(high, low) -> indicator)."""
    descs = []
    for i, name in enumerate(NAME_STRINGS):
        descs.append((name, "high", i, "high"))
        descs.append((name, "low",  i, "low"))
    return descs


def get_indicator(high, low, idx, side):
    return high[:, idx] if side == "high" else low[:, idx]


# ---- Metrics ----------------------------------------------------------
def conf_matrix(pred, y):
    pred = np.asarray(pred, dtype=bool)
    y = np.asarray(y, dtype=bool)
    tp = int(np.sum(pred & y))
    fp = int(np.sum(pred & ~y))
    fn = int(np.sum(~pred & y))
    tn = int(np.sum(~pred & ~y))
    return tp, fp, fn, tn


def metrics_from(tp, fp, fn, tn):
    sens = tp / (tp + fn) if (tp + fn) else float("nan")
    spec = tn / (tn + fp) if (tn + fp) else float("nan")
    ppv  = tp / (tp + fp) if (tp + fp) else float("nan")
    npv  = tn / (tn + fn) if (tn + fn) else float("nan")
    n = tp + fp + fn + tn
    acc  = (tp + tn) / n if n else float("nan")
    return sens, spec, ppv, npv, acc


# ---- Outcome-by-outcome analysis --------------------------------------
def analyze_outcome(outcome_name, y_full, high, low, max_fpr=0.05):
    """For one outcome, find high-spec features and report OR-rule
    performance at depth 1..K.  Returns a dict suitable for the report.
    """
    mask = np.array([v is not None for v in y_full])
    y = np.array([v for v in y_full if v is not None], dtype=int)
    high_m = high[mask]
    low_m  = low[mask]
    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))

    if n_pos < 3 or n_neg < 3:
        return {"outcome": outcome_name, "skipped": True,
                "n_pos": n_pos, "n_neg": n_neg}

    feats = []
    for name, side, idx, side_key in feature_descriptors():
        ind = get_indicator(high_m, low_m, idx, side_key)
        fp_rate = ind[y == 0].mean()
        tp_rate = ind[y == 1].mean()
        if fp_rate > max_fpr:
            continue
        if tp_rate == 0:
            continue
        # PPV at this single feature
        tp = int(np.sum(ind & (y == 1)))
        fp = int(np.sum(ind & (y == 0)))
        ppv = tp / (tp + fp) if (tp + fp) else float("nan")
        feats.append({
            "name": name, "side": side, "idx": idx, "side_key": side_key,
            "tp_rate": tp_rate, "fp_rate": fp_rate, "ppv": ppv,
            "tp": tp, "fp": fp,
        })
    feats.sort(key=lambda r: (-r["tp_rate"], r["fp_rate"]))

    # OR-rules at depth 1..min(K, len(feats))
    K = min(8, len(feats))
    rules = []
    cum = np.zeros(len(y), dtype=int)
    for k in range(K):
        f = feats[k]
        ind = get_indicator(high_m, low_m, f["idx"], f["side_key"])
        cum = (cum + ind).astype(int)
        pred = cum >= 1
        tp, fp, fn, tn = conf_matrix(pred, y == 1)
        sens, spec, ppv, npv, acc = metrics_from(tp, fp, fn, tn)
        rules.append({
            "depth": k + 1,
            "features": [{"name": ff["name"], "side": ff["side"]}
                          for ff in feats[:k + 1]],
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "sens": sens, "spec": spec, "ppv": ppv, "npv": npv, "acc": acc,
        })

    return {
        "outcome": outcome_name,
        "n_pos": n_pos, "n_neg": n_neg,
        "features": feats[:K],
        "rules": rules,
    }


# ---- Reporting --------------------------------------------------------
def write_report(results, path):
    lines = ["# High-specificity ('rule-in') detectors\n\n"]
    lines.append(
        "Source: 93-row z-score matrix from "
        "`out/multivariate_zmatrix.csv`.  Labels from "
        "`comparison_chart_new_data.xlsx`.\n\n")
    lines.append(
        "Each detector is built from direction-aware OOB indicators "
        "(`z ≥ +2` or `z ≤ −2`) on individual Brain Panel metrics.  The "
        "selection rule is **false-positive rate ≤ 5%** on the negative "
        "class.  Detectors are OR-rules: fire if ANY of the included "
        "flags is positive.\n\n")
    lines.append(
        "Interpretation: when one of these detectors fires, the **PPV "
        "is the chance the recording really has the outcome**.  These "
        "are *rule-in* tools — not screening (which needs high "
        "sensitivity).\n\n")
    lines.append("---\n\n")

    for r in results:
        outcome = r["outcome"]
        lines.append(f"## {outcome}\n\n")
        if r.get("skipped"):
            lines.append(
                f"Insufficient positive/negative class: "
                f"n+ = {r['n_pos']}, n- = {r['n_neg']}.  Skipped.\n\n")
            continue

        n_pos, n_neg = r["n_pos"], r["n_neg"]
        prev = n_pos / (n_pos + n_neg)
        lines.append(
            f"n+ = {n_pos}, n- = {n_neg}, prevalence = {prev*100:.0f}%.\n\n")

        lines.append("### High-specificity features (FPR ≤ 5%)\n\n")
        lines.append("| Metric | Direction | TP rate (pos) | FP rate (neg) | PPV at this flag alone |\n")
        lines.append("|---|---|---|---|---|\n")
        for f in r["features"]:
            side_str = "z ≥ +2" if f["side"] == "high" else "z ≤ −2"
            lines.append(
                f"| {f['name']} | {side_str} | "
                f"{f['tp_rate']:.2f} ({f['tp']}/{n_pos}) | "
                f"{f['fp_rate']:.2f} ({f['fp']}/{n_neg}) | "
                f"{f['ppv']*100:.0f}% |\n")
        if not r["features"]:
            lines.append("| (none) | | | | |\n")
        lines.append("\n")

        lines.append("### OR-rule performance by depth\n\n")
        lines.append("| Depth | Cumulative flag set | Sens | Spec | PPV | NPV | Acc | TP / FP / FN / TN |\n")
        lines.append("|---|---|---|---|---|---|---|---|\n")
        for rule in r["rules"]:
            flag_set = ", ".join(
                f"{ff['name']}({'+' if ff['side']=='high' else '-'})"
                for ff in rule["features"])
            lines.append(
                f"| {rule['depth']} | {flag_set} | "
                f"{rule['sens']*100:.0f}% | {rule['spec']*100:.0f}% | "
                f"{rule['ppv']*100:.0f}% | {rule['npv']*100:.0f}% | "
                f"{rule['acc']*100:.0f}% | "
                f"{rule['tp']} / {rule['fp']} / {rule['fn']} / "
                f"{rule['tn']} |\n")
        lines.append("\n---\n\n")

    lines.append("## How to use these\n\n")
    lines.append(
        "A high-PPV rule-in detector is reported alongside the rest of "
        "the panel as a confidence flag:\n\n")
    lines.append(
        "- **If the rule fires** → the outcome is very likely present.  "
        "Useful for tagging the recording at high confidence in the "
        "report, prioritizing neurologist review of recordings the "
        "machine is confident about, or as a positive-confirmation "
        "flag in the discriminant block of the report.\n")
    lines.append(
        "- **If the rule does NOT fire** → no information.  These "
        "detectors are designed not to fire on the negatives, but they "
        "also miss many true positives (sensitivity is intentionally "
        "low).  A negative result is *not* evidence of absence.\n\n")
    lines.append(
        "The trade-off is opposite to the published Table 4 detectors, "
        "which were optimized for sensitivity at the cost of "
        "specificity.  Both styles have a place: high-sens for "
        "screening, high-spec for confirming.\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    print("Loading z-matrix + labels...")
    Z, patient_keys = load_zmatrix()
    labels = load_labels(patient_keys)
    high, low = build_features(Z)

    print(f"Z: {Z.shape}, labels: {list(labels.keys())}")
    for k, v in labels.items():
        n_pos = sum(1 for x in v if x == 1)
        n_neg = sum(1 for x in v if x == 0)
        n_un  = sum(1 for x in v if x is None)
        print(f"  {k}: +{n_pos}  -{n_neg}  ?{n_un}")

    results = []
    for outcome_key, outcome_name in [
        ("drowsiness",      "Drowsiness"),
        ("artifact_mod",    "Artifact (Moderate/Severe)"),
        ("quality_concern", "EEG Quality concern (Fair/Poor)"),
        ("abnormal",        "Clinical abnormality"),
        ("paroxysmal",      "Paroxysmal disturbance"),
    ]:
        print(f"\nAnalyzing {outcome_name}...")
        r = analyze_outcome(outcome_name, labels[outcome_key],
                            high, low, max_fpr=0.05)
        results.append(r)
        if r.get("skipped"):
            print(f"  skipped (n+ = {r['n_pos']}, n- = {r['n_neg']})")
            continue
        print(f"  {len(r['features'])} features with FPR <= 5%; "
              f"best OR-rule: depth {r['rules'][-1]['depth']}, "
              f"sens {r['rules'][-1]['sens']*100:.0f}%, "
              f"spec {r['rules'][-1]['spec']*100:.0f}%, "
              f"PPV {r['rules'][-1]['ppv']*100:.0f}%")

    out_path = os.path.join(OUT, "derive_rule_in_detectors.md")
    write_report(results, out_path)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
