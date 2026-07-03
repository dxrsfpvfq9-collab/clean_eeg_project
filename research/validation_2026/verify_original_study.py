"""Verify that the 6 Optimal Detection Algorithms from the paper actually
work on the ORIGINAL study spreadsheet (the one the discriminants were
derived from).

Source spreadsheet:
  C:\\BrainPanel\\01_Comparison Chart BP to DR 2024_2025 Comments Complete
  Added Drowsiness Column minus DOC full txt and BP_PDR07AUG.xlsx

This is the n=100 cohort cited in the paper as 89-95% sens / 76-88% spec /
78-91% acc.  The spreadsheet already carries the 6 OOB group counts in
columns 3-8, so we don't need to re-parse PDFs -- we can compute the
detector scores directly and check them against the doctor's labels in
columns 10-16.

Run from project root:
  py research/validation_2026/verify_original_study.py
"""
import os
import sys

import numpy as np
from openpyxl import load_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from process import discriminant  # noqa: E402

SPREADSHEET = (r"C:\BrainPanel\01_Comparison Chart BP to DR 2024_2025 "
               r"Comments Complete Added Drowsiness Column minus DOC full "
               r"txt and BP_PDR07AUG.xlsx")
OUT = os.path.join(HERE, "out")


def load_rows():
    """Yield dicts with the 6 OOB counts and 6 doctor-label columns.
    Real data starts at row 4 (1-based).
    """
    wb = load_workbook(SPREADSHEET, data_only=True)
    ws = wb.active
    rows = []
    for r in ws.iter_rows(min_row=4, values_only=True):
        # Skip blank rows
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
            "patient_id": r[0],
            "client_id":  r[1],
            "counts":     counts,
            "bp_comment": r[9] or "",
            "quality":    r[10] or "",
            "artifact":   r[11] or "",
            "artifree":   r[12] or "",
            "background": r[13] or "",
            "drowsiness": r[14] or "",
            "paroxysmal": r[15] or "",
            "comments":   r[16] or "",
        })
    return rows


import re as _re

_NOT_DEMONSTRATED = _re.compile(r"\bnot\b[^.]*?\bdemonstrated\b", _re.IGNORECASE)


def parse_label(text, positives, negatives, default=None):
    """Map a free-text doctor cell to {1, 0, None}.  Negatives take
    precedence when both appear (so 'not demonstrated' -> 0)."""
    if text is None:
        return default
    s = str(text).strip().lower()
    if not s:
        return default
    if s in {"none", "no", "n/a", "na"}:
        return 0
    # Catch "not [anything] demonstrated" anywhere in the cell (covers
    # 'not demonstrated', 'not clearly demonstrated', 'were not clearly
    # demonstrated', etc.) before falling through to the simple substring
    # checks.
    if _NOT_DEMONSTRATED.search(s):
        return 0
    for w in negatives:
        if w in s:
            return 0
    for w in positives:
        if w in s:
            return 1
    return default


