"""Run rule-IN PPV validation on the COMBINED cross-cohort:
  100 original-study EDFs  +  242 newly-processed EDFs
  = up to 342 EDFs labelled by Dr. P. David Ims.

This is independent of the n=98 derivation cohort where the rules were
originally crafted, so it's a clean cross-cohort generalization test.

Pipeline:
  1. Load the rule-IN flag specs (B1-B4) from the clinician card.
  2. For each EDF in both cohorts, parse the .icale.rep.pdf for its
     48 z-scores.
  3. Pull doctor's labels:
       - n=100 cohort: from original spreadsheet (load_spreadsheet_rows)
       - 242 new cohort: from new_cohort_labels.csv (dr_report_parser output)
  4. Apply each rule-IN flag and compute PPV/sens/spec on the combined
     cohort, and on each sub-cohort separately for comparison.

Output: out/validate_rule_in_combined.md
"""
import csv
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, PROJECT_ROOT)

from panel_parser import NAME_STRINGS, parse_panel_pdf  # noqa: E402
from moments_split_analysis import load_rows as load_spreadsheet_rows  # noqa
from moments_split_analysis import DEFAULT_SPREADSHEET  # noqa

OUT = os.path.join(HERE, "out")

# Rule-IN flag specs from the clinician card (after cross-validation
# on the original cohort).
SECTION_B_FLAGS = {
    "Drowsiness": [
        ("Diffuse Hibeta",   "high", 86),
        ("Diffuse Gamma",    "high", 86),
        ("XS Temp. Alpha",   "low",  80),
        ("Focal Delta Amp.", "low",  80),
        ("Diffuse Beta",     "high", 78),
        # Flags that were dropped but worth tracking for completeness:
        ("Delta Moment 1",   "high", 75),  # was 100 derivation, dropped to 75
        ("Focal Delta Amp.", "high", 50),  # was 100, dropped to 50
        ("Focal Beta Index", "high", 67),  # was 89, dropped to 67
    ],
    "Artifact (Mod/Sev)": [
        ("PDR Moment 3",      "low",  100),  # was 80, strengthened to 100
        ("Focal Theta Index", "low",   67),  # was 75, dropped slightly
        ("Focal Beta Amp.",   "high",  57),  # was 100, dropped to 57
    ],
    "EEG Quality concern": [
        ("PDR Max Post.",     "high",  36),  # was 57, dropped to 36
    ],
    "Clinical Abnormality": [
        ("Frontal Delta",     "high",  33),
        ("XS Temp. Alpha",    "low",   20),
        ("PDR Symmetry",      "low",    0),  # dropped to 0
    ],
}

_NOT_DEMONSTRATED = re.compile(r"\bnot\b[^.]*?\bdemonstrated\b", re.IGNORECASE)


# ---- Label parsers (matching the original-cohort logic) -------------
def lbl_drowsiness(s):
    if s is None:
        return None
    t = str(s).strip().lower()
    if not t:
        return None
    if t in {"none", "no"}:
        return 0
    if _NOT_DEMONSTRATED.search(t):
        return 0
    if any(w in t for w in ["demonstrated", "noted", "diminution", "present"]):
        return 1
    return None


def lbl_artifact_mod(s):
    if s is None:
        return None
    t = str(s).strip().lower()
    if not t:
        return None
    if any(w in t for w in ["severe", "marked", "moderate"]):
        return 1
    if any(w in t for w in ["mild", "minimal", "minor", "none"]):
        return 0
    return None


def lbl_quality_concern(s):
    if s is None:
        return None
    t = str(s).strip().lower()
    if not t:
        return None
    if any(w in t for w in ["poor", "inadequate", "limited", "fair", "marginal"]):
        return 1
    if any(w in t for w in ["good", "excellent", "adequate"]):
        return 0
    return None


def lbl_abnormal(s):
    if s is None:
        return None
    t = str(s).strip().lower()
    if not t:
        return None
    for neg in ["no overt abnormal", "no abnormalities noted",
                "no abnormalities", "no abnormal", "no other overt",
                "no other abnormal"]:
        if neg in t:
            return 0
    for pos in ["epileptiform", "spike wave", "spike-wave",
                "sharp wave", "sharp/slowing", "interictal",
                "ictal", "encephalopathy", "abnormal",
                "slowing of background", "intermittent slowing",
                "isolated spike", "intermittent left"]:
        if pos in t:
            return 1
    return None


