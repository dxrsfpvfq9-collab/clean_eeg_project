"""Phase D-3: derive OPTIMAL decision formulas on the new cohort.

Mirrors the paper's method -- find small-integer weighted combinations of the
Brain Panel OOB group counts that best predict each clinical outcome -- but adds
the honesty layer the paper lacked: a cross-validated estimate (select formula
on train folds, score the held-out fold) next to the in-sample fit, so we can
tell a real signal from an over-fit one.

Search space: weights {0..3} on 7 terms
  [std_global, pdr, phenotypes, focal, diffuse, state_shift, total].
Selection metric: ROC-AUC (ties broken toward fewer non-zero terms).
For each outcome we report the all-data formula, its in-sample AUC + Youden
sens/spec/acc, the honest CV-AUC, and the published formula for comparison.
"""
import csv
import itertools
import os
import sys

import numpy as np
from scipy.stats import rankdata
from sklearn.model_selection import StratifiedKFold

import config
import labels as L
import panel_parser as pp
import report_parser as rp

sys.path.insert(0, config.REPO_ROOT)
from process import discriminant  # noqa: E402

TERMS = ["std_global", "pdr", "phenotypes", "focal", "diffuse", "state_shift", "total"]
LABELS = {"std_global": "Std/Global", "pdr": "PDR", "phenotypes": "Phenotype",
          "focal": "Focal", "diffuse": "Diffuse", "state_shift": "State Shift",
          "total": "Total"}
WMAX = 3
# precompute all candidate weight vectors (skip all-zero)
CANDS = np.array([w for w in itertools.product(range(WMAX + 1), repeat=len(TERMS))
                  if any(w)], dtype=float)
NNZ = (CANDS != 0).sum(1)  # term count, for tie-break


def fast_auc(y, s):
    n1 = y.sum(); n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def build():
    rows = list(csv.DictReader(open(os.path.join(config.OUT_DIR, "study_cohort.csv"),
                                    encoding="utf-8")))
    X, Y = [], {o: [] for o in L.OUTCOMES}
    print(f"Building feature matrix for {len(rows)} panels ...")
    for i, r in enumerate(rows, 1):
        parsed = pp.parse_panel_pdf(r["ec_panel_path"])
        c = discriminant.compute_oob_counts(parsed["zscores"])
        X.append([c["std_global"], c["pdr"], c["phenotypes"], c["focal"],
                  c["diffuse"], c["state_shift"], c["total"]])
        rep = rp.parse_report(r["report_path"]) if r["report_path"] else {}
        age = int(r["age"]) if r["age"] not in ("", None) else None
        labs = L.all_labels(rep, age)
        for o in L.OUTCOMES:
            Y[o].append(labs[o][0])
        if i % 25 == 0:
            print(f"   {i}/{len(rows)}")
    return np.array(X, float), {o: np.array(Y[o]) for o in L.OUTCOMES}


def best_formula(X, y):
    """Exhaustive search -> (weights, auc). Best AUC, ties -> fewer terms."""
    scores = X @ CANDS.T          # (n_samples, n_cands)
    aucs = np.array([fast_auc(y, scores[:, k]) for k in range(CANDS.shape[0])])
    aucs = np.where(np.isnan(aucs), 0.0, aucs)
    # also consider the inverse direction (negative association)
    aucs = np.maximum(aucs, 1 - aucs)
    best = aucs.max()
    mask = aucs >= best - 1e-9
    k = np.where(mask)[0][np.argmin(NNZ[mask])]
    return CANDS[k], aucs[k], (fast_auc(y, X @ CANDS[k]) < 0.5)


def youden(y, s):
    thr = np.unique(s)
    best = None
    for t in thr:
        pred = (s >= t).astype(int)
        tp = ((pred == 1) & (y == 1)).sum(); tn = ((pred == 0) & (y == 0)).sum()
        fp = ((pred == 1) & (y == 0)).sum(); fn = ((pred == 0) & (y == 1)).sum()
        sens = tp / (tp + fn) if tp + fn else 0
        spec = tn / (tn + fp) if tn + fp else 0
        j = sens + spec - 1
        if best is None or j > best[0]:
            best = (j, sens, spec, (tp + tn) / len(y), t)
    return best  # j, sens, spec, acc, thr


def cv_auc(X, y, n_pos):
    if n_pos < 10:
        return float("nan")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    test_aucs = []
    for tr, te in cv.split(X, y):
        w, _, inv = best_formula(X[tr], y[tr])
        s = X[te] @ w
        a = fast_auc(y[te], s)
        if a == a:
            test_aucs.append(1 - a if inv else a)
    return float(np.mean(test_aucs)) if test_aucs else float("nan")


def fmt(w, inv):
    parts = [f"{int(wi)}*{LABELS[t]}" for wi, t in zip(w, TERMS) if wi]
    s = " + ".join(parts)
    return ("-(" + s + ")") if inv else s


def main():
    X, Y = build()
    pub = {d["name"]: discriminant._formula(d["weights"]) for d in discriminant.DISCRIMINANTS}
    lines = ["# Phase D-3 — Optimal decision formulas derived on the new data",
             "", f"n={len(X)} EC panels. Search: integer weights 0-3 over "
             "[Std/Global, PDR, Phenotype, Focal, Diffuse, State Shift, Total]. "
             "In-sample AUC is optimistic (best of many); CV-AUC is the honest "
             "generalization estimate.", "",
             "| Outcome | n+ | Derived formula (this data) | In-sample AUC | "
             "Youden sens/spec/acc | CV-AUC | Published formula |",
             "|---|---|---|---|---|---|---|"]
    print("\n" + "=" * 90)
    print(f"{'outcome':16s} {'n+':>3} {'inAUC':>6} {'CVauc':>6}  derived formula")
    for o in L.OUTCOMES:
        y = Y[o]; npos = int(y.sum())
        if npos < 3 or npos > len(y) - 3:
            print(f"{o:16s} {npos:>3}   --     --   (too few positives)")
            lines.append(f"| {o} | {npos} | (too few positives) | - | - | - | {pub[L.DISCRIMINANT_OF[o]]} |")
            continue
        w, a_in, inv = best_formula(X, y)
        s = X @ w
        if inv:
            s = -s
        j, sens, spec, acc, thr = youden(y, s)
        cva = cv_auc(X, y, npos)
        f = fmt(w, inv)
        print(f"{o:16s} {npos:>3} {a_in:>6.2f} {('%.2f'%cva) if cva==cva else '  n/a':>6}  {f}")
        lines.append(f"| {o} | {npos} | `{f}` | {a_in:.2f} | "
                     f"{100*sens:.0f}/{100*spec:.0f}/{100*acc:.0f}% | "
                     f"{('%.2f'%cva) if cva==cva else 'n/a'} | {pub[L.DISCRIMINANT_OF[o]]} |")
    lines += ["", "Reading this table:",
              "- A formula prefixed with `-(...)` means the outcome is associated "
              "with FEWER such OOB metrics (inverse), e.g. drowsiness.",
              "- Where CV-AUC << in-sample AUC, the formula is largely over-fit "
              "(same caution that applies to the published Table-4 numbers).",
              "- `Total` is the sum of the six groups; when it dominates, the "
              "outcome tracks overall OOB burden rather than any specific group."]
    with open(os.path.join(config.OUT_DIR, "optimal_formulas.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\nWrote out/optimal_formulas.md")


if __name__ == "__main__":
    main()
