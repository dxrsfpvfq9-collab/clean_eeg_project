"""Phase D-2: direction-aware OOB features.

Splits each Brain Panel group's out-of-bounds count into HIGH (z >= +2) and LOW
(z <= -2) halves -- 12 features instead of 6 -- directly testing the paper's own
Future-Works proposal ("the exact direction of deviations ... instead of simply
counting"). The targeted hypothesis: drowsiness tracks state_shift HIGH (high
Moment-3), which the direction-blind |z| count conflates with very-stable
(low Moment-3) recordings.

For each outcome we report:
  - single-feature AUC for every directional feature (which direction separates)
  - a Moment-3-specific HIGH feature (idx 38,41,44,47) for drowsiness
  - cross-validated AUC of a re-derived classifier using 6 blind vs 12
    directional features (improvement = does direction help?)
"""
import csv
import os
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score

import config
import labels as L
import panel_parser as pp
import report_parser as rp

sys.path.insert(0, config.REPO_ROOT)
from process import discriminant  # noqa: E402

GROUPS = ["std_global", "pdr", "phenotypes", "focal", "diffuse", "state_shift"]
GI = discriminant.GROUP_INDEXES
MOMENT3_IDX = [38, 41, 44, 47]  # PDR/Beta/Theta/Delta Moment 3


def dir_features(z):
    """Return (blind6, dir12, moment3_hi) from 48 z-scores."""
    z = np.asarray(z, float)
    blind, hi, lo = [], [], []
    for g in GROUPS:
        idx = GI[g]
        zz = z[idx]
        blind.append(int(np.nansum(np.abs(zz) >= 2)))
        hi.append(int(np.nansum(zz >= 2)))
        lo.append(int(np.nansum(zz <= -2)))
    dir12 = []
    for h, l in zip(hi, lo):
        dir12 += [h, l]
    m3 = int(np.nansum(z[MOMENT3_IDX] >= 2))
    return blind, dir12, m3


DIR_NAMES = []
for g in GROUPS:
    DIR_NAMES += [f"{g}_hi", f"{g}_lo"]


def build():
    rows = list(csv.DictReader(open(os.path.join(config.OUT_DIR, "study_cohort.csv"),
                                    encoding="utf-8")))
    B, D, M3, Y = [], [], [], {o: [] for o in L.OUTCOMES}
    print(f"Building direction-aware features for {len(rows)} panels ...")
    for i, r in enumerate(rows, 1):
        parsed = pp.parse_panel_pdf(r["ec_panel_path"])
        b, d, m3 = dir_features(parsed["zscores"])
        B.append(b); D.append(d); M3.append(m3)
        rep = rp.parse_report(r["report_path"]) if r["report_path"] else {}
        age = int(r["age"]) if r["age"] not in ("", None) else None
        labs = L.all_labels(rep, age)
        for o in L.OUTCOMES:
            Y[o].append(labs[o][0])
        if i % 25 == 0:
            print(f"   {i}/{len(rows)}")
    return (np.array(B, float), np.array(D, float), np.array(M3, float),
            {o: np.array(Y[o]) for o in L.OUTCOMES})


def cv_auc(X, y):
    npos = int(y.sum())
    if npos < 4 or npos > len(y) - 4:
        return float("nan")
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    clf = LogisticRegression(max_iter=3000, class_weight="balanced", C=0.5)
    try:
        cv = StratifiedKFold(n_splits=min(5, npos), shuffle=True, random_state=0)
        return float(np.mean(cross_val_score(clf, Xs, y, cv=cv, scoring="roc_auc")))
    except Exception:
        return float("nan")


def sf_auc(x, y):
    if y.sum() == 0 or y.sum() == len(y):
        return float("nan")
    return roc_auc_score(y, x)


def main():
    B, D, M3, Y = build()
    lines = ["# Phase D-2 — Direction-aware OOB features",
             "", f"n={len(B)} EC panels. Re-derived (logistic, 5-fold CV, "
             "class-balanced). 'blind' = 6 |z|>=2 group counts; 'dir' = 12 "
             "hi/lo split.", "",
             "| Outcome | n+ | CV-AUC blind(6) | CV-AUC dir(12) | best directional feature (single-AUC) |",
             "|---|---|---|---|---|"]
    print("\n" + "=" * 80)
    print(f"{'outcome':16s} {'n+':>3} {'blind6':>7} {'dir12':>7}  best directional single feature")
    for o in L.OUTCOMES:
        y = Y[o]
        ab = cv_auc(B, y)
        ad = cv_auc(D, y)
        # single-feature AUCs for the 12 directional features
        sf = [(DIR_NAMES[j], sf_auc(D[:, j], y)) for j in range(D.shape[1])]
        sf = [(n, a) for n, a in sf if a == a]
        sf.sort(key=lambda na: -abs(na[1] - 0.5))
        best = sf[0] if sf else ("-", float("nan"))
        # drowsiness: also report the targeted Moment-3-high feature
        extra = ""
        if o == "drowsiness":
            extra = f"  [Moment3_hi single-AUC={sf_auc(M3, y):.2f}]"
        bstr = f"{best[0]} {best[1]:.2f}"
        print(f"{o:16s} {int(y.sum()):>3} {ab:>7.2f} {ad:>7.2f}  {bstr}{extra}")
        lines.append(f"| {o} | {int(y.sum())} | {ab:.2f} | {ad:.2f} | "
                     f"{best[0]} (AUC {best[1]:.2f}){extra} |")
    with open(os.path.join(config.OUT_DIR, "phase_d2_results.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\nWrote out/phase_d2_results.md")


if __name__ == "__main__":
    main()
