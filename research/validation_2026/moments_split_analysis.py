"""Two-distribution analysis on the original n=100 spreadsheet.

Configurable split rule -- pass --group/--threshold/--out on the command
line, or edit DEFAULT_SPLIT below.  Default is State Shift >= 3 ("3+
Moments OOB"), which produced out/moments_split_analysis.md.  Re-running
with --group pdr --threshold 2 reproduces the PDR variant.

For each group, summarize how the doctor's comments distribute across:
  - EEG Quality (Good / Fair / Poor)
  - Artifact severity (Mild / Moderate / Severe)
  - Drowsiness (demonstrated / not demonstrated)
  - Paroxysmal disturbance (None / present)
  - Clinical abnormality (Yes / No, parsed from DR Comments)
  - PDR frequency (numeric, where parseable)

Report Fisher's exact p-values for the binary breakdowns and effect-size
summaries.

Outputs:
  out/<split-name>_split_analysis.md
"""
import argparse
import os
import re
import sys
from collections import Counter
from math import lgamma

import numpy as np
from openpyxl import load_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

DEFAULT_SPREADSHEET = (
    r"C:\BrainPanel\01_Comparison Chart BP to DR 2024_2025 "
    r"Comments Complete Added Drowsiness Column minus DOC full "
    r"txt and BP_PDR07AUG.xlsx")
NEW_SPREADSHEET = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "out", "comparison_chart_new_data.xlsx")
OUT = os.path.join(HERE, "out")

# Default split: State Shift (Moments) >= 3.  Override on the CLI.
DEFAULT_SPLIT = {"group": "state_shift", "threshold": 3,
                 "name": "moments", "label": "Moments OOB",
                 "outfile": "moments_split_analysis.md"}

GROUP_LABELS = {
    "std_global":  "Std/Global OOB",
    "pdr":         "PDR OOB",
    "phenotypes":  "Phenotype OOB",
    "focal":       "Focal/Frontal OOB",
    "diffuse":     "Diffuse OOB",
    "state_shift": "State Shift (Moments) OOB",
    "total":       "Total OOB",
}

_NOT_DEMONSTRATED = re.compile(r"\bnot\b[^.]*?\bdemonstrated\b", re.IGNORECASE)
PDR_RE   = re.compile(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*hz",
                      re.IGNORECASE)
PDR_RE1  = re.compile(r"\b(\d+(?:\.\d+)?)\s*hz\b", re.IGNORECASE)


# Header substrings used to locate each field.  Order matters: the
# "comments" key is matched LAST so the more specific keys (quality,
# artifact, ...) claim their columns first.  For "comments" we take the
# rightmost column that contains "dr comments" but isn't claimed by
# another field, so we land on the substantive narrative (not "DR
# Comments Overall quality").
_HEADER_KEYS_ORDERED = [
    ("quality",    "overall quality"),
    ("artifact",   "presence of artifact"),
    ("artifree",   "artifact free"),
    ("background", "background"),
    ("drowsiness", "drowsiness"),
    ("paroxysmal", "paroxsmal"),
]
_HEADER_KEYS = dict(_HEADER_KEYS_ORDERED)


def _resolve_columns(ws):
    """Find the column index for each doctor-text field by header match.

    Both the original (n=100) and new (n=98) comparison-chart spreadsheets
    use a similar header layout but with one column shifted, so name-based
    lookup is more robust than fixed indices.  Returns dict[field -> int].
    """
    # Try header row 1 first, then row 3 (the "Patient ID / Client ID" row).
    header = [str(c.value or "").strip().lower() for c in ws[1]]
    if not any(_HEADER_KEYS["quality"] in h for h in header):
        header = [str(c.value or "").strip().lower() for c in ws[3]]

    cols = {}
    for field, key in _HEADER_KEYS_ORDERED:
        for idx, h in enumerate(header):
            if key in h and idx not in cols.values():
                cols[field] = idx
                break

    # Comments: rightmost column whose header contains "dr comments" but
    # not "quality" (which is the first DR-Comments-prefixed column).
    comments_candidates = [
        idx for idx, h in enumerate(header)
        if "dr comments" in h and "quality" not in h
    ]
    if comments_candidates:
        cols["comments"] = comments_candidates[-1]
    elif "comments" not in cols:
        # Fall back: column right after paroxysmal.
        cols["comments"] = cols.get("paroxysmal", -1) + 1

    # Sanity fallback: if any field is missing, use fixed original-layout
    # indices.
    if not all(f in cols for f in ["quality", "artifact", "artifree",
                                    "background", "drowsiness", "paroxysmal",
                                    "comments"]):
        cols = {"quality": 10, "artifact": 11, "artifree": 12,
                "background": 13, "drowsiness": 14, "paroxysmal": 15,
                "comments": 16}
    return cols