def lbl_paroxysmal(s):
    if s is None:
        return None
    t = str(s).strip().lower()
    if not t:
        return None
    if t in {"none", "none.", "no", "no."}:
        return 0
    if any(w in t for w in ["spike", "sharp", "epileptiform", "discharge",
                            "paroxysm", "burst"]):
        return 1
    return None


# ---- PDF location -----------------------------------------------
def find_pdf(edf_path):
    if not edf_path:
        return None
    bn = os.path.basename(edf_path).replace(".edf", "")
    d = os.path.dirname(edf_path)
    for sub in ("", "output", "output version 1"):
        cand = os.path.join(d, sub, bn + ".icale.rep.pdf")
        if os.path.exists(cand):
            return cand
    return None


# ---- Cohort loaders ---------------------------------------------
def load_original_cohort():
    """Return list of dicts with z, drowsy, artifact, quality, abnormal,
    paroxysmal from the n=100 original-study spreadsheet."""
    match_rows = list(csv.DictReader(open(
        os.path.join(OUT, "original_cohort_match.csv"), encoding="utf-8")))
    spread = {r["client_id"]: r for r in
              load_spreadsheet_rows(DEFAULT_SPREADSHEET)}
    out = []
    for r in match_rows:
        cid = r["client_id"]
        edf = r["edf_path"]
        pdf = find_pdf(edf)
        if pdf is None:
            continue
        try:
            res = parse_panel_pdf(pdf)
        except Exception:
            continue
        if not res.get("valid"):
            continue
        s = spread.get(cid)
        if not s:
            continue
        out.append({
            "cohort": "original_n100",
            "z": res["zscores"],
            "drowsy":     lbl_drowsiness(s["drowsiness"]),
            "artifact":   lbl_artifact_mod(s["artifact"]),
            "quality":    lbl_quality_concern(s["quality"]),
            "abnormal":   lbl_abnormal(s["comments"]),
            "paroxysmal": lbl_paroxysmal(s["paroxysmal"]),
        })
    return out


def load_new_cohort():
    """Return list of dicts with z + labels for the 242 new EDFs."""
    label_rows = list(csv.DictReader(open(
        os.path.join(OUT, "new_cohort_labels.csv"), encoding="utf-8")))
    label_map = {os.path.normpath(r["edf_path"]).lower(): r
                  for r in label_rows}
    out = []
    for r in label_rows:
        edf = r["edf_path"]
        pdf = find_pdf(edf)
        if pdf is None:
            continue
        try:
            res = parse_panel_pdf(pdf)
        except Exception:
            continue
        if not res.get("valid"):
            continue
        # Labels are already structured in the CSV
        def _to_bin(v, pos_label, neg_label):
            v = (v or "").strip()
            if not v:
                return None
            if v == pos_label:
                return 1
            if v == neg_label:
                return 0
            return None
        out.append({
            "cohort": "new_242",
            "z": res["zscores"],
            "drowsy":     _to_bin(r["drowsiness"],
                                  "Demonstrated", "Not demonstrated"),
            "artifact":   _to_bin(r["artifact_severity"], "Moderate", "Mild")
                          or _to_bin(r["artifact_severity"], "Severe", "Mild"),
            "quality":    _to_bin(r["quality"], "Fair", "Good")
                          or _to_bin(r["quality"], "Poor", "Good"),
            "abnormal":   _to_bin(r["clinical_abnormality"], "Yes", "No"),
            "paroxysmal": _to_bin(r["paroxysmal"], "Present", "None"),
        })
    return out


# ---- Metrics helpers ---------------------------------------------
def metrics_for(flag_arr, label_arr):
    """flag_arr/label_arr are aligned int arrays."""
    flag = np.asarray(flag_arr, dtype=bool)
    y = np.asarray(label_arr, dtype=bool)
    tp = int(np.sum(flag & y))
    fp = int(np.sum(flag & ~y))
    fn = int(np.sum(~flag & y))
    tn = int(np.sum(~flag & ~y))
    sens = tp / (tp + fn) if (tp + fn) else float("nan")
    spec = tn / (tn + fp) if (tn + fp) else float("nan")
    ppv  = tp / (tp + fp) if (tp + fp) else float("nan")
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "sens": sens, "spec": spec, "ppv": ppv}


