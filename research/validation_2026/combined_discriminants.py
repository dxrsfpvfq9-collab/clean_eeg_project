"""
Task 3 -- COMBINED direction-aware discriminants.

Fuse the three information sources into one detector per outcome:
  (a) individual metric deviations   -- the 48 signed z-scores
  (b) the 6 covariance axes          -- signed axis z-scores (panel_signature)
  (c) direction of deviation         -- signs everywhere + n_high / n_low counts

Phase D's lesson: naive many-feature / direction-split models OVERFIT (positive
classes as small as 2-7). So "superior" is judged ONLY by held-out AUC, and the
model is kept honest by:
  * compact feature set (6 axes + 2 directional counts + in-fold top-k metrics)
  * in-FOLD selection of the individual metrics (no label leakage)
  * L2 regularization (C=0.5)
  * RepeatedStratifiedKFold (5x20) -> mean +/- std AUC

Baselines compared on the SAME CV: published paper score, a-priori GROUPS,
AXES-only. Cohort/labels/parse identical to Phase D + axis_discriminants.

Run: py combined_discriminants.py     (first run parses 98 PDFs & caches)
"""
import csv, os, sys, json, warnings
import numpy as np
warnings.filterwarnings("ignore")
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_score

import config, labels as L, panel_parser as pp, report_parser as rp
sys.path.insert(0, config.REPO_ROOT)
from process import discriminant                       # noqa: E402
from panel_signature import AXIS_NAMES, NAXES          # noqa: E402

OUTS = "out_structure"
CACHE = os.path.join(OUTS, "cohort_cache.npz")
MODEL = json.load(open(os.path.join(OUTS, "axis_model.json")))
ASSIGN = np.array(MODEL["assign"]); SIGN = np.array(MODEL["sign"])
AX_MU = np.array(MODEL["ax_mu"]); AX_SD = np.array(MODEL["ax_sd"])
GROUPS = ["std_global", "pdr", "phenotypes", "focal", "diffuse", "state_shift"]

def axis_scores_from_z(z):
    out = np.zeros(NAXES)
    for j in range(NAXES):
        m = np.where(ASSIGN == j)[0]
        raw = np.nanmean(SIGN[m] * z[m])
        out[j] = 0.0 if not np.isfinite(raw) else (raw - AX_MU[j]) / AX_SD[j]
    return out

def build_cache():
    rows = list(csv.DictReader(open(os.path.join(config.OUT_DIR, "study_cohort.csv"),
                                    encoding="utf-8")))
    Z, AX, GP, PUBSC = [], [], [], []
    Y = {o: [] for o in L.OUTCOMES}
    pub = {d["name"]: d for d in discriminant.DISCRIMINANTS}
    print(f"Parsing {len(rows)} cohort panels (one-time cache) ...")
    for i, row in enumerate(rows, 1):
        parsed = pp.parse_panel_pdf(row["ec_panel_path"])
        z = np.asarray(parsed["zscores"], float)
        counts = discriminant.compute_oob_counts(z)
        scored = {s["name"]: s["score"] for s in discriminant.compute_scores(counts)}
        Z.append(z); AX.append(axis_scores_from_z(z))
        GP.append([counts[g] for g in GROUPS])
        PUBSC.append([scored[L.DISCRIMINANT_OF[o]] for o in L.OUTCOMES])
        rep = rp.parse_report(row["report_path"]) if row["report_path"] else {}
        age = int(row["age"]) if row["age"] not in ("", None) else None
        labs = L.all_labels(rep, age)
        for o in L.OUTCOMES: Y[o].append(labs[o][0])
        if i % 25 == 0: print(f"   {i}/{len(rows)}")
    Z = np.nan_to_num(np.array(Z, float), nan=0.0)   # unparsed -> population mean
    np.savez(CACHE, Z=Z, AX=np.array(AX, float), GP=np.array(GP, float),
             PUBSC=np.array(PUBSC, float),
             **{f"Y_{o}": np.array(Y[o]) for o in L.OUTCOMES})
    print(f"cached -> {CACHE}")

