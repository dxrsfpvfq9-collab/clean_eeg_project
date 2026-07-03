"""Cross-cohort validation of the rule-OUT detectors.

The detectors in Sections A1-A4 of the quick-reference card were derived
on the n=98 validation cohort.  Here we test them on the ORIGINAL n=100
training spreadsheet to see whether the NPV claims hold.

What's testable:
  A1: Total OOB < 4   -> no Clinical Abnormality
  A2: Total OOB < 2   -> no Paroxysmal
  A3: State Shift = 0 -> no EEG Quality Concern (strict)
  A4: Total OOB < 4   -> no EEG Quality Concern (sensitive)
  + A1'-A4' counterparts for Drowsiness, Artifact (where NPV-based rule-out
  was not recommended but we report sens/spec/PPV/NPV for context)

What's NOT testable (no individual z-scores in original spreadsheet):
  B1-B4: direction-aware single-metric rule-IN flags

Output: out/cross_cohort_validation.md
"""
import os
import re
import sys

from openpyxl import load_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from moments_split_analysis import (  # noqa: E402
    load_rows, NEW_SPREADSHEET, DEFAULT_SPREADSHEET,
)
import re as _re
_NOT_DEMONSTRATED = _re.compile(r"\bnot\b[^.]*?\bdemonstrated\b",
                                  _re.IGNORECASE)

OUT = os.path.join(HERE, "out")


def label_quality_concern(s):
    if s is None: return None
    t = str(s).strip().lower()
    if not t: return None
    if any(w in t for w in ["poor", "inadequate", "limited", "fair", "marginal"]):
        return 1
    if any(w in t for w in ["good", "excellent", "adequate"]):
        return 0
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


def label_drowsiness(s):
    if s is None: return None
    t = str(s).strip().lower()
    if not t: return None
    if t in {"none", "no"}: return 0
    if _NOT_DEMONSTRATED.search(t): return 0
    if any(w in t for w in ["demonstrated", "noted", "diminution", "present"]):
        return 1
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


def metrics(tp, fp, fn, tn):
    sens = tp / (tp + fn) if (tp + fn) else float("nan")
    spec = tn / (tn + fp) if (tn + fp) else float("nan")
    ppv  = tp / (tp + fp) if (tp + fp) else float("nan")
    npv  = tn / (tn + fn) if (tn + fn) else float("nan")
    n = tp + fp + fn + tn
    acc = (tp + tn) / n if n else float("nan")
    return sens, spec, ppv, npv, acc


def evaluate(rows, condition_fn, label_fn, key, group_size_field=None):
    """For each row, condition_fn returns True if the rule predicts POSITIVE.
    Rule-OUT rules predict POSITIVE when the threshold is exceeded
    (i.e., "cannot rule out the outcome").  NPV = of rows where the rule
    predicted NEGATIVE (= cleared), how many were actually negative.
    """
    tp = fp = fn = tn = 0
    n_unlab = 0
    for r in rows:
        y = label_fn(r[key])
        if y is None:
            n_unlab += 1
            continue
        pred_pos = condition_fn(r["counts"])
        if pred_pos and y == 1: tp += 1
        elif pred_pos and y == 0: fp += 1
        elif not pred_pos and y == 1: fn += 1
        else: tn += 1
    sens, spec, ppv, npv, acc = metrics(tp, fp, fn, tn)
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "sens": sens, "spec": spec, "ppv": ppv, "npv": npv, "acc": acc,
        "n_unlab": n_unlab,
    }


# ---- Conditions (rule predicts POSITIVE when outcome NOT confidently absent) -
def cond_total_ge(k):
    return lambda c: c["total"] >= k


def cond_state_shift_ge(k):
    return lambda c: c["state_shift"] >= k