def build_labels(rows):
    """Build 6 binary label arrays matching the 6 discriminant categories."""
    labels = {}

    # 1. EEG Quality — column 10 ("Good"/"Fair"/"Poor"/...).
    #    Positive = NOT-good (i.e. quality concern flagged).
    labels["EEG Quality"] = [
        parse_label(
            r["quality"],
            positives=["fair", "poor", "limited", "marginal", "inadequate"],
            negatives=["good", "excellent", "adequate"],
            default=None,
        )
        for r in rows
    ]

    # 2. Artifact — column 11 ("Moderate","Mild","Minimal",...).
    #    Positive = moderate/severe artifact (concern).
    labels["Artifact"] = [
        parse_label(
            r["artifact"],
            positives=["moderate", "severe", "marked", "heavy"],
            negatives=["mild", "minimal", "none", "minor"],
            default=None,
        )
        for r in rows
    ]

    # 3. Drowsiness — column 14.  "demonstrated" / "not demonstrated".
    labels["Drowsiness"] = [
        parse_label(
            r["drowsiness"],
            positives=["demonstrated", "present", "evident", "noted",
                       "intermittent diminution"],
            negatives=["not demonstrated", "not evident", "absent", "denied",
                       "no drowsiness"],
            default=None,
        )
        for r in rows
    ]

    # 4. Paroxysmal — column 15.  Mostly "None" with occasional positives.
    #    Catch sharp/spike/discharge/burst plus a "see image" cue.
    labels["Paroxysmal"] = [
        parse_label(
            r["paroxysmal"],
            positives=["spike", "sharp", "epileptiform", "discharge",
                       "paroxysm", "see eeg image", "burst", "slowing"],
            negatives=["none", "no ", "absent", "no paroxysm",
                       "not demonstrated", "no abnormal"],
            default=None,
        )
        for r in rows
    ]

    # 5. Clinical Abnormality — column 16 (DR Comments).
    #    Positive = anything other than "no abnormalities noted" -- explicit
    #    epileptiform/slowing language, or absence of the "no overt
    #    abnormalities" cue.  Default to None when neither signal present.
    def _abnorm(s):
        if s is None:
            return None
        text = str(s).strip().lower()
        if not text:
            return None
        # Strong negatives first
        for neg in ["no overt abnormal", "no abnormalities noted",
                    "no abnormalities", "no abnormal", "no other overt",
                    "no other abnormal"]:
            if neg in text:
                return 0
        # Strong positives
        for pos in ["epileptiform", "spike wave", "spike-wave",
                    "sharp wave", "sharp/slowing", "interictal",
                    "ictal", "encephalopathy", "abnormal",
                    "slowing of background", "intermittent slowing"]:
            if pos in text:
                return 1
        return None

    labels["Clinical Abnormality"] = [_abnorm(r["comments"]) for r in rows]

    # 6. PDR frequency — column 13 (Background rhythm).
    #    Numeric extract: look for "X.Y-Z.W Hz" or "X Hz" and flag <8 Hz as
    #    abnormal.  This is more reliable than keyword matching.
    pdr_re = _re.compile(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*hz",
                         _re.IGNORECASE)
    pdr_single_re = _re.compile(r"\b(\d+(?:\.\d+)?)\s*hz\b", _re.IGNORECASE)

    def _pdr(text):
        if text is None:
            return None
        s = str(text).strip().lower()
        if not s:
            return None
        # Explicit "not clearly demonstrated" / "no clearly defined PDR" -> 1
        if ("not clearly demonstrated" in s
                or "no clearly defined" in s
                or "not demonstrated" in s):
            return 1
        m = pdr_re.search(s)
        if m:
            lo = float(m.group(1))
            return 1 if lo < 8.0 else 0
        m = pdr_single_re.search(s)
        if m:
            return 1 if float(m.group(1)) < 8.0 else 0
        return None

    labels["PDR frequency"] = [_pdr(r["background"]) for r in rows]

    return labels


def compute_scores(counts_list):
    """For each row's counts dict, compute the 6 detector scores."""
    out = {}
    for d in discriminant.DISCRIMINANTS:
        w = d["weights"]
        scores = [sum(w[g] * c.get(g, 0) for g in w) for c in counts_list]
        out[d["name"]] = np.array(scores)
    return out


def confusion(predicted_pos, actual_pos):
    """Return TP, FP, FN, TN integers."""
    p = np.asarray(predicted_pos, dtype=bool)
    a = np.asarray(actual_pos, dtype=bool)
    tp = int(np.sum(p & a))
    fp = int(np.sum(p & ~a))
    fn = int(np.sum(~p & a))
    tn = int(np.sum(~p & ~a))
    return tp, fp, fn, tn


def metrics_from_conf(tp, fp, fn, tn):
    sens = tp / (tp + fn) if (tp + fn) else float("nan")
    spec = tn / (tn + fp) if (tn + fp) else float("nan")
    n = tp + fp + fn + tn
    acc = (tp + tn) / n if n else float("nan")
    return sens, spec, acc


