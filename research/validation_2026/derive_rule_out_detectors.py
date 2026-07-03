"""Derive high-sensitivity 'rule-out' detectors for each clinical outcome.

A rule-out detector is an OR of direction-aware OOB indicators chosen
to capture as many true positives as possible.  When the detector
*fails* to fire, the negative-predictive-value (NPV) tells you how
confident "no positive case here" is.

Approach:
  1. Load the 93x48 z-score matrix and all five clinical labels
     (same as derive_rule_in_detectors.py).
  2. Build direction-aware OOB indicators (z >= +2 and z <= -2).
     Also build "softer" indicators at z >= +1 and z <= -1 so we can
     catch more positives at lower confidence.
  3. For each outcome, greedy-OR the features that add the most NEW
     true-positive coverage at each step (regardless of FPR).
  4. Report sens / spec / PPV / NPV at each depth; identify the
     operating point where sens >= 90% (the "screening" sweet spot).
  5. Also report performance of group-OOB-COUNT rules ("predict
     positive if Total OOB >= K" etc.) as the closest analog to the
     paper's framework.

Output: out/derive_rule_out_detectors.md
"""
import csv
import os
import re
import sys

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

GROUP_RANGES = {
    "std_global":  list(range(0, 2)),
    "pdr":         list(range(2, 11)),
    "phenotypes":  list(range(11, 17)),
    "focal":       list(range(17, 29)),
    "diffuse":     list(range(29, 36)),
    "state_shift": list(range(36, 48)),
}


# ---- Label parsers (same as before) -----------------------------------
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
    if s is None: return None
    t = str(s).strip().lower()
    if not t: return None
    if any(w in t for w in ["severe", "marked", "moderate"]):
        return 1
    if any(w in t for w in ["mild", "minimal", "minor", "none"]):
        return 0
    return None


def label_quality_concern(s):
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


