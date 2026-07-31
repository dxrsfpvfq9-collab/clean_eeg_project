"""
Task 2 -- re-derive the six discriminants on the EMPIRICAL AXES.

Phase D showed the paper's a-priori-group weights don't generalize (AUC
0.36-0.73) and that re-fitting logistic weights on the 6 a-priori GROUP
counts also tops out ~0.73.  Here we swap the feature basis: score every
cohort panel on the 6 covariance-derived axes (panel_signature.py) and ask,
per outcome, (a) which single axis best separates it (interpretable,
low-overfit) and (b) does a multivariate fit on the 6 AXES beat the 6
a-priori GROUPS out of sample (same 5-fold CV as Phase D).

Run: py axis_discriminants.py    (parses the 98 cohort PDFs; ~1 min)
"""
import csv, os, sys, json, warnings
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
warnings.filterwarnings("ignore")

import config, labels as L, panel_parser as pp, report_parser as rp
sys.path.insert(0, config.REPO_ROOT)
from process import discriminant                       # noqa: E402
from panel_signature import AXIS_NAMES, NAXES          # noqa: E402

GROUPS = ["std_global", "pdr", "phenotypes", "focal", "diffuse", "state_shift"]
OUTS = "out_structure"
MODEL = json.load(open(os.path.join(OUTS, "axis_model.json")))
ASSIGN = np.array(MODEL["assign"]); SIGN = np.array(MODEL["sign"])
AX_MU = np.array(MODEL["ax_mu"]); AX_SD = np.array(MODEL["ax_sd"])

def axis_scores_from_z(zscores):
    """48 panel z-scores -> 6 axis z-scores (NaN axis -> 0 = population mean)."""
    z = np.asarray(zscores, float); out = np.zeros(NAXES)
    for j in range(NAXES):
        m = np.where(ASSIGN == j)[0]
        raw = np.nanmean(SIGN[m] * z[m])
        out[j] = 0.0 if not np.isfinite(raw) else (raw - AX_MU[j]) / AX_SD[j]
    return out

def build():
    rows = list(csv.DictReader(open(os.path.join(config.OUT_DIR, "study_cohort.csv"),
                                    encoding="utf-8")))
    Xg, Xa, Y = [], [], {o: [] for o in L.OUTCOMES}
    print(f"Parsing {len(rows)} cohort panels ...")
    for i, row in enumerate(rows, 1):
        parsed = pp.parse_panel_pdf(row["ec_panel_path"])
        z = parsed["zscores"]
        counts = discriminant.compute_oob_counts(z)
        Xg.append([counts[g] for g in GROUPS])
        Xa.append(axis_scores_from_z(z))
        rep = rp.parse_report(row["report_path"]) if row["report_path"] else {}
        age = int(row["age"]) if row["age"] not in ("", None) else None
        labs = L.all_labels(rep, age)
        for o in L.OUTCOMES:
            Y[o].append(labs[o][0])
        if i % 25 == 0: print(f"   {i}/{len(rows)}")
    return (np.array(Xg, float), np.array(Xa, float),
            {o: np.array(Y[o]) for o in L.OUTCOMES})

def cv_auc(X, y):
    npos = int(y.sum())
    if npos < 3 or npos > len(y) - 3: return None
    k = min(5, npos, len(y) - npos)
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=1.0))
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=0)
    return float(np.mean(cross_val_score(clf, X, y, cv=skf, scoring="roc_auc")))

if __name__ == "__main__":
    Xg, Xa, Y = build()
    print(f"\n{'Outcome':<16}{'npos':>5} | {'best axis (univ AUC)':<34}"
          f"{'AXES cv':>8}{'GROUPS cv':>10}")
    print("-" * 84)
    summary = []
    for o in L.OUTCOMES:
        y = Y[o]; npos = int(y.sum())
        # univariate AUC of each axis (signed; <0.5 = inverted/protective)
        univ = []
        if 0 < npos < len(y):
            for j in range(NAXES):
                try: univ.append(roc_auc_score(y, Xa[:, j]))
                except Exception: univ.append(0.5)
            jb = int(np.argmax([max(a, 1 - a) for a in univ]))
            a = univ[jb]; disp = f"{AXIS_NAMES[jb]} {a:.2f}" + ("*inv" if a < 0.5 else "")
        else:
            disp = "(class too small)"; jb = -1
        auc_ax = cv_auc(Xa, y); auc_gp = cv_auc(Xg, y)
        f_ax = f"{auc_ax:.2f}" if auc_ax else "  -"
        f_gp = f"{auc_gp:.2f}" if auc_gp else "  -"
        print(f"{o:<16}{npos:>5} | {disp:<34}{f_ax:>8}{f_gp:>10}")
        summary.append((o, npos, jb, univ if jb >= 0 else None, auc_ax, auc_gp))

    print("\n=== per-axis univariate AUC (rows=outcomes, cols=axes) ===")
    print("outcome".ljust(16) + "".join(f"A{j}".rjust(7) for j in range(NAXES)))
    for o, npos, jb, univ, _, _ in summary:
        if univ is None:
            print(o.ljust(16) + "   (class too small)"); continue
        print(o.ljust(16) + "".join(f"{univ[j]:+.2f}"[:6].rjust(7) for j in range(NAXES)))
    print("\naxes: " + " | ".join(f"A{j}={AXIS_NAMES[j]}" for j in range(NAXES)))
    print("(univ AUC >0.5 => higher axis score predicts the outcome; <0.5 => inverse)")

    # ---- comparison chart: AXES vs a-priori GROUPS (CV-AUC) ----------------
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    pub = {d["name"]: d for d in discriminant.DISCRIMINANTS}
    names = [o for o, _, _, _, ax, gp in summary if ax and gp]
    ax_v  = [ax for o, _, _, _, ax, gp in summary if ax and gp]
    gp_v  = [gp for o, _, _, _, ax, gp in summary if ax and gp]
    x = np.arange(len(names)); w = 0.38
    fig, axp = plt.subplots(figsize=(10, 4.5))
    axp.axhspan(0.45, 0.55, color="#eee", zorder=0)
    axp.axhline(0.5, color="#999", ls="--", lw=1, zorder=1)
    axp.bar(x - w/2, gp_v, w, label="a-priori GROUPS (Phase D)", color="#8FA5B8")
    axp.bar(x + w/2, ax_v, w, label="empirical AXES (this work)", color="#C44E52")
    for xi, v in zip(x - w/2, gp_v): axp.text(xi, v+0.01, f"{v:.2f}", ha="center", fontsize=8)
    for xi, v in zip(x + w/2, ax_v): axp.text(xi, v+0.01, f"{v:.2f}", ha="center", fontsize=8)
    axp.set_xticks(x, names, rotation=20, ha="right", fontsize=9)
    axp.set_ylabel("5-fold CV ROC-AUC"); axp.set_ylim(0, 1.0)
    axp.set_title("Re-deriving the 6 discriminants: empirical AXES vs a-priori GROUPS")
    axp.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUTS, "axis_vs_group_auc.png"), dpi=130)
    print(f"\nChart -> {os.path.join(OUTS,'axis_vs_group_auc.png')}")
