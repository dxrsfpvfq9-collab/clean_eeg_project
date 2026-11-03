"""Brain Panel vs the EDF and source analyses, and all three vs the doctor.

Uses the production panels already parsed into the source database (`panel`:
48 values + z per study, from the study's .icale.rep.pdf).

1. Agreement: Spearman between every panel z row and every age-adjusted EDF /
   source feature (one study per client per condition) -- which panel rows
   measure the same thing as which new feature.
2. Prediction: cross-validated L2 logistic regression for each doctor's label
   from (P) the 48 panel z-scores, (D) the published discriminant score for
   that outcome (process/discriminant.py, no fitting), (E) the EDF features,
   (S) the source features + source atypicality, and their combinations.
   Folds are grouped by client (EC and EO sessions of one client never split
   across train/test); 10 repeats of 5-fold, AUC averaged.

Panels showing Global STD = 1000 (issued before the 2026-10-08 fix) have that
row set to NaN -> imputed with the training median.

    py tools/panel_crosscheck.py [--store DIR]
-> research/validation_2026/out/PANEL_CROSSCHECK.md
"""
import argparse
import os
import sqlite3
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "validation_2026"))

from process.discriminant import compute_oob_counts, compute_scores   # noqa: E402

DEFAULT_STORE = r"C:\BrainPanel\source_db"
OUT_MD = os.path.join(ROOT, "research", "validation_2026", "out", "PANEL_CROSSCHECK.md")
EDF_F = ["tbr_cz", "tbr_fz", "tbr_mean", "paf_post", "rel_alpha_post", "rel_theta_front",
         "rel_delta_mean", "rel_hibeta_mean", "alpha_asym_f4f3"]
SRC_F = ["artifact_pct", "alpha_pct", "theta_pct", "delta_pct", "beta_pct", "post_alpha_pct",
         "dom_post_hz", "dmn_pct", "sn_pct", "ecn_pct", "n_edges_alpha"]
DISC_OF = {"clinical_abnorm": "Clinical Abnormality", "pdr_slow": "PDR frequency",
           "pdr_freq_abnorm": "PDR frequency", "drowsiness": "Drowsiness",
           "paroxysmal": "Paroxysmal"}
OUTCOMES = ["clinical_abnorm", "pdr_slow", "drowsiness", "paroxysmal"]
Z_CLIP = 10.0


def load(con):
    from panel_parser import NAME_STRINGS
    st = {r[0]: dict(client=r[1] or r[0], cond=r[2], when=r[3] or "")
          for r in con.execute("SELECT id, client, cond, rec_start FROM studies WHERE status='ok'")}
    pz = {}
    for sid, row, value, z in con.execute("SELECT study_id, row, value, z FROM panel"):
        pz.setdefault(sid, [np.nan] * 48)
        if row == 1 and value is not None and abs(value - 1000) < 1e-6:
            z = None                                  # pre-fix Global STD
        pz[sid][row] = np.nan if z is None else z
    rz = {}
    for sid, f, z in con.execute("SELECT study_id, feature, z FROM ref_z WHERE feature NOT LIKE '%.%'"):
        rz.setdefault(sid, {})[f] = z
    atyp = {r[0]: r[1] for r in con.execute("SELECT study_id, atyp_pctile FROM source_atyp")}
    lab = {}
    for sid, o, v, cf in con.execute("SELECT study_id, outcome, value, conf FROM labels"):
        if cf == "high":
            lab.setdefault(o, {})[sid] = v
    first = {}
    for sid, s in sorted(st.items(), key=lambda kv: kv[1]["when"]):
        if s["cond"] in ("EC", "EO") and sid in pz and sid in rz:
            first.setdefault((s["client"], s["cond"]), sid)
    ids = sorted(first.values())
    return st, pz, rz, atyp, lab, ids, NAME_STRINGS


def matrix(ids, pz, rz, atyp, st):
    P = np.clip(np.array([pz[s] for s in ids], float), -Z_CLIP, Z_CLIP)
    E = np.array([[rz[s].get(f, np.nan) for f in EDF_F] for s in ids], float)
    S = np.array([[rz[s].get(f, np.nan) for f in SRC_F] + [atyp.get(s, np.nan)] for s in ids], float)
    C = np.array([[1.0 if st[s]["cond"] == "EO" else 0.0] for s in ids])
    return P, np.clip(E, -Z_CLIP, Z_CLIP), S, C


def disc_score(ids, pz, outcome):
    name = DISC_OF[outcome]
    out = []
    for s in ids:
        z = np.nan_to_num(np.array(pz[s], float), nan=0.0)
        sc = {d["name"]: d["score"] for d in compute_scores(compute_oob_counts(z))}
        out.append([sc[name]])
    return np.array(out, float)