# ---- Loaders ---------------------------------------------------------
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
    wb = load_workbook(COMPARISON_XLSX, data_only=True)
    ws = wb.active
    client_to_labels = {}
    for r in ws.iter_rows(min_row=4, values_only=True):
        if r[1] is None: continue
        client_id = str(r[1]).strip()
        client_to_labels[client_id] = {
            "drowsiness":      label_drowsiness(r[15]),
            "artifact_mod":    label_artifact_moderate(r[12]),
            "quality_concern": label_quality_concern(r[11]),
            "abnormal":        label_abnormal(r[17]),
            "paroxysmal":      label_paroxysmal(r[16]),
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


# ---- Metric helpers --------------------------------------------------
def conf_matrix(pred, y):
    pred = np.asarray(pred, dtype=bool); y = np.asarray(y, dtype=bool)
    tp = int(np.sum(pred & y));   fp = int(np.sum(pred & ~y))
    fn = int(np.sum(~pred & y));  tn = int(np.sum(~pred & ~y))
    return tp, fp, fn, tn


def metrics_from(tp, fp, fn, tn):
    sens = tp / (tp + fn) if (tp + fn) else float("nan")
    spec = tn / (tn + fp) if (tn + fp) else float("nan")
    ppv  = tp / (tp + fp) if (tp + fp) else float("nan")
    npv  = tn / (tn + fn) if (tn + fn) else float("nan")
    n = tp + fp + fn + tn
    acc = (tp + tn) / n if n else float("nan")
    return sens, spec, ppv, npv, acc


# ---- Direction-aware features ----------------------------------------
def build_features(Z, thr=2.0):
    """Return (features [n, 2*48], names [2*48]) where each metric
    contributes a 'high' (z >= +thr) and 'low' (z <= -thr) indicator."""
    high = (Z >= thr).astype(int)
    low  = (Z <= -thr).astype(int)
    feats = []
    names = []
    for i, m in enumerate(NAME_STRINGS):
        feats.append(high[:, i]); names.append((m, "high"))
        feats.append(low[:, i]);  names.append((m, "low"))
    return np.array(feats).T, names


# ---- Greedy OR (maximizing sensitivity) ------------------------------
def greedy_or_for_sens(features, names, y, max_depth=10):
    """At each step pick the feature that adds the most NEW true positives.
    Return list of (depth, chosen_idx, name, tp, fp, fn, tn) after each pick.
    """
    n = len(y)
    chosen = np.zeros(n, dtype=int)
    picks = []
    used = set()
    for depth in range(1, max_depth + 1):
        best = (-1, None)
        for fi in range(features.shape[1]):
            if fi in used: continue
            new_pred = (chosen + features[:, fi]) >= 1
            tp = int(np.sum(new_pred & (y == 1)))
            # Score = newly-covered true positives, tiebreak by fewer new FPs.
            old_pred = chosen >= 1
            new_tp = int(np.sum(new_pred & (y == 1) & ~old_pred))
            new_fp = int(np.sum(new_pred & (y == 0) & ~old_pred))
            score = new_tp - 0.001 * new_fp
            if score > best[0]:
                best = (score, fi)
        if best[1] is None or best[0] <= 0:
            break
        fi = best[1]
        used.add(fi)
        chosen = (chosen + features[:, fi]).astype(int)
        pred = chosen >= 1
        tp, fp, fn, tn = conf_matrix(pred, y == 1)
        picks.append({
            "depth": depth, "idx": fi, "name": names[fi],
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        })
    return picks


# ---- Per-outcome analysis --------------------------------------------
def analyze_outcome(outcome_name, y_full, features, names):
    mask = np.array([v is not None for v in y_full])
    y = np.array([v for v in y_full if v is not None], dtype=int)
    feats = features[mask]
    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))
    if n_pos < 3 or n_neg < 3:
        return {"outcome": outcome_name, "skipped": True,
                "n_pos": n_pos, "n_neg": n_neg}

    # Single-feature ranking by TPR
    single = []
    for fi in range(feats.shape[1]):
        ind = feats[:, fi]
        tpr = ind[y == 1].mean()
        fpr = ind[y == 0].mean()
        tp = int(np.sum(ind & (y == 1)))
        fp = int(np.sum(ind & (y == 0)))
        sens = tp / n_pos if n_pos else 0
        spec = 1 - (fp / n_neg if n_neg else 0)
        if tpr <= 0:
            continue
        single.append({
            "name": names[fi], "idx": fi,
            "tpr": tpr, "fpr": fpr,
            "sens": sens, "spec": spec,
            "ppv": tp / (tp + fp) if (tp + fp) else float("nan"),
            "tp": tp, "fp": fp,
        })
    single.sort(key=lambda r: (-r["tpr"], r["fpr"]))

    # Greedy OR-rule
    picks = greedy_or_for_sens(feats, names, y, max_depth=10)
    rules = []
    for p in picks:
        sens, spec, ppv, npv, acc = metrics_from(p["tp"], p["fp"], p["fn"], p["tn"])
        rules.append({**p, "sens": sens, "spec": spec, "ppv": ppv, "npv": npv, "acc": acc})

    return {
        "outcome": outcome_name, "n_pos": n_pos, "n_neg": n_neg,
        "single": single[:10], "rules": rules,
    }


# ---- Group-OOB-count rules (paper-style) -----------------------------
def group_oob_rule_sweep(Z_l, y, thr=2.0):
    """For each group sum (Total OOB, PDR OOB, etc.), sweep threshold k and
    report the configuration that maximizes sens given spec >= 30%
    (a screening-sweet-spot heuristic).
    """
    high = (Z_l >= thr).astype(int)
    low  = (Z_l <= -thr).astype(int)
    oob = (high | low)
    rows = []
    for g, idxs in GROUP_RANGES.items():
        cnt = oob[:, idxs].sum(axis=1)
        for k in range(0, int(cnt.max()) + 1):
            pred = cnt >= k
            tp, fp, fn, tn = conf_matrix(pred, y == 1)
            sens, spec, ppv, npv, acc = metrics_from(tp, fp, fn, tn)
            rows.append({"group": g, "k": k, "sens": sens, "spec": spec,
                         "ppv": ppv, "npv": npv, "acc": acc,
                         "tp": tp, "fp": fp, "fn": fn, "tn": tn})
    # Also Total
    cnt = oob.sum(axis=1)
    for k in range(0, int(cnt.max()) + 1):
        pred = cnt >= k
        tp, fp, fn, tn = conf_matrix(pred, y == 1)
        sens, spec, ppv, npv, acc = metrics_from(tp, fp, fn, tn)
        rows.append({"group": "total", "k": k, "sens": sens, "spec": spec,
                     "ppv": ppv, "npv": npv, "acc": acc,
                     "tp": tp, "fp": fp, "fn": fn, "tn": tn})
    return rows


