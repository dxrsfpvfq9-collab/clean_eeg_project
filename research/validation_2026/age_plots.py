"""Illustrative graphs of the age-regressed databases: each metric's values
across age, with EC and EO regression curves (mean +/- 2 SD) overlaid.

Outputs PNGs to out/graphs/. Aggregate scatter only (no filenames/PII).
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

sys.path.insert(0, os.path.dirname(__file__))
import age_regression as ar
from panel_parser import NAME_STRINGS

OUT = os.path.join(os.path.dirname(__file__), "out")
GDIR = os.path.join(OUT, "graphs")
os.makedirs(GDIR, exist_ok=True)
COL0 = 10  # row = [file, age, m0..m55]; report metric i at col 10+i

EC_C, EO_C = "#1f77b4", "#d62728"


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


def curve(model, name, ages):
    e = model["metrics"][name]
    mean = np.array([ar.predict(e, a) for a in ages])  # (mean_t, sd_t)
    mt, st = mean[:, 0], mean[:, 1]
    if e["transform"] == "log":
        return np.exp(mt), np.exp(mt + 2 * st), np.exp(mt - 2 * st)
    return mt, mt + 2 * st, mt - 2 * st


def panel(metrics, ec, eo, ecm, eom, fname, title):
    ecA, ecM = ec
    eoA, eoM = eo
    ag = np.linspace(5, 75, 100)
    ncol = 3
    nrow = int(np.ceil(len(metrics) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(15, 4 * nrow))
    axes = np.atleast_1d(axes).ravel()
    for k, name in enumerate(metrics):
        ax = axes[k]
        mi = NAME_STRINGS.index(name)
        for A, M, mod, c, lab in ((ecA, ecM, ecm, EC_C, "EC"),
                                  (eoA, eoM, eom, EO_C, "EO")):
            v = M[:, mi]
            ok = np.isfinite(v) & (A >= 5) & (A <= 75)
            # clip y for readability (1st-99th pct of EC+EO)
            ax.scatter(A[ok], v[ok], s=6, alpha=0.20, color=c)
            m, hi, lo = curve(mod, name, ag)
            ax.plot(ag, m, color=c, lw=2.2, label=f"{lab} mean")
            ax.fill_between(ag, lo, hi, color=c, alpha=0.10)
        allv = np.concatenate([ecM[:, mi], eoM[:, mi]])
        allv = allv[np.isfinite(allv)]
        if len(allv):
            ax.set_ylim(np.nanpercentile(allv, 1), np.nanpercentile(allv, 99))
        ax.set_title(name, fontsize=11, fontweight="bold")
        ax.set_xlabel("Age (years)"); ax.grid(alpha=0.25)
        ax.legend(fontsize=8, loc="best")
    for k in range(len(metrics), len(axes)):
        axes[k].axis("off")
    fig.suptitle(title, fontsize=15, fontweight="bold", y=1.005)
    fig.tight_layout()
    p = os.path.join(GDIR, fname)
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("wrote", p)


def main():
    ecm = json.load(open(os.path.join(OUT, "EC_AGE.agemodel.json")))
    eom = json.load(open(os.path.join(OUT, "EO_AGE.agemodel.json")))
    ec = load("EC_AGE")
    eo = load("EO_AGE")
    print(f"EC n={len(ec[0])}  EO n={len(eo[0])}")

    # curated, clinically meaningful, diverse age patterns
    featured = ["Alpha Peak", "PDR Magnitude", "STD Raw",
                "Diffuse Delta", "Diffuse Theta", "PDR Regulation",
                "Fractal Dimension", "Frontal Gamma", "Global STD"]
    panel(featured, ec, eo, ecm, eom, "age_metrics_overview.png",
          "Brain Panel metrics across age  —  EC (blue) vs EO (red), mean ± 2 SD")

    # the two clearest developmental stories, larger
    panel(["Alpha Peak", "Diffuse Delta"], ec, eo, ecm, eom,
          "age_developmental_highlights.png",
          "Developmental trends: posterior rhythm speeds up, slow activity drops")


if __name__ == "__main__":
    main()