def cv_auc(X, y, groups, reps=10, k=5, C=0.1):
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    rng = np.random.default_rng(0)
    ug = np.unique(groups)
    aucs = []
    for _ in range(reps):
        fold = dict(zip(ug, rng.permutation(len(ug)) % k))
        f = np.array([fold[g] for g in groups])
        pred = np.full(len(y), np.nan)
        for j in range(k):
            tr, te = f != j, f == j
            if y[tr].sum() == 0 or y[tr].sum() == tr.sum():
                continue
            m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                              LogisticRegression(C=C, max_iter=2000, class_weight="balanced"))
            m.fit(X[tr], y[tr])
            pred[te] = m.predict_proba(X[te])[:, 1]
        ok = np.isfinite(pred)
        if 0 < y[ok].sum() < ok.sum():
            aucs.append(roc_auc_score(y[ok], pred[ok]))
    return float(np.mean(aucs)), float(np.std(aucs))


def main():
    from scipy.stats import spearmanr
    from sklearn.metrics import roc_auc_score
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=DEFAULT_STORE)
    a = ap.parse_args()
    con = sqlite3.connect(os.path.join(a.store, "sources.db"))
    st, pz, rz, atyp, lab, ids, names = load(con)
    P, E, S, C = matrix(ids, pz, rz, atyp, st)
    L = ["# Brain Panel vs EDF and source analyses -- and all three vs the doctor\n",
         "Generated by `tools/panel_crosscheck.py`. Studies with a production panel, EDF power "
         "and source features; one study per client per condition. Panel = the 48 z-scores "
         "against EC_191 (an eyes-closed adult database, not age-adjusted); EDF and source "
         "features = age-by-condition z (`reference_ranges.py`).\n",
         f"Studies: {len(ids)} (EC {sum(st[s]['cond'] == 'EC' for s in ids)}, "
         f"EO {sum(st[s]['cond'] == 'EO' for s in ids)}).\n"]

    # ---- 1. agreement
    L.append("## 1. Which panel row measures the same thing as each new feature\n")
    L.append("Spearman rho, eyes-closed studies; strongest panel row per feature (|rho| >= 0.3 "
             "is a real overlap, < 0.2 means the panel does not see it).\n")
    L.append("| feature | best panel row | rho | 2nd | rho |")
    L.append("|---|---|---:|---|---:|")
    ec = np.array([st[s]["cond"] == "EC" for s in ids])
    for j, f in enumerate(EDF_F + SRC_F + ["source atypicality"]):
        x = (E[:, j] if j < len(EDF_F) else S[:, j - len(EDF_F)])
        rs = []
        for r in range(48):
            m = ec & np.isfinite(x) & np.isfinite(P[:, r])
            if m.sum() > 50:
                rs.append((spearmanr(x[m], P[m, r])[0], names[r]))
        rs.sort(key=lambda t: -abs(t[0]))
        L.append(f"| {f} | {rs[0][1]} | {rs[0][0]:+.2f} | {rs[1][1]} | {rs[1][0]:+.2f} |")
    L.append("")

    # ---- 2. prediction
    L.append("## 2. Predicting the doctor's labels (cross-validated AUC, EC + EO pooled)\n")
    L.append("Mean AUC over 10 x 5-fold, folds grouped by client; +/- = SD over repeats. "
             "'Published discriminant' is the paper's weighted OOB count for that outcome, "
             "applied as-is (no fitting). Condition (EC/EO) is in every fitted model.\n")
    L.append("| outcome | n | pos | published discriminant | panel (P) | EDF (E) | sources (S) "
             "| P+E | E+S | P+E+S |")
    L.append("|---|---:|---:|---:|---|---|---|---|---|---|")
    groups = np.array([st[s]["client"] for s in ids])
    for o in OUTCOMES:
        if o not in lab:
            continue
        sel = np.array([s in lab[o] for s in ids])
        y = np.array([lab[o].get(s, 0) for s in ids])[sel]
        if y.sum() < 10:
            continue
        g = groups[sel]
        D = disc_score([s for s, k in zip(ids, sel) if k], pz, o)
        try:
            dauc = roc_auc_score(y, D[:, 0])
        except ValueError:
            dauc = float("nan")
        sets = {"P": P, "E": E, "S": S}
        cells = []
        for combo in ("P", "E", "S", "PE", "ES", "PES"):
            X = np.hstack([sets[c][sel] for c in combo] + [C[sel]])
            mu, sd = cv_auc(X, y, g)
            cells.append(f"{mu:.2f} +/-{sd:.2f}")
        L.append(f"| {o} | {len(y)} | {int(y.sum())} | {dauc:.2f} | " + " | ".join(cells) + " |")
    L.append("")
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L))
    print("wrote", OUT_MD)


if __name__ == "__main__":
    main()
