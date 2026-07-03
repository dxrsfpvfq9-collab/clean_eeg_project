"""Phase D: validate the published discriminants on the new cohort.

For each of the six clinical outcomes:
  1. Build binary ground truth from the Doctor's Report (labels.py).
  2. Score every case with the PUBLISHED weighted discriminant
     (process/discriminant.py) and measure ROC-AUC + the best achievable
     sensitivity/specificity/accuracy, compared against the paper's Table 4.
  3. Re-derive weights on the new data (logistic regression on the 6 OOB group
     counts) and report cross-validated AUC + which groups carry signal.

Outputs: out/phase_d_results.md and out/validation_results.xlsx
"""
import csv
import os
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold, cross_val_score

import config
import labels as L
import panel_parser as pp
import report_parser as rp

sys.path.insert(0, config.REPO_ROOT)
from process import discriminant  # noqa: E402

GROUPS = ["std_global", "pdr", "phenotypes", "focal", "diffuse", "state_shift"]


def build_dataset():
    rows = list(csv.DictReader(open(os.path.join(config.OUT_DIR, "study_cohort.csv"),
                                    encoding="utf-8")))
    X, Y, CONF, SCORES = [], {o: [] for o in L.OUTCOMES}, {o: [] for o in L.OUTCOMES}, \
        {o: [] for o in L.OUTCOMES}
    pub = {d["name"]: d for d in discriminant.DISCRIMINANTS}
    print(f"Building Phase D dataset for {len(rows)} cohort panels ...")
    for i, row in enumerate(rows, 1):
        parsed = pp.parse_panel_pdf(row["ec_panel_path"])
        counts = discriminant.compute_oob_counts(parsed["zscores"])
        X.append([counts[g] for g in GROUPS])
        scored = {s["name"]: s["score"] for s in discriminant.compute_scores(counts)}
        rep = rp.parse_report(row["report_path"]) if row["report_path"] else {}
        age = int(row["age"]) if row["age"] not in ("", None) else None
        labs = L.all_labels(rep, age)
        for o in L.OUTCOMES:
            v, conf = labs[o]
            Y[o].append(v)
            CONF[o].append(conf)
            SCORES[o].append(scored[L.DISCRIMINANT_OF[o]])
        if i % 25 == 0:
            print(f"   {i}/{len(rows)}")
    return (np.array(X, float), {o: np.array(Y[o]) for o in L.OUTCOMES},
            {o: np.array(CONF[o]) for o in L.OUTCOMES},
            {o: np.array(SCORES[o], float) for o in L.OUTCOMES}, pub)


def best_operating_point(y, score):
    """ROC-AUC + Youden-optimal sens/spec/acc for a fixed score classifier."""
    if y.sum() == 0 or y.sum() == len(y):
        return None
    auc = roc_auc_score(y, score)
    fpr, tpr, thr = roc_curve(y, score)
    j = tpr - fpr
    k = int(np.argmax(j))
    t = thr[k]
    pred = (score >= t).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum()); fn = int(((pred == 0) & (y == 1)).sum())
    sens = tp / (tp + fn) if tp + fn else float("nan")
    spec = tn / (tn + fp) if tn + fp else float("nan")
    acc = (tp + tn) / len(y)
    return {"auc": auc, "thr": float(t), "sens": sens, "spec": spec, "acc": acc,
            "tp": tp, "tn": tn, "fp": fp, "fn": fn}


def rederive(y, X):
    """Logistic regression on the 6 group counts; CV-AUC + standardized coefs."""
    npos = int(y.sum())
    if npos < 3 or npos > len(y) - 3:
        return None
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced")
    nsplit = min(5, npos)
    try:
        cv = StratifiedKFold(n_splits=nsplit, shuffle=True, random_state=0)
        cvauc = float(np.mean(cross_val_score(clf, Xs, y, cv=cv, scoring="roc_auc")))
    except Exception:
        cvauc = float("nan")
    clf.fit(Xs, y)
    coefs = dict(zip(GROUPS, clf.coef_[0].round(2)))
    top = sorted(coefs.items(), key=lambda kv: -abs(kv[1]))[:3]
    return {"cv_auc": cvauc, "coefs": coefs,
            "top_groups": ", ".join(f"{g}({w:+.2f})" for g, w in top)}