# ---- Run on both cohorts ---------------------------------------------
def main():
    print("Loading cohorts...")
    orig = load_rows(DEFAULT_SPREADSHEET)
    new  = load_rows(NEW_SPREADSHEET)
    print(f"  Original (n=100): {len(orig)} rows loaded")
    print(f"  New      (n=98):  {len(new)}  rows loaded")

    rules = [
        # (rule_label, condition_fn, label_fn, key, intended_outcome,
        #  derivation_npv)
        ("A1. Total OOB ≥ 4 → can't rule out Clinical Abnormality",
         cond_total_ge(4), label_abnormal, "comments",
         "Clinical Abnormality", 96),
        ("A2. Total OOB ≥ 2 → can't rule out Paroxysmal",
         cond_total_ge(2), label_paroxysmal, "paroxysmal",
         "Paroxysmal", 100),
        ("A3. State Shift ≥ 1 → can't rule out EEG Quality concern (strict)",
         cond_state_shift_ge(1), label_quality_concern, "quality",
         "EEG Quality concern", 93),
        ("A4. Total OOB ≥ 4 → can't rule out EEG Quality concern (sens.)",
         cond_total_ge(4), label_quality_concern, "quality",
         "EEG Quality concern", 96),
        # Same rule applied to additional outcomes — for context
        ("(context) Total OOB ≥ 4 → can't rule out Drowsiness",
         cond_total_ge(4), label_drowsiness, "drowsiness",
         "Drowsiness", None),
        ("(context) Total OOB ≥ 2 → can't rule out Mod/Sev Artifact",
         cond_total_ge(2), label_artifact_moderate, "artifact",
         "Artifact", None),
    ]

    # Run each rule on both cohorts
    rows_for_doc = []
    for desc, cond, lbl, key, outcome_name, derived_npv in rules:
        r_o = evaluate(orig, cond, lbl, key)
        r_n = evaluate(new, cond, lbl, key)
        rows_for_doc.append({
            "desc": desc,
            "outcome": outcome_name,
            "derived_npv": derived_npv,
            "orig": r_o,
            "new":  r_n,
        })

    # Console summary -- ASCII safe
    print("\n" + "=" * 100)
    print(f"{'Outcome / rule':<50}  {'cohort':<10}  {'NPV':>6}  {'TN/FN':>10}")
    print("=" * 100)
    for r in rows_for_doc:
        ascii_desc = r['desc'].replace('≥', '>=').replace('→', '->')[:48]
        for cohort_label, c in (("orig n=100", r["orig"]), ("new n=98", r["new"])):
            npv_val = c['npv'] * 100 if (c['tn'] + c['fn']) > 0 else 0
            print(f"{ascii_desc:<50}  {cohort_label:<10}  "
                  f"{npv_val:>5.0f}%  {c['tn']}/{c['fn']:>2}")

    # Markdown report
    md_lines = [
        "# Cross-cohort validation of the rule-OUT detectors\n\n",
        "These rules were **derived on the n=98 validation cohort** (Section A "
        "of the clinician quick-reference card).  This document tests them on "
        "the **original n=100 training cohort** to check whether the NPV "
        "claims hold across cohorts.\n\n",
        "What's testable: group-level OOB count rules.  Both spreadsheets "
        "carry the same six group counts (Std/Global, PDR, Phenotype, Focal, "
        "Diffuse, State Shift) and the Total.\n\n",
        "What's NOT testable here: the rule-IN detectors (Sections B1-B4), "
        "which use direction-aware single-metric flags (e.g., 'Diffuse Beta z "
        "≥ +2').  The original n=100 spreadsheet only carries group OOB "
        "counts, not individual z-scores.  Those rules would need the "
        "original cohort PDFs re-parsed for individual z-scores before a "
        "fair cross-cohort test.\n\n",
        "---\n\n## Results\n\n",
        "Each row shows the rule's predicted-negative confidence (NPV) and the "
        "TN/FN counts on each cohort.  **Higher NPV = better rule-OUT.**\n\n",
        "| Rule | Outcome | Derived NPV (n=98) | NPV on n=98 | TN/FN n=98 | "
        "NPV on n=100 | TN/FN n=100 | Replicates? |\n",
        "|---|---|---|---|---|---|---|---|\n",
    ]
    for r in rows_for_doc:
        derived = f"{r['derived_npv']}%" if r["derived_npv"] else "(context)"
        n_o = r["orig"]; n_n = r["new"]
        npv_o = "n/a" if n_o["tn"] + n_o["fn"] == 0 else f"{n_o['npv']*100:.0f}%"
        npv_n = "n/a" if n_n["tn"] + n_n["fn"] == 0 else f"{n_n['npv']*100:.0f}%"
        # Replication: does NPV on n=100 match the derived value within 10pp?
        replicates = "—"
        if r["derived_npv"] is not None and n_o["tn"] + n_o["fn"] > 0:
            delta = abs(n_o["npv"] * 100 - r["derived_npv"])
            replicates = "✓ Yes" if delta <= 10 else f"✗ No ({delta:.0f}pp off)"
        md_lines.append(
            f"| {r['desc']} | {r['outcome']} | {derived} | {npv_n} | "
            f"{n_n['tn']}/{n_n['fn']} | {npv_o} | {n_o['tn']}/{n_o['fn']} | "
            f"{replicates} |\n"
        )

    md_lines.append("\n---\n\n## Interpretation\n\n")
    md_lines.append(
        "**Which rules replicate** (NPV within 10pp of the derivation claim):\n\n"
    )

    # Quick text summary of replication
    for r in rows_for_doc:
        if r["derived_npv"] is None:
            continue
        n_o = r["orig"]
        if n_o["tn"] + n_o["fn"] == 0:
            continue
        delta = n_o["npv"] * 100 - r["derived_npv"]
        verdict = "REPLICATES" if abs(delta) <= 10 else "DOES NOT REPLICATE"
        md_lines.append(
            f"- **{r['outcome']}** ({r['desc'].split(' → ')[0]}): "
            f"derived NPV {r['derived_npv']}%, "
            f"observed on n=100 = {n_o['npv']*100:.0f}% "
            f"({n_o['tn']} TN, {n_o['fn']} FN).  **{verdict}.**\n"
        )

    md_lines.append("\n---\n\n## What this doesn't test\n\n")
    md_lines.append(
        "The Section B rule-IN detectors (e.g., 'Diffuse Beta z ≥ +2 → 100% "
        "PPV for drowsiness') were derived from the 48-z-score matrix on the "
        "n=98 cohort.  Their cross-cohort validation requires re-parsing the "
        "original n=100 cohort PDFs to extract the same 48 individual z-scores.  "
        "That is the next step before claiming any of the 100% PPV figures "
        "are robust.\n\n"
        "Without that step, the rule-IN figures should be reported as "
        "**in-sample on the derivation cohort** and treated as candidates "
        "for follow-up validation, not as established performance numbers.\n"
    )

    out_path = os.path.join(OUT, "cross_cohort_validation.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(md_lines)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