# ---- Main --------------------------------------------------------
def main():
    print("Loading original n=100 cohort...")
    orig = load_original_cohort()
    print(f"  loaded {len(orig)} EDFs with z-scores + labels")

    print("Loading new 242-EDF cohort...")
    new = load_new_cohort()
    print(f"  loaded {len(new)} EDFs with z-scores + labels")

    combined = orig + new
    print(f"\nCOMBINED cohort: {len(combined)} EDFs\n")

    name_to_idx = {n: i for i, n in enumerate(NAME_STRINGS)}

    md = ["# Combined cross-cohort validation of Section B rule-IN flags\n\n"]
    md.append(f"**Cohorts** (both independent of the n=98 derivation):\n")
    md.append(f"- Original n=100 cohort (from BP_PDR07AUG.xlsx + ICALE PDFs):  "
              f"{len(orig)} EDFs\n")
    md.append(f"- 242-EDF expansion (from STS QA Reviews + labels parsed "
              f"with dr_report_parser):  {len(new)} EDFs\n")
    md.append(f"- **Combined**:  **{len(combined)} EDFs**, all labelled by "
              f"Dr. P. David Ims.\n\n")
    md.append("---\n\n")

    label_keys = {
        "Drowsiness":           "drowsy",
        "Artifact (Mod/Sev)":   "artifact",
        "EEG Quality concern":  "quality",
        "Clinical Abnormality": "abnormal",
    }

    print(f"{'Outcome':<22} {'Flag':<32} {'cohort':<10} {'n+/n-':<8} "
          f"{'TP/FP/FN/TN':<14} {'Sens':>4} {'Spec':>4} {'PPV':>4} {'card PPV':>8}")
    print("=" * 110)

    for outcome, flags in SECTION_B_FLAGS.items():
        md.append(f"## {outcome}\n\n")
        md.append("| Flag | Cohort | n+ / n- | TP/FP/FN/TN | "
                  "Sens | Spec | **PPV** | Card PPV |\n")
        md.append("|---|---|---|---|---|---|---|---|\n")

        ykey = label_keys[outcome]

        for metric_name, side, card_ppv in flags:
            if metric_name not in name_to_idx:
                continue
            mi = name_to_idx[metric_name]

            for cohort_label, rows in [("original_n100", orig),
                                       ("new_242", new),
                                       ("COMBINED", combined)]:
                # Filter to labelled rows
                y = []; z = []
                for r in rows:
                    if r[ykey] is None:
                        continue
                    y.append(r[ykey])
                    z.append(r["z"][mi])
                y = np.array(y)
                z = np.array(z)
                if len(y) == 0 or len(set(y.tolist())) < 2:
                    continue
                if side == "high":
                    flag = z >= 2.0
                else:
                    flag = z <= -2.0
                m = metrics_for(flag, y)
                n_pos = int(np.sum(y == 1))
                n_neg = int(np.sum(y == 0))
                side_str = "z ≥ +2" if side == "high" else "z ≤ −2"
                ppv_str = f"{m['ppv']*100:.0f}%" if not np.isnan(m['ppv']) else "—"
                cohort_emph = "**" if cohort_label == "COMBINED" else ""
                md.append(
                    f"| {metric_name} ({side_str}) | {cohort_emph}{cohort_label}{cohort_emph} | "
                    f"{n_pos}/{n_neg} | {m['tp']}/{m['fp']}/{m['fn']}/{m['tn']} | "
                    f"{m['sens']*100:.0f}% | {m['spec']*100:.0f}% | "
                    f"{cohort_emph}{ppv_str}{cohort_emph} | {card_ppv}% |\n"
                )
                print(f"{outcome:<22} {metric_name + ' ' + side:<32} "
                      f"{cohort_label:<10} {n_pos}/{n_neg:<5} "
                      f"{m['tp']}/{m['fp']}/{m['fn']}/{m['tn']:<6} "
                      f"{m['sens']*100:>3.0f}% {m['spec']*100:>3.0f}% "
                      f"{ppv_str:>4} {card_ppv}%")
            print()
            md.append("\n")

    md.append("---\n\n## Interpretation\n\n")
    md.append(
        "Comparing the COMBINED-cohort PPV to the clinician-card PPV "
        "tells us which flags **really** generalize.  A flag that holds "
        "within 10 pp of the card value across ~340 independent EDFs is "
        "robust.  A flag that drops materially (≥ 15 pp) should be "
        "downgraded or removed from the clinician card.\n\n"
        "Sample sizes are now large enough for proper confidence "
        "intervals (95% CI half-width ≈ ±5 pp on PPV at n=300).\n"
    )

    out_path = os.path.join(OUT, "validate_rule_in_combined.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(md)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
