"""Validation of the age-regressed database (#1).

1. Consistency with EC_191: per metric, compare the established flat EC_191 mean
   to the age-regressed population mean (average of the age-model predictions
   over the cohort's actual ages). Agreement -> the age DB reproduces the
   validated database on aggregate.
2. Regression fit: per metric x age-bin, compare the empirical binned mean to
   the regression-predicted value at the bin's center age. Points on y=x -> the
   fitted curves pass through the data.
3. Rank which metrics age-adjustment changes most (age span of the mean curve in
   units of the flat SD).

Outputs: out/graphs/validation_agreement.png and out/age_validation_report.md
"""
import csv
import glob
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpyxl

sys.path.insert(0, os.path.dirname(__file__))
import age_regression as ar
from panel_parser import NAME_STRINGS

OUT = os.path.join(os.path.dirname(__file__), "out")
GDIR = os.path.join(OUT, "graphs")
COL0 = 10
BINS = ar.AGE_BINS


def load(prefix):
    ages, mat = [], []
    for f in sorted(glob.glob(os.path.join(OUT, f"{prefix}_p*.agerows.csv"))):
        for r in csv.reader(open(f, encoding="utf-8")):
            try:
                a = float(r[1])
            except (ValueError, IndexError):
                continue
            ages.append(a)
            mat.append([float(r[COL0 + i]) if r[COL0 + i] not in ("", None) else np.nan
                        for i in range(48)])
    return np.array(ages), np.array(mat)


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def ec191_flat():
    rows = list(openpyxl.load_workbook(
        os.path.join(REPO_ROOT, "EC_191.out_file.icale.xlsx"),
        data_only=True, read_only=True).active.iter_rows(values_only=True))
    return {NAME_STRINGS[i]: (float(rows[9 + i][0]), float(rows[9 + i][1]))
            for i in range(48)}


def pred_mean(e, age):
    mt, _ = ar.predict(e, age)
    return np.exp(mt) if e["transform"] == "log" else mt


def main():
    model = json.load(open(os.path.join(OUT, "EC_AGE.agemodel.json")))
    ages, mat = load("EC_AGE")
    flat = ec191_flat()

    consistency = []   # (metric, ec191_mean, agedb_popmean)
    fit_pts = []       # (predicted_bin, observed_bin)  across all metric x bin
    age_effect = []    # (metric, span_in_flatSD)

    valid = (ages >= 5) & (ages <= 75)
    for i, name in enumerate(NAME_STRINGS):
        e = model["metrics"][name]
        v = mat[:, i]
        # 1. population mean of predictions over the cohort ages
        pm = np.nanmean([pred_mean(e, a) for a in ages[valid]])
        consistency.append((name, flat[name][0], pm))
        # 2. binned observed vs predicted
        for lo, hi in BINS:
            sel = np.isfinite(v) & (ages >= lo) & (ages <= hi)
            if sel.sum() >= 8:
                obs = float(np.mean(v[sel]))
                ctr = min((lo + hi) / 2.0, 72)
                fit_pts.append((pred_mean(e, ctr), obs))
        # 3. age effect: span of mean curve over 5-75 in flat-SD units
        grid = np.linspace(5, 75, 50)
        curve = np.array([pred_mean(e, a) for a in grid])
        span = (curve.max() - curve.min()) / (flat[name][1] + 1e-9)
        age_effect.append((name, span))

    # ---- figure: two agreement XY plots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.5))

    cx = np.array([c[1] for c in consistency])
    cy = np.array([c[2] for c in consistency])
    ax1.loglog([1e-2, 1e4], [1e-2, 1e4], "k--", lw=1, alpha=0.6, label="y = x")
    ax1.scatter(cx, cy, s=45, color="#2c7fb8", edgecolor="k", linewidth=0.4, zorder=3)
    lr = np.corrcoef(np.log(cx), np.log(cy))[0, 1] ** 2
    ax1.set_xlabel("EC_191 established mean (flat)", fontsize=11)
    ax1.set_ylabel("Age-regressed DB population mean", fontsize=11)
    ax1.set_title(f"(a) Age-DB reproduces EC_191 norms\n48 metrics, log-log,  "
                  f"R² = {lr:.4f}", fontsize=12, fontweight="bold")
    ax1.grid(alpha=0.25, which="both"); ax1.legend(loc="upper left")
    lo = min(cx.min(), cy.min()) * 0.7; hi = max(cx.max(), cy.max()) * 1.4
    ax1.set_xlim(lo, hi); ax1.set_ylim(lo, hi)

    fp = np.array(fit_pts)
    ax2.loglog([1e-2, 1e4], [1e-2, 1e4], "k--", lw=1, alpha=0.6, label="y = x")
    ax2.scatter(fp[:, 0], fp[:, 1], s=22, color="#d95f0e", alpha=0.5,
                edgecolor="none", zorder=3)
    fr = np.corrcoef(np.log(fp[:, 0]), np.log(fp[:, 1]))[0, 1] ** 2
    ax2.set_xlabel("Regression-predicted (at bin-center age)", fontsize=11)
    ax2.set_ylabel("Observed age-bin mean", fontsize=11)
    ax2.set_title(f"(b) Regression fits the binned data\n48 metrics x 9 age bins,"
                  f"  R² = {fr:.4f}", fontsize=12, fontweight="bold")
    ax2.grid(alpha=0.25, which="both"); ax2.legend(loc="upper left")
    lo2 = fp.min() * 0.7; hi2 = fp.max() * 1.4
    ax2.set_xlim(lo2, hi2); ax2.set_ylim(lo2, hi2)

    fig.suptitle("Age-regressed database validation (eyes-closed)",
                 fontsize=15, fontweight="bold")
    fig.tight_layout()
    p = os.path.join(GDIR, "validation_agreement.png")
    fig.savefig(p, dpi=140, bbox_inches="tight")
    plt.close(fig)

    # ---- report
    age_effect.sort(key=lambda x: -x[1])
    rep = ["# Age-regression validation (eyes-closed)", "",
           f"Consistency with EC_191 (48 metrics, log-log): **R² = {lr:.4f}**  ",
           f"Regression fit to binned data (48x9): **R² = {fr:.4f}**", "",
           "## Metrics most changed by age-adjustment",
           "(age span of the mean curve across 5-75, in units of the flat SD; "
           "big = the flat norm is a poor fit at the age extremes)", "",
           "| rank | metric | age span (flat-SD units) |", "|---|---|---|"]
    for r, (nm, sp) in enumerate(age_effect[:12], 1):
        rep.append(f"| {r} | {nm} | {sp:.2f} |")
    rep += ["", "## Least age-dependent (flat norm is fine)", "",
            "| metric | age span |", "|---|---|"]
    for nm, sp in age_effect[-6:]:
        rep.append(f"| {nm} | {sp:.2f} |")
    with open(os.path.join(OUT, "age_validation_report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(rep) + "\n")

    print(f"consistency R^2={lr:.4f}  fit R^2={fr:.4f}")
    print("top age-adjusted:", ", ".join(f"{n}({s:.1f})" for n, s in age_effect[:5]))
    print("wrote", p, "and out/age_validation_report.md")


if __name__ == "__main__":
    main()