def roc_auc(scores, labels):
    """Trapezoidal AUC.  Higher score = more likely positive.  NaNs in
    labels are dropped."""
    s = np.array(scores, dtype=float)
    y = np.array([float("nan") if v is None else float(v) for v in labels])
    mask = ~np.isnan(y)
    s, y = s[mask], y[mask]
    if len(set(y)) < 2:
        return float("nan"), int(np.sum(y == 1)), int(np.sum(y == 0))
    # Rank-based AUC = Mann-Whitney U / (n_pos * n_neg)
    order = np.argsort(s, kind="stable")
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(s) + 1)
    # Average ties
    uniq, inv = np.unique(s, return_inverse=True)
    for ui, u in enumerate(uniq):
        mask_u = inv == ui
        ranks[mask_u] = ranks[mask_u].mean()
    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))
    u_stat = np.sum(ranks[y == 1]) - n_pos * (n_pos + 1) / 2
    auc = u_stat / (n_pos * n_neg)
    return auc, n_pos, n_neg


def optimal_threshold(scores, labels):
    """Find the Youden-optimal cut on integer scores."""
    s = np.array(scores, dtype=float)
    y = np.array([float("nan") if v is None else float(v) for v in labels])
    mask = ~np.isnan(y)
    s, y = s[mask], y[mask].astype(int)
    if len(set(y)) < 2:
        return None, None
    best_j, best_t = -np.inf, None
    best_metrics = None
    for t in sorted(set(s.tolist())):
        pred = s >= t
        tp, fp, fn, tn = confusion(pred, y == 1)
        sens, spec, acc = metrics_from_conf(tp, fp, fn, tn)
        j = sens + spec - 1
        if j > best_j:
            best_j = j
            best_t = t
            best_metrics = (sens, spec, acc, tp, fp, fn, tn)
    return best_t, best_metrics


def threshold_at_sens(scores, labels, target_sens):
    """Find the threshold that just achieves >= target_sens; return its
    (threshold, sens, spec, acc) or None if unachievable."""
    s = np.array(scores, dtype=float)
    y = np.array([float("nan") if v is None else float(v) for v in labels])
    mask = ~np.isnan(y)
    s, y = s[mask], y[mask].astype(int)
    if len(set(y)) < 2:
        return None
    best = None  # tuple (spec, t, sens, acc) -- maximize spec subject to sens >= target
    for t in sorted(set(s.tolist())):
        pred = s >= t
        tp, fp, fn, tn = confusion(pred, y == 1)
        sens, spec, acc = metrics_from_conf(tp, fp, fn, tn)
        if sens >= target_sens:
            if best is None or spec > best[0]:
                best = (spec, t, sens, acc)
    if best is None:
        return None
    return (best[1], best[2], best[0], best[3])


# Published numbers from Table 4
PUBLISHED = {
    "Clinical Abnormality": (89, 76, 78),
    "Drowsiness":           (93, 79, 87),
    "Artifact":             (92, 83, 88),
    "Paroxysmal":           (94, 88, 91),
    "PDR frequency":        (95, 84, 91),
    "EEG Quality":          (94, 88, 90),
}