def load_rows(spreadsheet_path):
    wb = load_workbook(spreadsheet_path, data_only=True)
    ws = wb.active
    cols = _resolve_columns(ws)
    rows = []
    # Real data starts at row 4 in both layouts.
    for r in ws.iter_rows(min_row=4, values_only=True):
        if r[1] is None or str(r[1]).strip() == "":
            continue
        try:
            counts = {
                "total":       int(r[2]) if r[2] is not None else 0,
                "std_global":  int(r[3]) if r[3] is not None else 0,
                "pdr":         int(r[4]) if r[4] is not None else 0,
                "phenotypes":  int(r[5]) if r[5] is not None else 0,
                "focal":       int(r[6]) if r[6] is not None else 0,
                "diffuse":     int(r[7]) if r[7] is not None else 0,
                "state_shift": int(r[8]) if r[8] is not None else 0,
            }
        except (TypeError, ValueError):
            continue
        rows.append({
            "client_id":  r[1],
            "counts":     counts,
            "quality":    str(r[cols["quality"]]    or "").strip(),
            "artifact":   str(r[cols["artifact"]]   or "").strip(),
            "artifree":   str(r[cols["artifree"]]   or "").strip(),
            "background": str(r[cols["background"]] or "").strip(),
            "drowsiness": str(r[cols["drowsiness"]] or "").strip(),
            "paroxysmal": str(r[cols["paroxysmal"]] or "").strip(),
            "comments":   str(r[cols["comments"]]   or "").strip(),
        })
    return rows


def label_quality(s):
    t = s.lower()
    if not t:
        return None
    if "good" in t or "excellent" in t:
        return "Good"
    if "fair" in t:
        return "Fair"
    if "poor" in t or "inadequate" in t:
        return "Poor"
    return None


def label_artifact_severity(s):
    t = s.lower()
    if not t:
        return None
    if "severe" in t or "marked" in t:
        return "Severe"
    if "moderate" in t:
        return "Moderate"
    if "mild" in t or "minimal" in t or "minor" in t:
        return "Mild"
    return None


def label_drowsiness(s):
    t = s.lower()
    if not t:
        return None
    if t in {"none", "no"}:
        return "Not demonstrated"
    if _NOT_DEMONSTRATED.search(t):
        return "Not demonstrated"
    if "demonstrated" in t or "noted" in t or "diminution" in t or "present" in t:
        return "Demonstrated"
    return None


def label_paroxysmal(s):
    t = s.lower()
    if not t:
        return None
    if t in {"none", "none.", "no", "no."}:
        return "None"
    if any(w in t for w in ["spike", "sharp", "epileptiform", "discharge",
                            "paroxysm", "burst", "slowing"]):
        return "Present"
    if "none" in t and "no abnormal" in t:
        return "None"
    return None


def label_abnormal(s):
    t = s.lower()
    if not t:
        return None
    for neg in ["no overt abnormal", "no abnormalities noted",
                "no abnormalities", "no abnormal", "no other overt",
                "no other abnormal"]:
        if neg in t:
            return "No"
    for pos in ["epileptiform", "spike wave", "sharp wave", "sharp/slowing",
                "interictal", "ictal", "encephalopathy", "abnormal",
                "slowing of background", "intermittent slowing",
                "isolated spike", "intermittent left"]:
        if pos in t:
            return "Yes"
    return None


