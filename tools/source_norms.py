"""Are a study's brain sources typical for its age and condition?

Each accepted (non-line) ICA component is put in a coarse SOURCE CELL:
lobe of its sLORETA peak (frontal / temporal / parietal / occipital /
cingulate-deep = limbic + sub-lobar) x side (x < 0 left) x band of its FFT
peak (delta / theta / alpha / fast = beta + gamma) -- 40 cells. A study's cell
share is the % of recording variance in that cell; two sources in one cell are
judged together.

AGE REGRESSION, per cell and condition, on one study per client (the earliest).
Most studies have no source in a given cell, so one mean and SD would not fit;
the model has two parts:
    prev(age)      logistic in log(age) + log(age)^2: chance of having a source
                   in the cell (share >= 0.5%) at this age
    mu, sd(age)    among studies that have one: log(share) mean quadratic in
                   log(age), SD linear in log(age) from |residual|, two passes
                   trimming |z| > 4. Under 30 such studies: constant mean and SD.
                   Under 8: no z, prevalence only.
Each cell of a study then gets
    z       how strong the source is against others of that age that have one
    tail    prev * P(Z >= z) when present, 1 - prev when absent
    flag    strong -- share >= 2% and tail <= 1%
            rare   -- share >= 2% in a cell under 5% of that age have
            absent -- share < 0.5% in a cell >= 90% of that age have
The study verdict is ONE score: atyp = sum of w * -log(tail), w = the study's
share (present) or the expected share at that age (absent), so the cells holding
the recording count. log(atyp) is regressed on age the same way and ranked ->
atyp_pctile; >= 95 = unusual source make-up for age.

Every stored study is scored by models fitted WITHOUT its own client (5 folds by
client), so nobody is compared with themselves. typicality() for one EDF uses
the stored full fit, or refits without the client when they are in the reference.

Replaces the nearest-80-peers comparison, whose window had to stretch at the age
extremes (few young children and elderly clients): a 4-year-old's "peers" ran well
into later childhood.

Tables: source_models, source_calib, source_typ, source_atyp. The label analysis
goes to research/validation_2026/out/SOURCE_TYPICALITY.md.

A SCREENING POPULATION, NOT NORMS: "unusual" means unusual among referred
clients of that age.

    py tools/source_norms.py [--store DIR]
"""
import argparse
import json
import math
import os
import sqlite3
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

DEFAULT_STORE = r"C:\BrainPanel\source_db"
OUT_MD = os.path.join(ROOT, "research", "validation_2026", "out", "SOURCE_TYPICALITY.md")
PRESENT = 0.5        # % share that counts as "has a source in the cell"
MIN_FLAG = 2.0       # % share below which nothing is called strong/rare
STRONG_TAIL = 0.01
RARE_PREV = 0.05
UNCOMMON_PREV = 0.25  # page wording only
ABSENT_PREV = 0.90
MIN_EVENTS = 5       # fewer present/absent studies than this: constant prevalence
MIN_SLOPE_N = 30     # fewer present studies than this: constant mean and SD
MIN_Z_N = 8          # fewer than this: no z
MIN_SD = 0.15        # floor on the log(share) SD
TRIM_Z = 4.0
TAIL_FLOOR = 1e-4
N_FOLDS = 5
AGE_MIN, AGE_MAX = 3, 90
AGE_REF = 20.0       # log(age) is centred here

LOBES = {"Frontal": "frontal", "Temporal": "temporal", "Parietal": "parietal",
         "Occipital": "occipital", "Limbic": "cingulate/deep", "Sub-lobar": "cingulate/deep"}
BANDS = {"Delta": "delta", "Theta": "theta", "Alpha": "alpha", "Beta": "fast", "Gamma": "fast"}
CELLS = [f"{s} {l} {b}" for l in dict.fromkeys(LOBES.values()) for s in ("L", "R")
         for b in dict.fromkeys(BANDS.values())]