def main():
    X, Y, CONF, SCORES, pub = build_dataset()
    n = len(X)
    results = []
    for o in L.OUTCOMES:
        y = Y[o]
        d = pub[L.DISCRIMINANT_OF[o]]
        op = best_operating_point(y, SCORES[o])
        rd = rederive(y, X)
        results.append({
            "outcome": o, "discriminant": d["name"], "n": n,
            "n_pos": int(y.sum()), "n_lowconf": int((CONF[o] == "low").sum()),
            "pub_sens": d["sens"], "pub_spec": d["spec"], "pub_acc": d["acc"],
            "formula": discriminant._formula(d["weights"]),
            "auc": op["auc"] if op else float("nan"),
            "sens": op["sens"] if op else float("nan"),
            "spec": op["spec"] if op else float("nan"),
            "acc": op["acc"] if op else float("nan"),
            "thr": op["thr"] if op else float("nan"),
            "cv_auc": rd["cv_auc"] if rd else float("nan"),
            "top_groups": rd["top_groups"] if rd else "(too few positives)",
        })
    write_outputs(results, n)
    print_console(results, n)


def _pct(x):
    return f"{100*x:.0f}%" if x == x else "n/a"


def write_outputs(results, n):
    md = [f"# Phase D — Validation of published discriminants (n={n})", "",
          "Published weights applied to the new cohort as a fixed classifier; "
          "AUC and Youden-optimal operating point shown next to the paper's "
          "Table-4 values. `re-derived CV-AUC` fits new weights on the 6 OOB "
          "group counts (5-fold stratified).", "",
          "| Outcome | Discriminant (published formula) | n+ | Pub sens/spec/acc | "
          "New AUC | New sens/spec/acc @Youden | Re-derived CV-AUC | Top groups (new fit) |",
          "|---|---|---|---|---|---|---|---|"]
    for r in results:
        md.append(
            f"| {r['outcome']} | {r['discriminant']}: {r['formula']} | {r['n_pos']} | "
            f"{r['pub_sens']}/{r['pub_spec']}/{r['pub_acc']}% | {_pct(r['auc'])} | "
            f"{_pct(r['sens'])}/{_pct(r['spec'])}/{_pct(r['acc'])} | {_pct(r['cv_auc'])} | "
            f"{r['top_groups']} |")
    md += ["", "Notes:",
           "- Positive classes are small for paroxysmal and clinical abnormality; "
           "AUC there is informative but unstable.",
           "- `pdr_freq_abnorm` ground truth depends on parsing space-corrupted "
           "PDR-Hz prose and is the lowest-confidence label.",
           "- Operating point is Youden-optimal (best achievable); the paper's "
           "single point may sit elsewhere on the same ROC."]
    with open(os.path.join(config.OUT_DIR, "phase_d_results.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")

    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook(); ws = wb.active; ws.title = "Validation"
    cols = ["outcome", "discriminant", "formula", "n", "n_pos", "n_lowconf",
            "pub_sens", "pub_spec", "pub_acc", "auc", "sens", "spec", "acc",
            "thr", "cv_auc", "top_groups"]
    ws.append(cols)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in results:
        ws.append([r.get(k) for k in cols])
    wb.save(os.path.join(config.OUT_DIR, "validation_results.xlsx"))


def print_console(results, n):
    print("\n" + "=" * 78)
    print(f"PHASE D VALIDATION  (n={n} EC panels, v2025_brainml)")
    print("=" * 78)
    print(f"{'outcome':16s} {'n+':>3} {'pub_sens':>8} {'AUC':>5} "
          f"{'sens':>5} {'spec':>5} {'acc':>5} {'CVauc':>6}")
    for r in results:
        print(f"{r['outcome']:16s} {r['n_pos']:>3} {str(r['pub_sens'])+'%':>8} "
              f"{_pct(r['auc']):>5} {_pct(r['sens']):>5} {_pct(r['spec']):>5} "
              f"{_pct(r['acc']):>5} {_pct(r['cv_auc']):>6}")
    print("\nWrote out/phase_d_results.md and out/validation_results.xlsx")


if __name__ == "__main__":
    main()