def pdr_freq(s):
    t = s.lower()
    if not t:
        return None
    if ("not clearly demonstrated" in t or "no clearly defined" in t):
        return ("Not demonstrated", None)
    m = PDR_RE.search(t)
    if m:
        lo = float(m.group(1)); hi = float(m.group(2))
        return ((lo + hi) / 2, lo)
    m = PDR_RE1.search(t)
    if m:
        v = float(m.group(1))
        return (v, v)
    return None


# --------- Fisher exact test (2x2) -------------------------------------
def _logcomb(n, k):
    return lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)


def fisher_exact_2x2(a, b, c, d):
    """One-sided + two-sided p, plus odds ratio.

    Table:
        A   B
        C   D
    """
    n = a + b + c + d
    r1, r2 = a + b, c + d
    c1, c2 = a + c, b + d
    if r1 == 0 or r2 == 0 or c1 == 0 or c2 == 0:
        return float("nan"), float("nan"), float("nan")
    # Probability of observed table under hypergeometric
    def logp(a_):
        return (_logcomb(r1, a_) + _logcomb(r2, c1 - a_) - _logcomb(n, c1))
    obs_lp = logp(a)
    lo = max(0, c1 - r2)
    hi = min(r1, c1)
    lps = [logp(x) for x in range(lo, hi + 1)]
    p_two = sum(np.exp(lp) for lp in lps if lp <= obs_lp + 1e-12)
    odds = (a * d) / (b * c) if (b * c) > 0 else float("inf")
    return p_two, odds, obs_lp