SCHEMA = """
DROP TABLE IF EXISTS source_models;
DROP TABLE IF EXISTS source_calib;
DROP TABLE IF EXISTS source_typ;
DROP TABLE IF EXISTS source_atyp;
CREATE TABLE source_models (
  cell TEXT, cond TEXT, logit_coef TEXT, mean_coef TEXT, sd_coef TEXT, n INTEGER, n_present INTEGER,
  PRIMARY KEY (cell, cond));
CREATE TABLE source_calib (cond TEXT PRIMARY KEY, mean_coef TEXT, sd_coef TEXT, resid_z TEXT, n INTEGER);
CREATE TABLE source_typ (
  study_id TEXT, cell TEXT, pct REAL, prev REAL, z REAL, pctile REAL, flag TEXT,
  PRIMARY KEY (study_id, cell));
CREATE TABLE source_atyp (
  study_id TEXT PRIMARY KEY, unusual_pct REAL, n_unusual INTEGER, n_absent INTEGER,
  unusual_cells TEXT, absent_cells TEXT, atyp REAL, atyp_pctile REAL);
"""


def cell_of(lobe, x, band):
    lo, b = LOBES.get(lobe), BANDS.get(band)
    if lo is None or b is None:
        return None
    return f"{'L' if x < 0 else 'R'} {lo} {b}"


def study_cells(con):
    """{study_id: np.array(len(CELLS)) of % share}"""
    idx = {c: i for i, c in enumerate(CELLS)}
    out = {}
    for sid, pct, lobe, x, band in con.execute(
            "SELECT study_id, pct, lobe, x, band FROM components WHERE accept=1 AND line=0"):
        c = cell_of(lobe, x, band)
        if c is None:
            continue
        out.setdefault(sid, np.zeros(len(CELLS)))[idx[c]] += pct
    return out


def reference(con):
    """(studies, cells, ref): every ok study's meta, its cell shares, and the
    one-study-per-client reference set per condition."""
    st = {r[0]: dict(client=r[1] or r[0], cond=r[2], age=r[3], when=r[4] or "")
          for r in con.execute("SELECT id, client, cond, age, rec_start FROM studies WHERE status='ok'")}
    cells = study_cells(con)
    first = {}
    for sid, s in sorted(st.items(), key=lambda kv: kv[1]["when"]):
        if sid in cells and s["cond"] in ("EC", "EO") and s["age"] and AGE_MIN <= s["age"] <= AGE_MAX:
            first.setdefault((s["client"], s["cond"]), sid)
    ref = {c: [sid for (cl, cc), sid in first.items() if cc == c] for c in ("EC", "EO")}
    return st, cells, ref


# ------------------------------------------------------------------ the two-part model
def _d(age, deg):
    la = np.log(np.clip(np.asarray(age, float), AGE_MIN, AGE_MAX) / AGE_REF)
    return np.vstack([la ** k for k in range(deg + 1)]).T


