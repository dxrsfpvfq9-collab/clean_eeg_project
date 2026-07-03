"""Cross-cohort validation of the rule-IN detectors (Section B of the
clinician quick-reference card) on the ORIGINAL n=100 training cohort.

Approach:
  1. Load the ID->EDF mapping built by match_original_cohort.py.
  2. For each row with an existing .icale.rep.pdf, parse the 48 z-scores
     using panel_parser.parse_panel_pdf().
  3. Pull the matching doctor's labels (drowsiness, artifact, quality,
     paroxysmal, clinical abnormality) from the original spreadsheet.
  4. Apply each Section B rule-in flag and compute PPV, sens, spec on
     this independent cohort.
  5. Report which flags replicate (PPV within 10pp of the n=98 derivation).

Output: out/validate_rule_in_original_cohort.md
"""
import csv
import os
import re
import sys

import numpy as np
from openpyxl import load_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from panel_parser import NAME_STRINGS, parse_panel_pdf  # noqa: E402
from moments_split_analysis import load_rows as load_spreadsheet_rows  # noqa
from moments_split_analysis import DEFAULT_SPREADSHEET  # noqa

OUT = os.path.join(HERE, "out")
MATCH_CSV = os.path.join(OUT, "original_cohort_match.csv")

_NOT_DEMONSTRATED = re.compile(r"\bnot\b[^.]*?\bdemonstrated\b", re.IGNORECASE)

# Section B rule-in flags from the clinician card (z >= +2 or z <= -2 on
# named metrics).  Direction-aware.
SECTION_B_FLAGS = {
    "Drowsiness": [
        ("Diffuse Beta",       "high", 100),  # derivation PPV %
        ("XS Temp. Alpha",     "low",  100),
        ("Delta Moment 1",     "high", 100),
        ("Focal Delta Amp.",   "high", 100),
        ("Focal Beta Index",   "high",  89),
        ("Focal Delta Amp.",   "low",   88),
        ("Diffuse Hibeta",     "high",  86),
        ("Diffuse Gamma",      "high",  86),
    ],
    "Artifact (Mod/Sev)": [
        ("Focal Beta Amp.",    "high", 100),
        ("PDR Moment 3",       "low",   80),
        ("Focal Theta Index",  "low",   75),
    ],
    "EEG Quality concern": [
        ("PDR Max Post.",      "high",  57),
    ],
    "Clinical Abnormality": [
        ("PDR Symmetry",       "low",   33),
        ("Frontal Delta",      "high",  33),
        ("XS Temp. Alpha",     "low",   25),
    ],
}


# ---- Label parsers (same logic as the other scripts) ------------------
def lbl_drowsiness(s):
    if s is None: return None
    t = str(s).strip().lower()
    if not t: return None
    if t in {"none", "no"}: return 0
    if _NOT_DEMONSTRATED.search(t): return 0
    if any(w in t for w in ["demonstrated", "noted", "diminution", "present"]):
        return 1
    return None


def lbl_artifact_mod(s):
    if s is None: return None
    t = str(s).strip().lower()
    if not t: return None
    if any(w in t for w in ["severe", "marked", "moderate"]):
        return 1
    if any(w in t for w in ["mild", "minimal", "minor", "none"]):
        return 0
    return None


def lbl_quality_concern(s):
    if s is None: return None
    t = str(s).strip().lower()
    if not t: return None
    if any(w in t for w in ["poor", "inadequate", "limited", "fair", "marginal"]):
        return 1
    if any(w in t for w in ["good", "excellent", "adequate"]):
        return 0
    return None


def lbl_abnormal(s):
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


def lbl_paroxysmal(s):
    if s is None: return None
    t = str(s).strip().lower()
    if not t: return None
    if t in {"none", "none.", "no", "no."}: return 0
    if any(w in t for w in ["spike", "sharp", "epileptiform", "discharge",
                            "paroxysm", "burst"]):
        return 1
    return None


# ---- PDF location helper --------------------------------------------
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


