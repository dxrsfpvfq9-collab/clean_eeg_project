"""Diagnostic for Phase D: why do the published discriminants under-perform on
the new data? Tests cohort/feature variants and per-group signal separation.

Scenarios:
  A) v2025_brainml, std_global as-is (Global STD z=2642 always OOB)
  B) v2025_brainml, std_global = STD Raw only (drop the meaningless Global STD)
  C) v2023_autoscan_192, std_global as-is (matches original study metric behavior)

For each scenario: per-outcome published-discriminant AUC. For scenario A also
print per-(outcome,group) positive/negative mean OOB + single-group AUC, to see
which expected associations exist at all.
"""
import csv
import os
import sys

import numpy as np
from sklearn.metrics import roc_auc_score

import config
import labels as L
import panel_parser as pp
import report_parser as rp

sys.path.insert(0, config.REPO_ROOT)
from process import discriminant  # noqa: E402

GROUPS = ["std_global", "pdr", "phenotypes", "focal", "diffuse", "state_shift"]


def load(version, drop_global_std=False):
    """Return (counts_list, labels_dict, scores_dict) for paired panels of a
    given version, from manifest_ec_features.csv."""
    rows = [r for r in csv.DictReader(
        open(os.path.join(config.OUT_DIR, "manifest_ec_features.csv"), encoding="utf-8"))
        if r["version"] == version and r["paired"] == "True"]
    C, Y, S = [], {o: [] for o in L.OUTCOMES}, {o: [] for o in L.OUTCOMES}
    for r in rows:
        parsed = pp.parse_panel_pdf(r["ec_panel_path"])
        z = list(parsed["zscores"])
        if drop_global_std:
            z[1] = float("nan")  # neutralize Global STD (index 1)
        counts = discriminant.compute_oob_counts(z)
        C.append([counts[g] for g in GROUPS])
        scored = {s["name"]: s["score"] for s in discriminant.compute_scores(counts)}
        rep = rp.parse_report(r["report_path"]) if r["report_path"] else {}
        age = int(r["age"]) if r["age"] not in ("", None) else None
        labs = L.all_labels(rep, age)
        for o in L.OUTCOMES:
            Y[o].append(labs[o][0]); S[o].append(scored[L.DISCRIMINANT_OF[o]])
    return (np.array(C, float), {o: np.array(Y[o]) for o in L.OUTCOMES},
            {o: np.array(S[o], float) for o in L.OUTCOMES})


def auc(y, s):
    y = np.asarray(y)
    if y.sum() == 0 or y.sum() == len(y):
        return float("nan")
    return roc_auc_score(y, s)


def disc_aucs(version, drop_global_std=False):
    C, Y, S = load(version, drop_global_std)
    n = len(C)
    out = {}
    for o in L.OUTCOMES:
        out[o] = (int(Y[o].sum()), auc(Y[o], S[o]))
    return n, out, C, Y


def main():
    print("Scenario published-discriminant AUCs (n+, AUC):\n")
    scen = [("A v2025 as-is", "v2025_brainml", False),
            ("B v2025 no-GlobalSTD", "v2025_brainml", True),
            ("C v2023 as-is", "v2023_autoscan_192", False)]
    table = {}
    for tag, ver, drop in scen:
        n, res, C, Y = disc_aucs(ver, drop)
        table[tag] = (n, res)
        if tag.startswith("A"):
            A_C, A_Y = C, Y

    hdr = f"{'outcome':16s}" + "".join(f"{t.split()[0]+'/'+t.split()[1]:>20s}" for t in [s[0] for s in scen])
    print(hdr)
    for o in L.OUTCOMES:
        line = f"{o:16s}"
        for tag, _, _ in scen:
            n, res = table[tag]
            npos, a = res[o]
            line += f"{f'n+={npos} AUC={a:.2f}':>20s}" if a == a else f"{f'n+={npos} AUC=n/a':>20s}"
        print(line)
    for tag, _, _ in scen:
        n, _ = table[tag]
        print(f"   {tag}: N={n}")

    print("\nPer-group signal separation (scenario A, v2025): "
          "pos-mean vs neg-mean OOB | single-group AUC")
    for o in L.OUTCOMES:
        y = A_Y[o]
        if y.sum() == 0:
            continue
        print(f"\n {o}  (n+={int(y.sum())}/{len(y)})")
        for gi, g in enumerate(GROUPS):
            x = A_C[:, gi]
            pm = x[y == 1].mean(); nm = x[y == 0].mean()
            try:
                a = roc_auc_score(y, x)
            except Exception:
                a = float("nan")
            flag = " *" if (a == a and abs(a - 0.5) >= 0.12) else ""
            print(f"   {g:12s} pos={pm:4.2f} neg={nm:4.2f}  AUC={a:.2f}{flag}")


if __name__ == "__main__":
    main()
