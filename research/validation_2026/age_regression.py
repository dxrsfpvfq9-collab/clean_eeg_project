"""Age-regressed normative database.

Reads the per-file (age + 48 metrics) rows captured by the build, and for each
metric fits:
  - a per-metric transform (log for positive/skewed amplitudes, else identity),
  - mean(age): best of {const, age, age^2, age^3, log(age), log(age)+age} by
    5-fold CV (guards against over-fitting the sparse tails),
  - sd(age): sqrt of a CV-selected poly (deg 0-2) fit to squared residuals
    (captures the wider spread in children; deg 0 -> homoscedastic).
Residual outliers (>3 robust-SD) are trimmed once before the final fit, echoing
the trimmed estimator used for EC_191.

Outputs (per prefix, e.g. EC_AGE):
  out/<prefix>.agemodel.json     - transform + coefficients + valid range + K-S p
  out/<prefix>.binned_norms.csv  - mean/sd per age bin per metric (fallback)
  out/<prefix>.regression_report.md
z_score(model, metric, value, age) computes an age-appropriate z for any age.
"""
import csv
import glob
import json
import os
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(__file__))
from panel_parser import NAME_STRINGS  # 48 metric names, in order

AGE_BINS = [(4, 9), (10, 14), (15, 19), (20, 24), (25, 34), (35, 44),
            (45, 54), (55, 64), (65, 120)]
VALID_AGE = (5, 75)   # reliable modeling range (data dense here)
METRIC_COL0 = 10      # row = [file, age, m0..m55]; report metric i at col 10+i


# ---- candidate mean models: name -> feature builder over age vector ----------
def _feats(name, age):
    t = age / 10.0
    la = np.log(age)
    return {
        "const": np.ones((len(age), 1)),
        "age":   np.c_[np.ones_like(t), t],
        "age2":  np.c_[np.ones_like(t), t, t**2],
        "age3":  np.c_[np.ones_like(t), t, t**2, t**3],
        "log":   np.c_[np.ones_like(t), la],
        "log+age": np.c_[np.ones_like(t), la, t],
    }[name]


MODELS = ["const", "age", "age2", "age3", "log", "log+age"]