def _phi_upper(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


def fit_mean_sd(age, y, deg):
    """Polynomial mean + SD linear in log(age), trimmed; constant when deg == 0."""
    keep = np.ones(len(y), bool)
    sd_deg = 1 if deg else 0
    for _ in range(2):
        mc = np.linalg.lstsq(_d(age[keep], deg), y[keep], rcond=None)[0]
        res = y - _d(age, deg) @ mc
        sc = np.linalg.lstsq(_d(age[keep], sd_deg), np.abs(res[keep]) * np.sqrt(np.pi / 2),
                             rcond=None)[0]
        sd = np.clip(_d(age, sd_deg) @ sc, MIN_SD, None)
        keep = np.abs(res / sd) <= TRIM_Z
    return mc, sc


def fit_cell(age, share):
    from sklearn.linear_model import LogisticRegression
    pres = share >= PRESENT
    n1, n0 = int(pres.sum()), int((~pres).sum())
    if n1 < MIN_EVENTS or n0 < MIN_EVENTS:
        p = (n1 + 0.5) / (len(share) + 1)
        logit = [math.log(p / (1 - p)), 0.0, 0.0]
    else:
        X = _d(age, 2)[:, 1:]
        m = LogisticRegression(C=1.0, max_iter=2000).fit(X, pres.astype(int))
        logit = [float(m.intercept_[0]), float(m.coef_[0][0]), float(m.coef_[0][1])]
    mc = sc = None
    if n1 >= MIN_Z_N:
        mc, sc = fit_mean_sd(age[pres], np.log(share[pres]), 2 if n1 >= MIN_SLOPE_N else 0)
        mc, sc = mc.tolist(), sc.tolist()
    return dict(logit=logit, mean=mc, sd=sc, n=len(share), n_present=n1)


def fit_models(age, shares):
    return [fit_cell(age, shares[:, k]) for k in range(len(CELLS))]


def score(v, age, models):
    """One study against the cell models: per cell prev, z, tail, pctile, flag,
    and the study's atyp score."""
    prev, zs, tails, pct, flags = [], [], [], [], []
    atyp = 0.0
    a = np.array([age], float)
    x2 = _d(a, 2)
    for k, m in enumerate(models):
        p = float(1 / (1 + np.exp(-(x2 @ np.array(m["logit"]))[0])))
        mu = sd = None
        if m["mean"] is not None:
            mu = float((_d(a, len(m["mean"]) - 1) @ np.array(m["mean"]))[0])
            sd = max(float((_d(a, len(m["sd"]) - 1) @ np.array(m["sd"]))[0]), MIN_SD)
        s = float(v[k])
        z = None
        if s >= PRESENT:
            if mu is not None:
                z = (math.log(s) - mu) / sd
                tail = p * _phi_upper(z)
            else:
                tail = p
            tail = max(tail, TAIL_FLOOR)
            w = s / 100
            pc = 100 * (1 - tail)
        else:
            tail = max(1 - p, TAIL_FLOOR)
            w = p * math.exp(mu) / 100 if mu is not None else 0.0
            pc = 50 * (1 - p)
        atyp += w * -math.log(tail)
        if s >= MIN_FLAG and p < RARE_PREV:
            f = "rare"
        elif s >= MIN_FLAG and tail <= STRONG_TAIL:
            f = "strong"
        elif s < PRESENT and p >= ABSENT_PREV:
            f = "absent"
        else:
            f = ""
        prev.append(p); zs.append(z); tails.append(tail); pct.append(pc); flags.append(f)
    return dict(prev=prev, z=zs, tail=tails, pctile=pct, flag=flags, atyp=atyp)


def fit_calib(age, atyp):
    """Age regression of log(atyp); resid_z = the reference to rank a study in."""
    y = np.log(np.clip(atyp, 1e-3, None))
    mc, sc = fit_mean_sd(age, y, 2)
    res = (y - _d(age, 2) @ mc) / np.clip(_d(age, 1) @ sc, MIN_SD, None)
    return dict(mean=mc.tolist(), sd=sc.tolist(), resid=np.sort(res).round(4).tolist())


def atyp_pct(calib, age, atyp):
    a = np.array([age], float)
    mu = float((_d(a, 2) @ np.array(calib["mean"]))[0])
    sd = max(float((_d(a, 1) @ np.array(calib["sd"]))[0]), MIN_SD)
    z = (math.log(max(atyp, 1e-3)) - mu) / sd
    ref = np.array(calib["resid"])
    return float(100 * np.searchsorted(ref, z, side="right") / len(ref))


# ------------------------------------------------------------------ one new study
def typicality(comps, age, cond, store=DEFAULT_STORE, client=None, frozen=None):
    """Age-regressed typicality of one study's sources from
    source_summary.load()['comps'], for the source page. None when age or
    condition are unknown. frozen: the bundle's entry for this condition (no database).
    Otherwise a client in the reference set is left out of the fit."""
    if age is None or cond not in ("EC", "EO") or not AGE_MIN <= age <= AGE_MAX:
        return None
    if frozen is not None:
        if frozen["cells"] != CELLS:
            raise ValueError("bundle's source cells differ from this code's")
        models, calib, n_ref = frozen["models"], frozen["calib"], frozen["n"]
    else:
        con = sqlite3.connect(os.path.join(store, "sources.db"))
        rows = {r[0]: r[1:] for r in con.execute(
            "SELECT cell, logit_coef, mean_coef, sd_coef, n FROM source_models WHERE cond=?", (cond,))}
        cal = con.execute("SELECT mean_coef, sd_coef, resid_z, n FROM source_calib WHERE cond=?",
                          (cond,)).fetchone()
        if not rows or cal is None:
            con.close()
            return None
        st, cells, ref = reference(con)
        con.close()
        keep = [s for s in ref[cond] if st[s]["client"] != client]
        if len(keep) < len(ref[cond]):
            models = fit_models(np.array([st[s]["age"] for s in keep], float),
                                np.array([cells[s] for s in keep]))
        else:
            models = [dict(logit=json.loads(rows[c][0]), mean=json.loads(rows[c][1]),
                           sd=json.loads(rows[c][2])) for c in CELLS]
        calib = dict(mean=json.loads(cal[0]), sd=json.loads(cal[1]), resid=json.loads(cal[2]))
        n_ref = cal[3]
    tot = sum(c["pct"] for c in comps) or 1.0
    v = np.zeros(len(CELLS))
    cell_k = {}
    for c in comps:
        if not c["accept"]:
            continue
        cell = cell_of(c["lobe"], float(c["xyz"][0]), band_name(c["hz"]))
        if cell:
            k = CELLS.index(cell)
            v[k] += 100 * c["pct"] / tot
            cell_k[c["rank"]] = k
    r = score(v, age, models)
    ap = atyp_pct(calib, age, r["atyp"])
    per, flagged = {}, set()
    for rank, k in cell_k.items():
        p, z, f = r["prev"][k], r["z"][k], r["flag"][k]
        ptxt = "<1%" if p < 0.01 else f"{100 * p:.0f}%"
        ztxt = f"z {z:+.1f} · {ptxt}" if z is not None else f"· {ptxt}"
        if f == "rare":
            per[rank] = (f"rare · {ptxt}", "#c62828")
            flagged.add(rank)
        elif f == "strong":
            per[rank] = (ztxt, "#c62828")
            flagged.add(rank)
        elif p < UNCOMMON_PREV or (z is not None and abs(z) >= 2):
            per[rank] = (ztxt, "#b26a00")
        else:
            per[rank] = (ztxt, "#2e7d32")
    absent = [(CELLS[k], 100 * r["prev"][k]) for k in range(len(CELLS)) if r["flag"][k] == "absent"]
    return dict(per_rank=per, flagged=flagged, atyp_pctile=ap, absent=absent, n_ref=n_ref,
                cond=cond, age=age)


def band_name(hz):
    for name, lo, hi in (("Delta", 0, 4), ("Theta", 4, 8), ("Alpha", 8, 13), ("Beta", 13, 30)):
        if lo <= hz < hi:
            return name
    return "Gamma"


# ------------------------------------------------------------------ whole database
def build(con):
    con.executescript(SCHEMA)
    st, cells, ref = reference(con)
    rng = np.random.default_rng(0)
    scored = {}
    for cond in ("EC", "EO"):
        ids = ref[cond]
        age = np.array([st[s]["age"] for s in ids], float)
        shares = np.array([cells[s] for s in ids])
        # full fit: stored, and used for clients outside the reference set
        full = fit_models(age, shares)
        for c, m in zip(CELLS, full):
            con.execute("INSERT INTO source_models VALUES (?,?,?,?,?,?,?)", (
                c, cond, json.dumps(m["logit"]), json.dumps(m["mean"]), json.dumps(m["sd"]),
                m["n"], m["n_present"]))
        # one model per fold, each without that fold's clients
        clients = sorted({st[s]["client"] for s in ids})
        fold = dict(zip(clients, rng.permutation(len(clients)) % N_FOLDS))
        f_ids = np.array([fold[st[s]["client"]] for s in ids])
        by_fold = [fit_models(age[f_ids != j], shares[f_ids != j]) for j in range(N_FOLDS)]
        # the calibration reference: out-of-fold atyp of the reference set
        oof = np.array([score(cells[s], st[s]["age"], by_fold[fold[st[s]["client"]]])["atyp"]
                        for s in ids])
        cal = fit_calib(age, oof)
        con.execute("INSERT INTO source_calib VALUES (?,?,?,?,?)", (
            cond, json.dumps(cal["mean"]), json.dumps(cal["sd"]), json.dumps(cal["resid"]), len(ids)))
        for sid, s in st.items():
            if sid not in cells or s["cond"] != cond or not s["age"] or not AGE_MIN <= s["age"] <= AGE_MAX:
                continue
            models = by_fold[fold[s["client"]]] if s["client"] in fold else full
            r = score(cells[sid], s["age"], models)
            scored[sid] = r
            v = cells[sid]
            con.executemany("INSERT INTO source_typ VALUES (?,?,?,?,?,?,?)", [
                (sid, CELLS[k], float(v[k]), 100 * r["prev"][k], r["z"][k], r["pctile"][k], r["flag"][k])
                for k in range(len(CELLS))])
            un = [k for k in range(len(CELLS)) if r["flag"][k] in ("strong", "rare")]
            ab = [k for k in range(len(CELLS)) if r["flag"][k] == "absent"]
            con.execute("INSERT INTO source_atyp VALUES (?,?,?,?,?,?,?,?)", (
                sid, float(sum(v[k] for k in un)), len(un), len(ab),
                "; ".join(f"{CELLS[k]} ({r['flag'][k]})" for k in un),
                "; ".join(CELLS[k] for k in ab), r["atyp"], atyp_pct(cal, s["age"], r["atyp"])))
    con.commit()
    print(f"scored {len(scored)} studies against age regressions (EC ref {len(ref['EC'])}, "
          f"EO ref {len(ref['EO'])} clients)")
    return ref


# ------------------------------------------------------------------ analysis
def analyze(con, ref):
    from label_join import auc, auc_ci
    rng = np.random.default_rng(0)
    keep = {sid for ids in ref.values() for sid in ids}
    cond = {r[0]: r[1] for r in con.execute("SELECT id, cond FROM studies")}
    lab = {}
    for sid, o, v, cf in con.execute("SELECT study_id, outcome, value, conf FROM labels"):
        if cf == "high" and sid in keep:
            lab.setdefault(o, {})[sid] = v
    atyp = {r[0]: r[1:5] for r in con.execute(
        "SELECT study_id, unusual_pct, n_unusual, n_absent, atyp_pctile FROM source_atyp")}
    typ = {}
    for sid, cell, pctile, flag in con.execute("SELECT study_id, cell, pctile, flag FROM source_typ"):  # all 40 cells
        typ.setdefault(sid, {})[cell] = (pctile, flag)

    L = ["# Are the brain sources typical, and does unusual go with the doctor's comments?\n",
         "Generated by `tools/source_norms.py`. Each accepted ICA component -> a source cell "
         "(lobe x side x band, 40 cells); each cell regressed on age per condition (chance of "
         "having the source; strength among those who do), one study per client, each study scored "
         "by models fitted without its own client. "
         "Flags: **strong** = share >= 2%, tail <= 1%; **rare** = >= 2% in a cell < 5% of that age "
         "have; **absent** = < 0.5% in a cell >= 90% of that age have. "
         "A screening population, not norms. Labels: matched Doctor's QA review, high-confidence; "
         "`pdr_slow` is the alpha-anchored PDR label.\n"]

    # how often is a study unusual at all
    L.append("## How common are unusual sources?\n")
    L.append("| condition | studies | atyp_pctile >= 95 | >= 1 strong/rare cell | median unusual % "
             "| >= 1 absent cell |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for c in ("EC", "EO"):
        ids = [s for s in ref[c] if s in atyp]
        a = np.array([atyp[s] for s in ids], float)
        L.append(f"| {c} | {len(ids)} | {100 * (a[:, 3] >= 95).mean():.0f}% | "
                 f"{100 * (a[:, 1] > 0).mean():.0f}% | "
                 f"{np.median(a[:, 0]):.1f} | {100 * (a[:, 2] > 0).mean():.0f}% |")
    L.append("")
    L.append("Most commonly flagged cells (EC reference set):\n")
    cnt = {}
    for s in ref["EC"]:
        for cell, (p, f) in typ.get(s, {}).items():
            if f:
                cnt[(cell, f)] = cnt.get((cell, f), 0) + 1
    L.append("| cell | flag | studies |")
    L.append("|---|---|---:|")
    for (cell, f), k in sorted(cnt.items(), key=lambda kv: -kv[1])[:10]:
        L.append(f"| {cell} | {f} | {k} |")
    L.append("")

    # is the age regression doing its job?
    L.append("## Calibration of the age regression\n")
    L.append("Out-of-client scores on the reference set. Flat rows across age = no leftover age "
             "trend. z = strength of present sources (should be mean ~0, SD ~1).\n")
    L.append("| condition | age | studies | mean atyp pctile | atyp pctile >= 95 | >= 1 strong/rare cell "
             "| source z mean | source z SD |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|")
    age = {r[0]: r[1] for r in con.execute("SELECT id, age FROM studies")}
    zs = {}
    for sid, z in con.execute("SELECT study_id, z FROM source_typ WHERE z IS NOT NULL"):
        zs.setdefault(sid, []).append(z)
    for c in ("EC", "EO"):
        for lo, hi in ((3, 7), (8, 12), (13, 17), (18, 29), (30, 49), (50, 64), (65, 90)):
            ids = [s for s in ref[c] if s in atyp and lo <= age[s] <= hi]
            if not ids:
                continue
            a = np.array([atyp[s] for s in ids], float)
            z = np.array([v for s in ids for v in zs.get(s, [])])
            L.append(f"| {c} | {lo}-{hi} | {len(ids)} | {a[:, 3].mean():.0f} | "
                     f"{100 * (a[:, 3] >= 95).mean():.0f}% | {100 * (a[:, 1] > 0).mean():.0f}% | "
                     f"{z.mean():+.2f} | {z.std():.2f} |")
    L.append("")

    L.append("## Study-level scores vs the doctor's labels (rank AUC, 95% bootstrap CI)\n")
    L.append("AUC > 0.5: higher score in label-positive studies. * = CI excludes 0.5.\n")
    L.append("| outcome | cond | n | pos | atypicality pctile | unusual % | n unusual cells "
             "| n absent cells |")
    L.append("|---|---|---:|---:|---|---|---|---|")
    outcomes = [o for o in ("clinical_abnorm", "pdr_slow", "paroxysmal", "drowsiness") if o in lab]
    for o in outcomes:
        for c in ("EC", "EO"):
            ids = [s for s in lab[o] if cond[s] == c and s in atyp]
            y = np.array([lab[o][s] for s in ids])
            if y.sum() < 8 or len(y) - y.sum() < 8:
                continue
            cells_ = []
            for j in (3, 0, 1, 2):
                x = np.array([atyp[s][j] for s in ids], float)
                a = auc(x, y)
                lo, hi = auc_ci(x, y, rng)
                cells_.append(f"{a:.2f}{'*' if lo > 0.5 or hi < 0.5 else ''} ({lo:.2f}-{hi:.2f})")
            L.append(f"| {o} | {c} | {len(y)} | {int(y.sum())} | " + " | ".join(cells_) + " |")
    L.append("")

    L.append("## Which source cells differ in label-positive studies\n")
    L.append("Per cell, AUC of the study's age-adjusted percentile for that cell (> 0.5: more of "
             "that source than expected for age in positives). Top 5 per outcome/condition by |AUC - 0.5|; "
             "* = CI excludes 0.5. With 15-25 positives, treat single cells as leads, not findings.\n")
    for o in outcomes:
        for c in ("EC", "EO"):
            ids = [s for s in lab[o] if cond[s] == c and s in typ]
            y = np.array([lab[o][s] for s in ids])
            if y.sum() < 8 or len(y) - y.sum() < 8:
                continue
            res = []
            for cell in CELLS:
                # a study with no row for the cell had share 0: rank it with the zeros
                x = np.array([typ[s].get(cell, (None, ""))[0] for s in ids], dtype=object)
                if all(v is None for v in x):
                    continue
                fill = min(v for v in x if v is not None)
                x = np.array([fill if v is None else v for v in x], float)
                res.append((cell, auc(x, y), x))
            res.sort(key=lambda t: -abs(t[1] - 0.5))
            L.append(f"**{o} — {c}** (n={len(y)}, positive {int(y.sum())})\n")
            L.append("| cell | AUC | 95% CI |")
            L.append("|---|---:|---|")
            for cell, a, x in res[:5]:
                lo, hi = auc_ci(x, y, rng)
                L.append(f"| {cell} | {a:.2f}{'*' if lo > 0.5 or hi < 0.5 else ''} | {lo:.2f}-{hi:.2f} |")
            L.append("")
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L))
    print("wrote", OUT_MD)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=DEFAULT_STORE)
    a = ap.parse_args()
    con = sqlite3.connect(os.path.join(a.store, "sources.db"), timeout=60)
    ref = build(con)
    analyze(con, ref)


if __name__ == "__main__":
    main()