# --------- Main analysis ----------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default=DEFAULT_SPLIT["group"],
                    choices=list(GROUP_LABELS.keys()),
                    help="Which OOB column to split on.")
    ap.add_argument("--threshold", type=int,
                    default=DEFAULT_SPLIT["threshold"],
                    help="Group A := samples with count >= threshold.")
    ap.add_argument("--name", default=None,
                    help="Short name used for the output filename "
                         "(default derives from --group).")
    ap.add_argument("--label", default=None,
                    help="Human-readable label like 'Moments OOB' or "
                         "'PDR OOB' (default from --group).")
    ap.add_argument("--spreadsheet", default=DEFAULT_SPREADSHEET,
                    help="Path to the xlsx comparison chart to analyze. "
                         "Use --new for the n=98 validation cohort.")
    ap.add_argument("--new", action="store_true",
                    help="Use the new-cohort spreadsheet "
                         "(out/comparison_chart_new_data.xlsx).")
    args = ap.parse_args()
    spreadsheet = NEW_SPREADSHEET if args.new else args.spreadsheet

    split_group = args.group
    split_thr = args.threshold
    split_name = args.name or split_group
    split_label = args.label or GROUP_LABELS[split_group]
    cohort_suffix = "_newdata" if args.new else ""
    outfile = f"{split_name}_split_analysis{cohort_suffix}.md"

    rows = load_rows(spreadsheet)
    n = len(rows)
    print(f"Loaded {n} rows from {os.path.basename(spreadsheet)}.\n")
    print(f"Split rule: {split_label} >= {split_thr}\n")

    a_rows = [r for r in rows if r["counts"][split_group] >= split_thr]
    b_rows = [r for r in rows if r["counts"][split_group] <  split_thr]
    nA, nB = len(a_rows), len(b_rows)
    group_a_label = f"{split_thr}+ {split_label}"
    group_b_label = f"<{split_thr} {split_label}"
    print(f"Group A ({group_a_label}):   n = {nA}")
    print(f"Group B ({group_b_label}):    n = {nB}")
    print()

    # Compute label distributions per group
    def dist(group, labeller, key):
        vals = [labeller(r[key]) for r in group]
        counter = Counter(v for v in vals if v is not None)
        n_lab = sum(counter.values())
        n_un  = sum(1 for v in vals if v is None)
        return counter, n_lab, n_un

    cats = [
        ("EEG Quality",          label_quality,           "quality",
         ["Good", "Fair", "Poor"]),
        ("Artifact severity",    label_artifact_severity, "artifact",
         ["Mild", "Moderate", "Severe"]),
        ("Drowsiness",           label_drowsiness,        "drowsiness",
         ["Demonstrated", "Not demonstrated"]),
        ("Paroxysmal",           label_paroxysmal,        "paroxysmal",
         ["None", "Present"]),
        ("Clinical abnormality", label_abnormal,          "comments",
         ["No", "Yes"]),
    ]

    out_lines = [f"# Two-distribution analysis: {group_a_label} vs {group_b_label}\n\n"]
    cohort_tag = "n=98 validation cohort" if args.new else "n=100 training cohort"
    out_lines.append(
        f"Source: `{os.path.basename(spreadsheet)}` ({cohort_tag}).  "
        f"Split rule: column for {split_label} >= {split_thr}.\n\n")
    out_lines.append(f"- **Group A ({group_a_label}):**  n = {nA}\n")
    out_lines.append(f"- **Group B ({group_b_label}):**  n = {nB}\n\n")
    out_lines.append("---\n\n")

    print("=" * 80)
    print(f"{'Category':<22} {'Label':<22}  A(3+) %  |  B(<3) %  |  diff   p")
    print("=" * 80)

    for cat_name, labeller, key, ordered in cats:
        countA, nlabA, nunA = dist(a_rows, labeller, key)
        countB, nlabB, nunB = dist(b_rows, labeller, key)

        out_lines.append(f"## {cat_name}\n\n")
        out_lines.append(
            f"Labels parsed: Group A {nlabA}/{nA} (unparsed {nunA}), "
            f"Group B {nlabB}/{nB} (unparsed {nunB}).\n\n")
        out_lines.append(
            f"| Label | A ({group_a_label}) | B ({group_b_label}) | "
            f"Δ pct pts | p (Fisher) |\n")
        out_lines.append("|---|---|---|---|---|\n")

        # Add any labels actually observed beyond `ordered`
        seen = list(ordered) + [k for k in (list(countA) + list(countB))
                                if k not in ordered]
        for lab in seen:
            if lab not in countA and lab not in countB:
                continue
            a = countA.get(lab, 0)
            b = nlabA - a
            c = countB.get(lab, 0)
            d = nlabB - c
            pa = (a / nlabA * 100) if nlabA else 0.0
            pc = (c / nlabB * 100) if nlabB else 0.0
            p, _odds, _ = fisher_exact_2x2(a, b, c, d) \
                if (nlabA and nlabB) else (float("nan"), 0, 0)
            sign = "+" if pa > pc else ("-" if pa < pc else " ")
            print(f"{cat_name:<22} {lab:<22}  {pa:5.1f}% |  {pc:5.1f}%  |  "
                  f"{sign}{abs(pa-pc):5.1f}  p={p:.3f}")
            out_lines.append(
                f"| {lab} | {a}/{nlabA} ({pa:.1f}%) | "
                f"{c}/{nlabB} ({pc:.1f}%) | {sign}{abs(pa-pc):.1f} | "
                f"{p:.3f} |\n")
        out_lines.append("\n")
        print()

    # PDR frequency — numeric breakdown
    out_lines.append("## PDR frequency (numeric where parseable)\n\n")
    print("=" * 80)
    print("PDR frequency (numeric where parseable):")
    pdr_a = []
    pdr_b = []
    nd_a = 0; nd_b = 0
    for r in a_rows:
        pf = pdr_freq(r["background"])
        if pf is None:
            continue
        if pf[0] == "Not demonstrated":
            nd_a += 1
        else:
            pdr_a.append(pf[0])
    for r in b_rows:
        pf = pdr_freq(r["background"])
        if pf is None:
            continue
        if pf[0] == "Not demonstrated":
            nd_b += 1
        else:
            pdr_b.append(pf[0])

    def _summ(name, vals, n_nd, n_group):
        if vals:
            arr = np.array(vals)
            print(f"  {name}  n={len(arr)}  mean {arr.mean():.2f} Hz  "
                  f"median {np.median(arr):.2f}  min {arr.min():.2f}  "
                  f"max {arr.max():.2f}  Not-demo {n_nd}  unparsed "
                  f"{n_group - len(arr) - n_nd}")
            return f"n={len(arr)}, mean {arr.mean():.2f} Hz, median {np.median(arr):.2f}, range {arr.min():.2f}-{arr.max():.2f}, 'not demonstrated' {n_nd}"
        return f"no numeric, 'not demonstrated' {n_nd}"

    sa = _summ(f"A ({group_a_label})", pdr_a, nd_a, nA)
    sb = _summ(f"B ({group_b_label})", pdr_b, nd_b, nB)
    out_lines.append(f"- **A ({group_a_label}):** {sa}\n")
    out_lines.append(f"- **B ({group_b_label}):** {sb}\n\n")
    if pdr_a and pdr_b:
        # Welch t
        arr_a, arr_b = np.array(pdr_a), np.array(pdr_b)
        diff = arr_a.mean() - arr_b.mean()
        sp = (arr_a.var(ddof=1) * (len(arr_a) - 1) +
              arr_b.var(ddof=1) * (len(arr_b) - 1))
        sp /= (len(arr_a) + len(arr_b) - 2)
        d = diff / np.sqrt(max(sp, 1e-12))
        out_lines.append(
            f"Mean PDR frequency difference: A - B = {diff:+.2f} Hz "
            f"(Cohen's d = {d:+.2f}).\n\n")
        print(f"  difference A-B = {diff:+.2f} Hz (Cohen's d {d:+.2f})")

    # Example comments
    print()
    print("Example DR Comments per group (first 6 unique):")
    out_lines.append("---\n\n## Example doctor comments per group\n\n")
    for label, group in [(f"A ({group_a_label})", a_rows),
                          (f"B ({group_b_label})", b_rows)]:
        seen = []
        for r in group:
            txt = r["comments"][:160].replace("\n", " ").strip()
            if txt and txt not in seen:
                seen.append(txt)
            if len(seen) >= 8:
                break
        out_lines.append(f"### Group {label}\n\n")
        for txt in seen:
            out_lines.append(f"- {txt}\n")
        out_lines.append("\n")
        print(f"--- {label} ---")
        for txt in seen[:4]:
            print(f"  {txt!r}")
        print()

    # Mean OOB profile per group (illuminate WHY one group has 3+ Moments)
    out_lines.append("---\n\n## Mean OOB profile per group\n\n")
    out_lines.append("| Group | Std/Global | PDR | Phenotypes | Focal | Diffuse | State Shift | Total |\n")
    out_lines.append("|---|---|---|---|---|---|---|---|\n")
    for label, group in [(f"A ({group_a_label})", a_rows),
                          (f"B ({group_b_label})", b_rows)]:
        means = {k: np.mean([r["counts"][k] for r in group]) for k in
                 ["std_global", "pdr", "phenotypes", "focal", "diffuse",
                  "state_shift", "total"]}
        out_lines.append(
            f"| {label} | {means['std_global']:.2f} | {means['pdr']:.2f} | "
            f"{means['phenotypes']:.2f} | {means['focal']:.2f} | "
            f"{means['diffuse']:.2f} | {means['state_shift']:.2f} | "
            f"{means['total']:.2f} |\n")
    out_lines.append("\n")

    out_lines.append("---\n\n## Interpretation (skeleton)\n\n")
    out_lines.append(
        f"The two-group comparison asks whether '{group_a_label}' "
        "selects a clinically distinct subpopulation that the doctors "
        "describe differently.  Read the per-category tables above against "
        "the Fisher p-values:\n\n")
    out_lines.append(
        "- Cells where Group A has a notably higher percentage of a "
        f"label (and Fisher p < 0.05) mean the '{split_thr}+ {split_label}' "
        "rule is **enriching** for that label vs the rest of the cohort.\n")
    out_lines.append(
        "- Cells where Group A has notably *lower* percentage of a "
        f"label mean the rule is **screening against** that label.\n")
    out_lines.append(
        "- Cells with similar percentages (p > 0.5) mean the doctors "
        "describe the two groups indistinguishably along that "
        "dimension.\n")

    out_path = os.path.join(OUT, outfile)
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(out_lines)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