def _fit_ls(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def _cv_mse(name, age, y, k=5):
    n = len(y)
    idx = np.arange(n)
    rng = np.random.default_rng(0)
    rng.shuffle(idx)
    folds = np.array_split(idx, k)
    errs = []
    for i in range(k):
        te = folds[i]
        tr = np.concatenate([folds[j] for j in range(k) if j != i])
        X = _feats(name, age)
        beta = _fit_ls(X[tr], y[tr])
        pred = X[te] @ beta
        errs.append(np.mean((y[te] - pred) ** 2))
    return float(np.mean(errs))


def _choose_transform(vals):
    v = vals[np.isfinite(vals)]
    if v.min() > 0 and stats.skew(v) > 0.75:
        return "log"
    return "identity"


def _apply_tf(tf, v):
    return np.log(v) if tf == "log" else v


def fit_metric(age, raw):
    """Fit transform + mean(age) + sd(age) for one metric. Returns dict."""
    m = np.isfinite(age) & np.isfinite(raw)
    age, raw = age[m], raw[m]
    tf = _choose_transform(raw)
    if tf == "log":
        m2 = raw > 0
        age, raw = age[m2], raw[m2]
    y = _apply_tf(tf, raw)

    # pick mean model by CV
    cv = {nm: _cv_mse(nm, age, y) for nm in MODELS}
    best = min(cv, key=cv.get)
    X = _feats(best, age)
    beta = _fit_ls(X, y)
    resid = y - X @ beta
    # trim residual outliers (>3 robust SD) once, refit
    rsd = 1.4826 * np.median(np.abs(resid - np.median(resid))) or resid.std() or 1.0
    keep = np.abs(resid) <= 3 * rsd
    beta = _fit_ls(X[keep], y[keep])
    resid = y - X @ beta

    # sd(age): CV-select poly deg 0-2 on squared residuals
    r2 = resid[keep] ** 2
    a_keep = age[keep]
    sd_best, sd_cv = "const", None
    for nm in ("const", "age", "age2"):
        c = _cv_mse(nm, a_keep, r2)
        if sd_cv is None or c < sd_cv:
            sd_cv, sd_best = c, nm
    sdX = _feats(sd_best, a_keep)
    sd_beta = _fit_ls(sdX, r2)

    # standardized residuals -> K-S vs N(0,1)
    sd_pred = np.sqrt(np.clip(_feats(sd_best, age) @ sd_beta, 1e-9, None))
    zr = resid / sd_pred
    ks_p = float(stats.kstest(zr[np.isfinite(zr)], "norm").pvalue)

    return {
        "transform": tf,
        "mean_model": best, "mean_coef": beta.tolist(),
        "sd_model": sd_best, "sd_coef": sd_beta.tolist(),
        "n": int(len(age)), "ks_p": round(ks_p, 4),
        "age_dependent": best != "const",
    }


def predict(model_entry, age):
    beta = np.asarray(model_entry["mean_coef"])
    mean = _feats(model_entry["mean_model"], np.atleast_1d(float(age))) @ beta
    sdv = _feats(model_entry["sd_model"], np.atleast_1d(float(age))) @ np.asarray(model_entry["sd_coef"])
    return float(mean[0]), float(np.sqrt(max(sdv[0], 1e-9)))


def z_score(model, metric, value, age):
    e = model["metrics"][metric]
    v = np.log(value) if e["transform"] == "log" and value > 0 else value
    mean, sd = predict(e, age)
    return (v - mean) / sd


# ---- driver ------------------------------------------------------------------
def load_rows(prefix, outdir):
    rows = []
    for f in sorted(glob.glob(os.path.join(outdir, f"{prefix}_p*.agerows.csv"))):
        for r in csv.reader(open(f, encoding="utf-8")):
            rows.append(r)
    return rows


def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else "EC_AGE"
    outdir = os.path.join(os.path.dirname(__file__), "out")
    rows = load_rows(prefix, outdir)
    if not rows:
        print(f"no rows for {prefix}", file=sys.stderr)
        return
    ages = np.array([float(r[1]) if r[1] else np.nan for r in rows])
    within = (ages >= VALID_AGE[0]) & (ages <= VALID_AGE[1])
    print(f"{prefix}: {len(rows)} files, {int(within.sum())} within age {VALID_AGE}")

    model = {"prefix": prefix, "valid_age": VALID_AGE, "n_files": len(rows),
             "age_bins": AGE_BINS, "metrics": {}}
    report = [f"# Age-regression report — {prefix}", "",
              f"n={len(rows)} files (age {VALID_AGE[0]}-{VALID_AGE[1]}: "
              f"{int(within.sum())}). Per metric: transform, mean(age) model "
              "(CV-selected), sd(age) model, K-S p of standardized residuals "
              "(p>0.05 = residuals ~Gaussian), age-dependent flag.", "",
              "| metric | tf | mean model | sd model | n | K-S p | age-dep |",
              "|---|---|---|---|---|---|---|"]
    binned = [["metric", "transform"] + [f"{lo}-{hi}_mean" for lo, hi in AGE_BINS]
              + [f"{lo}-{hi}_sd" for lo, hi in AGE_BINS]]

    for i, name in enumerate(NAME_STRINGS):
        raw = np.array([float(r[METRIC_COL0 + i]) if r[METRIC_COL0 + i] not in ("", None)
                        else np.nan for r in rows])
        # regression model (fit within valid age range)
        e = fit_metric(ages[within], raw[within])
        model["metrics"][name] = e
        report.append(f"| {name} | {e['transform'][:3]} | {e['mean_model']} | "
                      f"{e['sd_model']} | {e['n']} | {e['ks_p']} | "
                      f"{'yes' if e['age_dependent'] else 'no'} |")
        # binned norms (trimmed mean/sd per bin, on transformed scale back-txf)
        brow = [name, e["transform"]]
        sds = []
        for lo, hi in AGE_BINS:
            sel = np.isfinite(raw) & (ages >= lo) & (ages <= hi)
            v = raw[sel]
            brow.append(round(float(np.mean(v)), 4) if len(v) >= 5 else "")
            sds.append(round(float(np.std(v)), 4) if len(v) >= 5 else "")
        binned.append(brow + sds)

    with open(os.path.join(outdir, f"{prefix}.agemodel.json"), "w") as fh:
        json.dump(model, fh, indent=1)
    with open(os.path.join(outdir, f"{prefix}.binned_norms.csv"), "w", newline="") as fh:
        csv.writer(fh).writerows(binned)
    with open(os.path.join(outdir, f"{prefix}.regression_report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(report) + "\n")

    ndep = sum(1 for e in model["metrics"].values() if e["age_dependent"])
    ngauss = sum(1 for e in model["metrics"].values() if e["ks_p"] > 0.05)
    print(f"  age-dependent metrics: {ndep}/48 | residuals Gaussian (K-S p>.05): {ngauss}/48")
    print(f"  wrote out/{prefix}.agemodel.json, .binned_norms.csv, .regression_report.md")


if __name__ == "__main__":
    main()
