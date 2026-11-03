"""Age-by-condition reference ranges for the source database features.

For every feature (edf_features, study_features, and per-site chan_power) and
condition (EC / EO) this fits, on ONE study per client (the earliest, so a
client with ten sessions does not count ten times):

    mean(age)  = cubic polynomial in log(age)      after a transform (log for
    sd(age)    = linear in log(age), from |resid|  power and ratios, logit for
                                                    percentages, none for Hz)

two passes, dropping |z| > 4 between them so a handful of broken recordings
do not set the range. Every stored study then gets a z-score AND an empirical
age-adjusted percentile (rank of its z among the fit sample) -- the percentile
stays honest on features whose shape the transform does not fix (zero-heavy
network shares, say).

THESE ARE REFERENCE RANGES OF A SCREENING POPULATION, NOT NORMS. The QA corpus
is people who were referred for an EEG screening; "z = 2" means unusual for
that population at that age, not abnormal.

    py tools/reference_ranges.py [--store DIR] [--pdf]
"""
import argparse
import json
import os
import sqlite3

import numpy as np

DEFAULT_STORE = r"C:\BrainPanel\source_db"
AGE_MIN, AGE_MAX = 3, 90
MIN_N = 60
TRIM_Z = 4.0
EPS_PCT = 0.5          # logit clip for percentages, in %

SCHEMA = """
CREATE TABLE IF NOT EXISTS ref_models (
  feature TEXT, cond TEXT, transform TEXT, mean_coef TEXT, sd_coef TEXT,
  n INTEGER, age_min REAL, age_max REAL, resid_z TEXT, PRIMARY KEY (feature, cond));
CREATE TABLE IF NOT EXISTS ref_z (
  study_id TEXT, feature TEXT, value REAL, z REAL, pctile REAL,
  PRIMARY KEY (study_id, feature));
"""

# feature -> transform.  "site:<col>" features are expanded per 10-20 site.
STUDY = {
    # electrode space (edf_features)
    "tbr_cz": "log", "tbr_fz": "log", "tbr_mean": "log", "paf_post": "none",
    "rel_alpha_post": "logit", "rel_theta_front": "logit", "rel_delta_mean": "logit",
    "rel_hibeta_mean": "logit", "alpha_asym_f4f3": "none",
    # source space (study_features)
    "artifact_pct": "logit", "alpha_pct": "logit", "theta_pct": "logit",
    "delta_pct": "logit", "beta_pct": "logit", "post_alpha_pct": "logit",
    "dom_post_hz": "none", "dmn_pct": "logit", "sn_pct": "logit", "ecn_pct": "logit",
    "n_edges_alpha": "log1p",
}
SITE = {"rel_delta": "logit", "rel_theta": "logit", "rel_alpha": "logit", "rel_beta": "logit",
        "rel_hibeta": "logit", "rel_gamma": "logit", "abs_alpha": "log", "abs_theta": "log",
        "total": "log", "tbr": "log", "paf": "none"}


def fwd(t, v):
    v = np.asarray(v, float)
    if t == "log":
        return np.log(np.clip(v, 1e-6, None))
    if t == "log1p":
        return np.log1p(np.clip(v, 0, None))
    if t == "logit":
        p = np.clip(v, EPS_PCT, 100 - EPS_PCT) / 100
        return np.log(p / (1 - p))
    return v


def inv(t, y):
    y = np.asarray(y, float)
    if t == "log":
        return np.exp(y)
    if t == "log1p":
        return np.expm1(y)
    if t == "logit":
        return 100 / (1 + np.exp(-y))
    return y


def _design(age, deg):
    la = np.log(np.clip(age, AGE_MIN, AGE_MAX))
    return np.vstack([la ** k for k in range(deg + 1)]).T


def fit(age, y):
    keep = np.ones(len(y), bool)
    for _ in range(2):
        mc = np.linalg.lstsq(_design(age[keep], 3), y[keep], rcond=None)[0]
        res = y - _design(age, 3) @ mc
        # E|N(0,s)| = s*sqrt(2/pi)
        sc = np.linalg.lstsq(_design(age[keep], 1), np.abs(res[keep]) * np.sqrt(np.pi / 2),
                             rcond=None)[0]
        sd = np.clip(_design(age, 1) @ sc, 1e-6, None)
        keep = np.abs(res / sd) <= TRIM_Z
    z = res / sd
    return mc, sc, keep, z


def predict(model, age, value):
    a = np.asarray(age, float)
    mu = _design(a, 3) @ np.array(model["mean_coef"])
    sd = np.clip(_design(a, 1) @ np.array(model["sd_coef"]), 1e-6, None)
    z = (fwd(model["transform"], value) - mu) / sd
    ref = np.array(model["resid_z"])
    pct = 100 * np.searchsorted(ref, z, side="right") / len(ref)
    return z, pct