def main():
    print("Loading match CSV + spreadsheet...")
    match_rows = list(csv.DictReader(open(MATCH_CSV, encoding="utf-8")))
    print(f"  {len(match_rows)} ID rows in match CSV")

    spread_rows = load_spreadsheet_rows(DEFAULT_SPREADSHEET)
    spread_by_client = {r["client_id"]: r for r in spread_rows}

    # Build matched rows with z-scores + labels
    print("Parsing PDFs to extract z-scores...")
    n_used = 0
    n_no_pdf = 0
    n_bad_parse = 0
    Z = []
    keys = []
    labels = {"drowsy": [], "artifact": [], "quality": [], "abnormal": [],
              "paroxysmal": []}
    for r in match_rows:
        cid = r["client_id"]
        edf = r["edf_path"]
        pdf = find_pdf(edf)
        if pdf is None:
            n_no_pdf += 1
            continue
        try:
            res = parse_panel_pdf(pdf)
        except Exception as e:
            print(f"  parse error for {cid}: {e}")
            n_bad_parse += 1
            continue
        if not res.get("valid"):
            n_bad_parse += 1
            continue
        zs = res["zscores"]
        spread = spread_by_client.get(cid)
        if not spread:
            continue
        Z.append(zs)
        keys.append(cid)
        labels["drowsy"].append(lbl_drowsiness(spread["drowsiness"]))
        labels["artifact"].append(lbl_artifact_mod(spread["artifact"]))
        labels["quality"].append(lbl_quality_concern(spread["quality"]))
        labels["abnormal"].append(lbl_abnormal(spread["comments"]))
        labels["paroxysmal"].append(lbl_paroxysmal(spread["paroxysmal"]))
        n_used += 1

    Z = np.array(Z)
    print(f"  z-matrix shape: {Z.shape}")
    print(f"  used: {n_used}, no_pdf: {n_no_pdf}, bad_parse: {n_bad_parse}")
    print()

    # Compute each rule-IN flag and report PPV/sens/spec on this cohort
    name_to_idx = {n: i for i, n in enumerate(NAME_STRINGS)}

    print("=" * 96)
    print(f"{'Outcome':<22} {'Flag':<32} {'TP/FP/FN/TN':<14} {'Sens':>5} {'Spec':>5} {'PPV':>5} {'n+/n-':<8} {'pub PPV':>7}")
    print("=" * 96)

    md = ["# Cross-cohort validation of Section B rule-IN detectors on the original n=100 cohort\n\n"]
    md.append(f"Source z-scores: existing `.icale.rep.pdf` files for "
              f"{n_used} of the matched 100 EDFs (the remaining "
              f"{100 - n_used} EDFs would require a full pipeline re-run).\n\n")
    md.append("Each flag's derivation-cohort PPV is shown in the rightmost "
              "column for comparison.  PPV within 10pp = replicates.\n\n")

    label_map = {
        "Drowsiness": "drowsy",
        "Artifact (Mod/Sev)": "artifact",
        "EEG Quality concern": "quality",
        "Clinical Abnormality": "abnormal",
    }

    for outcome, flags in SECTION_B_FLAGS.items():
        md.append(f"## {outcome}\n\n")
        md.append("| Flag | Direction | TP/FP/FN/TN | Sens | Spec | PPV (n=100) | PPV (n=98 derived) | Replicates? |\n")
        md.append("|---|---|---|---|---|---|---|---|\n")
        ykey = label_map[outcome]
        y_full = labels[ykey]
        y_full = np.array([np.nan if v is None else float(v) for v in y_full])
        mask = ~np.isnan(y_full)
        y = y_full[mask].astype(int)
        n_pos = int(np.sum(y == 1))
        n_neg = int(np.sum(y == 0))
        for metric_name, side, pub_ppv in flags:
            if metric_name not in name_to_idx:
                continue
            i = name_to_idx[metric_name]
            col = Z[:, i][mask]
            if side == "high":
                flag = col >= 2.0
            else:
                flag = col <= -2.0
            tp = int(np.sum(flag & (y == 1)))
            fp = int(np.sum(flag & (y == 0)))
            fn = int(np.sum(~flag & (y == 1)))
            tn = int(np.sum(~flag & (y == 0)))
            sens = tp / (tp + fn) if (tp + fn) else float("nan")
            spec = tn / (tn + fp) if (tn + fp) else float("nan")
            ppv  = tp / (tp + fp) if (tp + fp) else float("nan")
            replicates = "—"
            if not np.isnan(ppv):
                delta = abs(ppv * 100 - pub_ppv)
                replicates = "✓ Yes" if delta <= 10 else f"✗ No ({delta:.0f}pp off)"
            print(f"{outcome:<22} {metric_name + ' ' + side:<32} "
                  f"{tp}/{fp}/{fn}/{tn:<8} "
                  f"{sens*100:>4.0f}% {spec*100:>4.0f}% "
                  f"{(ppv*100 if not np.isnan(ppv) else 0):>4.0f}% "
                  f"{n_pos}/{n_neg:<5} {pub_ppv:>5}%")
            side_str = "z >= +2" if side == "high" else "z <= -2"
            md.append(
                f"| {metric_name} | {side_str} | {tp}/{fp}/{fn}/{tn} | "
                f"{sens*100:.0f}% | {spec*100:.0f}% | "
                f"{(ppv*100 if not np.isnan(ppv) else 0):.0f}% | {pub_ppv}% | "
                f"{replicates} |\n"
            )
        md.append(f"\nn+ = {n_pos}, n- = {n_neg} on the {n_used}-EDF subset.\n\n")
        print()

    md.append("---\n\n## Interpretation\n\n")
    md.append(
        "These PPVs are from the **original n=100 training spreadsheet's "
        "doctor labels**, but using z-scores extracted from existing "
        f"Brain Panel `.icale.rep.pdf` files for {n_used} of the 100 "
        "EDFs.  This is an independent cohort relative to the n=98 "
        "validation cohort where the rule-IN flags were derived.\n\n"
        "Flags that show **PPV within 10pp of the derived value** are "
        "considered to replicate.  Flags whose PPV drops significantly "
        "(e.g., 100% → 50%) did not generalize and should be reported "
        "as derivation-cohort only.\n\n"
    )

    out_path = os.path.join(OUT, "validate_rule_in_original_cohort.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(md)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