class PickSignedMetrics(BaseEstimator, TransformerMixin):
    """Keep the 'always' columns; from the first 48 (signed z) pick the top-k by
    in-fold |point-biserial corr| with y.  Selection happens in fit() only."""
    def __init__(self, k=2, always_start=48):
        self.k = k; self.always_start = always_start
    def fit(self, X, y):
        M = X[:, :self.always_start]
        y = np.asarray(y, float)
        c = np.array([abs(np.corrcoef(M[:, j], y)[0, 1]) if np.std(M[:, j]) > 0 else 0
                      for j in range(M.shape[1])])
        self.sel_ = np.argsort(-np.nan_to_num(c))[:self.k]
        return self
    def transform(self, X):
        return np.hstack([X[:, self.always_start:], X[:, self.sel_]])

def evaluate(y, feats, model_pipe, n_splits=5, n_repeats=20):
    npos = int(y.sum())
    if npos < 5 or npos > len(y) - 5:
        return None
    k = min(n_splits, npos)
    cv = RepeatedStratifiedKFold(n_splits=k, n_repeats=n_repeats, random_state=0)
    s = cross_val_score(model_pipe, feats, y, cv=cv, scoring="roc_auc")
    return float(s.mean()), float(s.std())

if __name__ == "__main__":
    if not os.path.exists(CACHE):
        build_cache()
    d = np.load(CACHE)
    Z, AX, GP, PUBSC = d["Z"], d["AX"], d["GP"], d["PUBSC"]
    n_high = (Z >= 2).sum(1, keepdims=True).astype(float)     # directional counts
    n_low  = (Z <= -2).sum(1, keepdims=True).astype(float)
    # full stack the L1 model gets to choose from: signed metrics + axes + groups + direction
    FEAT = np.hstack([Z, AX, GP, n_high, n_low])              # 48 + 6 + 6 + 2 = 62
    FNAMES = (MODEL["labels"] + [f"AX:{AXIS_NAMES[j]}" for j in range(NAXES)]
              + [f"GRP:{g}" for g in GROUPS] + ["n_high", "n_low"])

    L2 = lambda: LogisticRegression(max_iter=5000, C=0.5)
    L1 = lambda: LogisticRegression(max_iter=5000, C=0.3, penalty="l1", solver="liblinear")
    pipe_groups = make_pipeline(StandardScaler(), L2())
    pipe_axes   = make_pipeline(StandardScaler(), L2())
    pipe_comb   = make_pipeline(StandardScaler(), L1())       # sparse: auto-select per outcome

    print(f"\n{'Outcome':<16}{'npos':>5} | {'PUBLISHED':>10}{'GROUPS':>10}"
          f"{'AXES':>10}{'COMBINED-L1':>14}")
    print("-" * 80)
    results = []
    for oi, o in enumerate(L.OUTCOMES):
        y = d[f"Y_{o}"]; npos = int(y.sum())
        pub_auc = (roc_auc_score(y, PUBSC[:, oi]) if 0 < npos < len(y) else None)
        r_g = evaluate(y, GP, pipe_groups)
        r_a = evaluate(y, AX, pipe_axes)
        r_c = evaluate(y, FEAT, pipe_comb)
        f = lambda r: f"{r[0]:.2f}±{r[1]:.2f}" if r else "   -"
        pubf = f"{pub_auc:.2f}" if pub_auc is not None else "   -"
        print(f"{o:<16}{npos:>5} | {pubf:>10}{f(r_g):>10}{f(r_a):>10}{f(r_c):>14}")
        results.append((o, npos, pub_auc, r_g, r_a, r_c))

    # what does the sparse combined model actually SELECT (full-sample fit)?
    print("\n=== COMBINED-L1 selected features (full-sample fit, signed) ===")
    for oi, o in enumerate(L.OUTCOMES):
        y = d[f"Y_{o}"]
        if not (5 <= int(y.sum()) <= len(y) - 5):
            print(f"  {o:<16}: (class too small)"); continue
        pipe = make_pipeline(StandardScaler(), L1()).fit(FEAT, y)
        coef = pipe.named_steps["logisticregression"].coef_[0]
        nz = [(FNAMES[j], coef[j]) for j in np.argsort(-np.abs(coef)) if abs(coef[j]) > 1e-6][:6]
        terms = ", ".join(f"{n}({c:+.2f})" for n, c in nz)
        print(f"  {o:<16}: {terms}")

    # ---- freeze the SUPERIOR outcome-matched, direction-aware detector set --
    # per outcome pick the basis with best mean CV-AUC; fit on full cohort;
    # store scaler + signed coefficients so a new panel can be scored.
    BASES = {"groups": (GP, pipe_groups), "axes": (AX, pipe_axes),
             "combined": (FEAT, pipe_comb)}
    BASIS_FEATNAMES = {"groups": [f"GRP:{g}" for g in GROUPS],
                       "axes": [f"AX:{AXIS_NAMES[j]}" for j in range(NAXES)],
                       "combined": FNAMES}
    frozen = {}
    for o, npos, pub_auc, r_g, r_a, r_c in results:
        cand = {"groups": r_g, "axes": r_a, "combined": r_c}
        cand = {k: v for k, v in cand.items() if v}
        if not cand:
            frozen[o] = {"basis": "published_fallback", "cv_auc": pub_auc,
                         "npos": npos, "confidence": "insufficient"}; continue
        best = max(cand, key=lambda k: cand[k][0])
        Xb, pipe = BASES[best]
        fit = make_pipeline(StandardScaler(),
                            L1() if best == "combined" else L2()).fit(Xb, d[f"Y_{o}"])
        sc = fit.named_steps["standardscaler"]; lr = fit.steps[-1][1]
        coef = lr.coef_[0]
        keep = [j for j in range(len(coef)) if abs(coef[j]) > 1e-6]
        frozen[o] = {
            "basis": best, "cv_auc": round(cand[best][0], 3),
            "cv_std": round(cand[best][1], 3), "npos": int(npos),
            "confidence": "ok" if npos >= 15 else "low (small positive class)",
            "feature_names": [BASIS_FEATNAMES[best][j] for j in keep],
            "weights": [round(float(coef[j]), 4) for j in keep],
            "scaler_mean": [round(float(sc.mean_[j]), 5) for j in keep],
            "scaler_scale": [round(float(sc.scale_[j]), 5) for j in keep],
            "intercept": round(float(lr.intercept_[0]), 4),
            "published_auc": round(pub_auc, 3) if pub_auc is not None else None,
        }
    with open(os.path.join(OUTS, "discriminant_v2.json"), "w") as fjson:
        json.dump(frozen, fjson, indent=1)
    print(f"\nFrozen superior detector set -> {os.path.join(OUTS,'discriminant_v2.json')}")
    for o in L.OUTCOMES:
        fr = frozen[o]
        print(f"  {o:<16}: basis={fr['basis']:<9} cv-AUC={fr.get('cv_auc')} "
              f"(paper {fr.get('published_auc')}) [{fr['confidence']}]")

    # ---- chart ----
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    rr = [r for r in results if r[3] and r[4] and r[5]]
    names = [r[0] for r in rr]; x = np.arange(len(names)); w = 0.26
    gp = [r[3][0] for r in rr]; ax = [r[4][0] for r in rr]; cb = [r[5][0] for r in rr]
    ge = [r[3][1] for r in rr]; ae = [r[4][1] for r in rr]; ce = [r[5][1] for r in rr]
    fig, axp = plt.subplots(figsize=(10.5, 5))
    axp.axhline(0.5, color="#999", ls="--", lw=1)
    axp.bar(x - w, gp, w, yerr=ge, capsize=3, label="a-priori GROUPS", color="#8FA5B8")
    axp.bar(x,     ax, w, yerr=ae, capsize=3, label="6 AXES", color="#DD8452")
    axp.bar(x + w, cb, w, yerr=ce, capsize=3, label="COMBINED-L1 (signed metrics+axes+groups+direction)",
            color="#C44E52")
    for xi, v in zip(x + w, cb): axp.text(xi, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
    axp.set_xticks(x, names, rotation=15, ha="right"); axp.set_ylim(0, 1)
    axp.set_ylabel("Repeated 5x20 CV ROC-AUC")
    axp.set_title("Combined direction-aware discriminants vs prior bases")
    axp.legend(fontsize=8, loc="upper right")
    fig.tight_layout(); fig.savefig(os.path.join(OUTS, "combined_auc.png"), dpi=130)
    print(f"\nChart -> {os.path.join(OUTS,'combined_auc.png')}")