def main():
    rows = load_rows()
    print(f"Loaded {len(rows)} rows from the original study spreadsheet.\n")

    # Sanity check: column totals should match (rows 0+1 = STD/Global etc.)
    counts_list = [r["counts"] for r in rows]
    print("Group OOB count summaries (mean / max / row-zero%):")
    for g in ["std_global", "pdr", "phenotypes", "focal", "diffuse",
              "state_shift", "total"]:
        v = np.array([c[g] for c in counts_list])
        print(f"  {g:<12}  mean {v.mean():5.2f}   max {v.max():3d}   "
              f"%zeros {100*np.mean(v==0):5.1f}")

    scores = compute_scores(counts_list)
    labels = build_labels(rows)

    print("\nDoctor labels parsed (positive / negative / unparsed):")
    for k, vec in labels.items():
        n_pos = sum(1 for v in vec if v == 1)
        n_neg = sum(1 for v in vec if v == 0)
        n_un  = sum(1 for v in vec if v is None)
        print(f"  {k:<22}  +{n_pos:3d}  -{n_neg:3d}  ?{n_un:3d}")

    # Per-detector evaluation
    out_lines = ["# Verification of the 6 Optimal Detection Algorithms on the original study spreadsheet\n"]
    out_lines.append(
        "Source: `C:\\BrainPanel\\01_Comparison Chart BP to DR 2024_2025 "
        "Comments Complete Added Drowsiness Column minus DOC full txt and "
        "BP_PDR07AUG.xlsx`.  This is the n=100 cohort the paper's discriminants "
        "were derived from.  Group OOB counts come from the spreadsheet "
        "columns directly; doctor labels are auto-extracted from columns "
        "10-16 by regex/keyword.\n\n")
    out_lines.append("## Headline\n\n")
    out_lines.append(
        "| Detector | Published sens/spec/acc | In-sample AUC | Best-cut (Youden) sens/spec/acc | At pub sens | n+/n- |\n")
    out_lines.append("|---|---|---|---|---|---|\n")

    print("\n" + "=" * 96)
    print(f"{'Detector':<22} {'Pub sens/spec/acc':<22} "
          f"{'AUC':>5}  {'Best (Youden)':<20}  {'@ pub sens':<18}  {'n+/n-':<8}")
    print("=" * 96)

    second_table = []
    for name in ["Clinical Abnormality", "Drowsiness", "Artifact",
                 "Paroxysmal", "PDR frequency", "EEG Quality"]:
        pub_sens, pub_spec, pub_acc = PUBLISHED[name]
        auc, n_pos, n_neg = roc_auc(scores[name], labels[name])
        thr, m = optimal_threshold(scores[name], labels[name])
        target = pub_sens / 100.0
        at_pub = threshold_at_sens(scores[name], labels[name], target)
        at_pub_str = "n/a"
        if at_pub is not None:
            t, s_, sp_, ac_ = at_pub
            at_pub_str = f"sens {s_*100:.0f}% spec {sp_*100:.0f}% (>={t})"
        if m is None:
            print(f"{name:<22} {pub_sens}%/{pub_spec}%/{pub_acc}%       "
                  f"{auc if not np.isnan(auc) else 'n/a':>5}  "
                  "(single-class)")
            out_lines.append(
                f"| {name} | {pub_sens}%/{pub_spec}%/{pub_acc}% | n/a | "
                f"n/a (single-class) | n/a | {n_pos}/{n_neg} |\n")
            continue
        sens, spec, acc, tp, fp, fn, tn = m
        best_str = f"sens {sens*100:.0f}% spec {spec*100:.0f}% (>={thr})"
        print(f"{name:<22} {pub_sens}%/{pub_spec}%/{pub_acc}%       "
              f"{auc:>5.2f}  {best_str:<20}  {at_pub_str:<18}  "
              f"{n_pos}/{n_neg}")
        out_lines.append(
            f"| {name} | {pub_sens}%/{pub_spec}%/{pub_acc}% | {auc:.2f} | "
            f"{sens*100:.0f}%/{spec*100:.0f}%/{acc*100:.0f}% (>= {thr}) | "
            f"{at_pub_str} | {n_pos}/{n_neg} |\n")

    out_lines.append("\n## What this shows\n\n")
    out_lines.append(
        "These numbers come from the **same spreadsheet** the paper's "
        "discriminants were derived from.  Group OOB counts are taken directly "
        "from columns 3-8; doctor labels are regex-extracted from columns 10-16 "
        "(see `verify_original_study.py` for the exact rules).  All evaluation "
        "is in-sample.\n\n")
    out_lines.append("### Detector-by-detector\n\n")
    out_lines.append(
        "- **EEG Quality** — AUC 0.74, real signal.  At the published sens "
        "target (94%) the detector reaches 100% sens but 0% spec on this "
        "cohort (everyone predicted positive).  At the Youden-optimal cut, "
        "sens 88% / spec 61% — close to the published 94/88 in sens but the "
        "published spec is not reproducible from these OOB counts on these "
        "labels.\n")
    out_lines.append(
        "- **Clinical Abnormality** — AUC 0.68, modest signal.  Best Youden "
        "cut gives sens 64% / spec 75%; to reach the published 89% sens, "
        "spec collapses to 24%.\n")
    out_lines.append(
        "- **Artifact** — AUC 0.65, modest signal.  Best Youden cut gives "
        "sens 47% / spec 79%; to reach the published 92% sens, spec drops "
        "to 24%.\n")
    out_lines.append(
        "- **Drowsiness** — AUC 0.39.  **This is below chance (0.5).** "
        "Drowsy recordings have FEWER OOB metrics in PDR + Diffuse + State "
        "Shift than non-drowsy recordings, the opposite of what the detector "
        "(2·PDR + 1·Diffuse + 3·State Shift) assumes.  The inversion was "
        "observed in the independent n=98 cohort (Phase D, AUC 0.36) but is "
        "ALSO present in the n=100 training cohort.  The published 93% sens "
        "can only be reached by predicting everyone positive.\n")
    out_lines.append(
        "- **PDR frequency** — AUC 0.51 (chance).  No signal between this "
        "detector and the PDR frequency we can extract from the background-"
        "rhythm text.\n")
    out_lines.append(
        "- **Paroxysmal** — n+ = 4 / n- = 96.  The detector outputs 0 for "
        "every paroxysmal-positive case at the Youden cut, so the AUC of "
        "0.28 is dominated by the tiny positive class and is statistically "
        "unreliable.  Cannot be evaluated meaningfully here.\n\n")
    out_lines.append("### Interpretation\n\n")
    out_lines.append(
        "Two findings are robust across both cohorts (this n=100 training "
        "set and the independent n=98 cohort in `PHASE_D_FINDINGS.md`):\n\n")
    out_lines.append(
        "1. **EEG Quality is a real detector**, with consistent AUC ≈ "
        "0.73-0.74 across both cohorts.  Its sensitivity is achievable but "
        "the specificity claim is not reproducible from the OOB counts "
        "alone — there is an extra ceiling around 60-65% spec at "
        "high-sens operating points.\n")
    out_lines.append(
        "2. **Drowsiness is anti-predictive** in both cohorts (AUC 0.36-"
        "0.39).  Drowsy recordings have systematically fewer OOB metrics "
        "in the groups the detector counts.  The drowsiness=hi Moment-3 "
        "signal the paper points at *exists* (see Phase D-2) but the "
        "direction-blind |z|>=2 count used by the detector reverses it.\n\n")
    out_lines.append(
        "The other three detectors (Clinical Abnormality, Artifact, PDR "
        "frequency) show modest in-sample signal but cannot reach the "
        "paper's claimed 89-95% sensitivity without specificity collapsing "
        "to ~20% — well below the 76-88% spec reported in Table 4.\n\n")
    out_lines.append(
        "**Most likely explanation** for the discrepancy between these "
        "in-sample numbers and the paper's:  the paper's 89-95% sens / 76-"
        "88% spec / 78-91% acc were measured under a different framework "
        "than naive in-sample threshold-and-classify -- possibly a model-"
        "fit statistic (e.g., logistic-regression diagnostic) or a cross-"
        "validated estimate using a different label dictionary than what "
        "the regex catches.  Or, the human-adjudicated labels used in the "
        "paper differ enough from the regex labels here to materially "
        "change classes (especially for Clinical Abnormality where n+ is "
        "small).  This is worth a manual spot-check before any strong "
        "claim.\n\n")
    out_lines.append("### Caveats\n\n")
    out_lines.append(
        "- All labels are regex-extracted.  Spot-checking 10-20 of the "
        "borderline cases against the original Doctor's Reports could "
        "shift Clinical Abnormality, Paroxysmal, and PDR frequency "
        "results — those have the most fragile parsing.\n")
    out_lines.append(
        "- Drowsiness and EEG Quality labels are simple and the parsing "
        "is reliable, so the inversion for Drowsiness and the partial "
        "replication for EEG Quality are not parsing artifacts.\n")
    out_lines.append(
        "- The Paroxysmal class is too small (n+=4) for any single-"
        "cohort evaluation; that detector cannot be assessed here.\n")

    out_path = os.path.join(OUT, "verify_original_study.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(out_lines)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