def collect(con):
    """{feature: (transform, {study_id: value})}"""
    out = {}
    cols = [r[1] for r in con.execute("PRAGMA table_info(edf_features)")]
    rows = con.execute("SELECT * FROM edf_features").fetchall()
    cols2 = [r[1] for r in con.execute("PRAGMA table_info(study_features)")]
    rows2 = con.execute("SELECT * FROM study_features").fetchall()
    for f, t in STUDY.items():
        if f in cols:
            i = cols.index(f)
            out[f] = (t, {r[0]: r[i] for r in rows if r[i] is not None})
        else:
            i = cols2.index(f)
            out[f] = (t, {r[0]: r[i] for r in rows2 if r[i] is not None})
    for col, t in SITE.items():
        for sid, site, v in con.execute(f"SELECT study_id, site, {col} FROM chan_power"):
            if v is not None:
                out.setdefault(f"{site}.{col}", (t, {}))[1][sid] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=DEFAULT_STORE)
    ap.add_argument("--pdf", action="store_true", help="write <store>/reference_ranges.pdf")
    a = ap.parse_args()
    con = sqlite3.connect(os.path.join(a.store, "sources.db"), timeout=60)
    con.executescript(SCHEMA)
    con.execute("DELETE FROM ref_models")
    con.execute("DELETE FROM ref_z")

    studies = {r[0]: dict(client=r[1], cond=r[2], age=r[3], when=r[4] or "")
               for r in con.execute("SELECT id, client, cond, age, rec_start FROM studies "
                                    "WHERE status='ok'")}
    # one study per client per condition: the earliest recording
    first = {}
    for sid, s in sorted(studies.items(), key=lambda kv: kv[1]["when"]):
        if s["cond"] in ("EC", "EO") and s["age"] and AGE_MIN <= s["age"] <= AGE_MAX:
            first.setdefault((s["client"] or sid, s["cond"]), sid)
    fitset = {c: [sid for (cl, cc), sid in first.items() if cc == c] for c in ("EC", "EO")}

    feats = collect(con)
    plots = []
    for f, (t, vals) in feats.items():
        for cond in ("EC", "EO"):
            ids = [sid for sid in fitset[cond] if sid in vals]
            if len(ids) < MIN_N:
                continue
            age = np.array([studies[s]["age"] for s in ids], float)
            y = fwd(t, [vals[s] for s in ids])
            mc, sc, keep, z = fit(age, y)
            ref = np.sort(z[keep])
            model = dict(transform=t, mean_coef=mc.tolist(), sd_coef=sc.tolist(),
                         resid_z=ref.round(4).tolist())
            con.execute("INSERT INTO ref_models VALUES (?,?,?,?,?,?,?,?,?)", (
                f, cond, t, json.dumps(model["mean_coef"]), json.dumps(model["sd_coef"]),
                int(keep.sum()), float(age.min()), float(age.max()), json.dumps(model["resid_z"])))
            # score every study of this condition with an age in range
            todo = [sid for sid, s in studies.items() if s["cond"] == cond and sid in vals
                    and s["age"] and AGE_MIN <= s["age"] <= AGE_MAX]
            zz, pp = predict(model, [studies[s]["age"] for s in todo], [vals[s] for s in todo])
            con.executemany("INSERT INTO ref_z VALUES (?,?,?,?,?)",
                            [(s, f, float(vals[s]), float(zv), float(pv))
                             for s, zv, pv in zip(todo, zz, pp)])
            if "." not in f:
                plots.append((f, cond, t, age, y, keep, model))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM ref_models").fetchone()[0]
    print(f"fit set: EC {len(fitset['EC'])}, EO {len(fitset['EO'])} clients; {n} models; "
          f"{con.execute('SELECT COUNT(*) FROM ref_z').fetchone()[0]} z-scores")
    if a.pdf:
        render(plots, os.path.join(a.store, "reference_ranges.pdf"))


def render(plots, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    grid = np.linspace(AGE_MIN, 85, 200)
    with PdfPages(out) as pdf:
        for k in range(0, len(plots), 6):
            fig, axs = plt.subplots(3, 2, figsize=(8.5, 11))
            for ax, (f, cond, t, age, y, keep, m) in zip(axs.flat, plots[k:k + 6]):
                mu = _design(grid, 3) @ np.array(m["mean_coef"])
                sd = np.clip(_design(grid, 1) @ np.array(m["sd_coef"]), 1e-6, None)
                ax.scatter(age, inv(t, y), s=4, c=np.where(keep, "0.45", "red"), lw=0)
                ax.plot(grid, inv(t, mu), "k", lw=1.5)
                for s in (-2, 2):
                    ax.plot(grid, inv(t, mu + s * sd), "k--", lw=0.8)
                ax.set_xscale("log")
                ax.set_xticks([4, 8, 15, 30, 60])
                ax.set_xticklabels(["4", "8", "15", "30", "60"])
                if t in ("log", "log1p"):
                    ax.set_yscale("symlog" if t == "log1p" else "log")
                ax.set_title(f"{f}  ({cond}, n={int(keep.sum())})", fontsize=9)
                ax.set_xlabel("age", fontsize=8)
                ax.tick_params(labelsize=7)
            for ax in axs.flat[len(plots[k:k + 6]):]:
                ax.axis("off")
            fig.suptitle("Reference ranges (screening population, one study per client): "
                         "mean and +/-2 SD by age", fontsize=9)
            fig.tight_layout(rect=(0, 0, 1, 0.97))
            pdf.savefig(fig)
            plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    main()