def best_group_at_sens(rows, target_sens=0.90):
    """Among (group, k) configurations that hit sens >= target, the one
    with the highest spec.  Returns dict or None."""
    candidates = [r for r in rows if r["sens"] >= target_sens]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r["spec"])


# ---- Reporting --------------------------------------------------------
def write_report(results, group_results, path):
    lines = ["# High-sensitivity ('rule-out') detectors\n\n"]
    lines.append(
        "Source: 93-row z-score matrix from "
        "`out/multivariate_zmatrix.csv`.  Labels from "
        "`comparison_chart_new_data.xlsx`.\n\n")
    lines.append(
        "Each detector is constructed to catch as many true positives "
        "as possible (high sensitivity).  Specificity is allowed to "
        "drop in exchange.  Useful for **screening**: when the rule "
        "does NOT fire, the negative-predictive value (NPV) tells you "
        "how confident 'no positive case' is.\n\n")
    lines.append(
        "Two detector families are evaluated per outcome:\n\n"
        "1. **Direction-aware OR-rule** (greedy): each step adds the "
        "direction-aware OOB indicator (`z ≥ +2` or `z ≤ −2`) that "
        "covers the most new true positives.\n"
        "2. **Group-OOB-count rule** (paper-style): predict positive if "
        "`<group> OOB count >= k` for some Brain Panel group "
        "(Std/Global, PDR, Focal, Diffuse, State Shift, or Total).\n\n")
    lines.append("---\n\n")

    for r, gres in zip(results, group_results):
        outcome = r["outcome"]
        lines.append(f"## {outcome}\n\n")
        if r.get("skipped"):
            lines.append(
                f"Insufficient positive/negative class: n+ = {r['n_pos']}, "
                f"n- = {r['n_neg']}.  Skipped.\n\n")
            continue
        n_pos, n_neg = r["n_pos"], r["n_neg"]
        prev = n_pos / (n_pos + n_neg)
        lines.append(
            f"n+ = {n_pos}, n- = {n_neg}, prevalence = {prev*100:.0f}%.\n\n")

        # Single-feature top-10 by TPR
        lines.append("### Single direction-aware features ranked by TPR\n\n")
        lines.append("| Metric | Direction | TPR (sens at depth=1) | FPR | "
                     "Spec | PPV | NPV |\n")
        lines.append("|---|---|---|---|---|---|---|\n")
        for s in r["single"]:
            metric, side = s["name"]
            side_str = "z ≥ +2" if side == "high" else "z ≤ −2"
            npv = (n_neg - s["fp"]) / (n_neg - s["fp"] + (n_pos - s["tp"])) \
                if (n_neg - s["fp"] + (n_pos - s["tp"])) else float("nan")
            lines.append(
                f"| {metric} | {side_str} | {s['sens']*100:.0f}% | "
                f"{s['fpr']*100:.0f}% | {s['spec']*100:.0f}% | "
                f"{s['ppv']*100:.0f}% | {npv*100:.0f}% |\n")
        lines.append("\n")

        # Greedy OR-rule
        lines.append("### Greedy OR-rule (each step adds maximum-new-TP feature)\n\n")
        lines.append("| Depth | Added flag | Sens | Spec | PPV | NPV | Acc | "
                     "TP / FP / FN / TN |\n")
        lines.append("|---|---|---|---|---|---|---|---|\n")
        for rule in r["rules"]:
            metric, side = rule["name"]
            side_str = "+" if side == "high" else "−"
            lines.append(
                f"| {rule['depth']} | {metric} ({side_str}) | "
                f"{rule['sens']*100:.0f}% | {rule['spec']*100:.0f}% | "
                f"{rule['ppv']*100:.0f}% | {rule['npv']*100:.0f}% | "
                f"{rule['acc']*100:.0f}% | "
                f"{rule['tp']} / {rule['fp']} / {rule['fn']} / {rule['tn']} |\n")
        lines.append("\n")

        # Group-OOB rules at high sens
        lines.append("### Group-OOB-count rules (paper-style)\n\n")
        best_at_90 = best_group_at_sens(gres, target_sens=0.90)
        best_at_80 = best_group_at_sens(gres, target_sens=0.80)
        for tgt, best in [("90% sens", best_at_90), ("80% sens", best_at_80)]:
            if best is None:
                lines.append(f"- Best rule at {tgt}: not achievable.\n")
            else:
                lines.append(
                    f"- Best rule at **≥{tgt}**: `{best['group']} OOB count ≥ {best['k']}` ->"
                    f"sens **{best['sens']*100:.0f}%**, spec **{best['spec']*100:.0f}%**, "
                    f"PPV {best['ppv']*100:.0f}%, NPV {best['npv']*100:.0f}%, "
                    f"acc {best['acc']*100:.0f}% "
                    f"(TP/FP/FN/TN = {best['tp']}/{best['fp']}/{best['fn']}/{best['tn']})\n")
        lines.append("\n---\n\n")

    lines.append("## How to use these\n\n")
    lines.append(
        "A high-sens rule-out detector is the opposite trade-off from "
        "the rule-in detectors:\n\n")
    lines.append(
        "- **If the rule does NOT fire** ->the outcome is very likely "
        "absent.  NPV tells you the chance of being right.  Useful "
        "for *clearing* a recording from further review.\n")
    lines.append(
        "- **If the rule fires** ->could be positive; needs follow-up.  "
        "PPV may be low because the rule was tuned to catch positives, "
        "not to avoid false positives.\n\n")
    lines.append(
        "The two styles are complementary in a real workflow:\n\n"
        "1. **Rule-out** (high-sens) screens out recordings that are "
        "clearly negative for an outcome.\n"
        "2. **Rule-in** (high-spec) confirms recordings that are "
        "clearly positive.\n"
        "3. The remaining middle (rule-out positive but rule-in "
        "negative) is the cohort that genuinely benefits from "
        "neurologist review.\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    print("Loading z-matrix + labels...")
    Z, patient_keys = load_zmatrix()
    labels = load_labels(patient_keys)
    features, fnames = build_features(Z, thr=2.0)
    print(f"  Z: {Z.shape}, features: {features.shape}")

    outcomes = [
        ("drowsiness",      "Drowsiness"),
        ("artifact_mod",    "Artifact (Moderate/Severe)"),
        ("quality_concern", "EEG Quality concern (Fair/Poor)"),
        ("abnormal",        "Clinical abnormality"),
        ("paroxysmal",      "Paroxysmal disturbance"),
    ]

    results = []
    group_results = []
    for key, name in outcomes:
        print(f"\n{name}:")
        r = analyze_outcome(name, labels[key], features, fnames)
        results.append(r)
        if r.get("skipped"):
            print(f"  skipped (n+ = {r['n_pos']}, n- = {r['n_neg']})")
            group_results.append([])
            continue
        # Group rules
        mask = np.array([v is not None for v in labels[key]])
        y = np.array([v for v in labels[key] if v is not None], dtype=int)
        gres = group_oob_rule_sweep(Z[mask], y)
        group_results.append(gres)
        best90 = best_group_at_sens(gres, 0.90)
        best80 = best_group_at_sens(gres, 0.80)
        if best90:
            print(f"  best group-rule @ 90% sens: {best90['group']} >= "
                  f"{best90['k']} ->spec {best90['spec']*100:.0f}%, "
                  f"PPV {best90['ppv']*100:.0f}%, NPV {best90['npv']*100:.0f}%")
        if best80:
            print(f"  best group-rule @ 80% sens: {best80['group']} >= "
                  f"{best80['k']} ->spec {best80['spec']*100:.0f}%, "
                  f"PPV {best80['ppv']*100:.0f}%, NPV {best80['npv']*100:.0f}%")
        last = r["rules"][-1] if r["rules"] else None
        if last:
            print(f"  greedy OR-rule depth {last['depth']}: sens "
                  f"{last['sens']*100:.0f}%, spec {last['spec']*100:.0f}%, "
                  f"NPV {last['npv']*100:.0f}%")

    out_path = os.path.join(OUT, "derive_rule_out_detectors.md")
    write_report(results, group_results, out_path)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
