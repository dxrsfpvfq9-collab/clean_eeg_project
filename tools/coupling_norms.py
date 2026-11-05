"""Amplitude-envelope coupling of the source components against age-regressed
norms, per condition, over the source database's one-study-per-client set.

Raw r cannot be compared between recordings: partial r and its family-wise
threshold both move with the number of components and the recording length
(thr 0.12-0.56 across the corpus). Dividing r by thr was tried first and made it
worse (rho -0.6 with the number of pairs), so both models carry the recording's
size as covariates instead. A link is |r| >= thr.

Two comparisons:
  band strength   log RMS(r) over all pairs in a band, regressed on age + log(pairs)
                  + log(thr): is this recording more or less coupled than others
                  of that age and size?
  link            each pair -> a type (region x region x band; region = side x
                  lobe), logistic chance of a link in that direction by age and
                  log(pairs). A link is "uncommon" when under UNCOMMON_PREV of
                  such pairs show one at that age.
A z for a single link is deliberately not reported: links are selected for being
extreme, so nearly every one would read as far out of range. Stored studies are
scored by models fitted without their own client (5 folds). A screening
population, not norms.

  py tools/coupling_norms.py            build tables coupling_typ + coupling_links
                                        and research/validation_2026/out/COUPLING_NORMS.md
"""
import argparse
import math
import os
import sqlite3
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from source_norms import (AGE_MAX, AGE_MIN, DEFAULT_STORE, LOBES, N_FOLDS, ROOT,  # noqa: E402
                          _d)

OUT_MD = os.path.join(ROOT, "research", "validation_2026", "out", "COUPLING_NORMS.md")
COUPLE_BANDS = ("Theta", "Alpha", "Beta")
MIN_PAIRS = 6            # fewer pairs in a band: too noisy for a strength score
UNCOMMON_PREV = 0.01
MIN_EVENTS = 5
MIN_SD_S = 0.05          # floor on the strength SD (log r units)
LOGIT_DEG = 2

SCHEMA = """
DROP TABLE IF EXISTS coupling_typ;
DROP TABLE IF EXISTS coupling_links;
CREATE TABLE coupling_typ (
  study_id TEXT, band TEXT, n_pairs INTEGER, n_links INTEGER, n_uncommon INTEGER,
  strength REAL, z REAL, pctile REAL, PRIMARY KEY (study_id, band));
CREATE TABLE coupling_links (
  study_id TEXT, band TEXT, rank_a INTEGER, rank_b INTEGER, type TEXT, r REAL, prev REAL,
  PRIMARY KEY (study_id, band, rank_a, rank_b));
"""


def region(lobe, x):
    lo = LOBES.get(lobe)
    return None if lo is None else f"{'L' if x < 0 else 'R'} {lo}"


def pair_type(ra, rb, band):
    return " – ".join(sorted((ra, rb))) + f" | {band}"


def load_pairs(con):
    """Every pair with a usable threshold: {study: {band: [(a, b, type, r, u, thr)]}}."""
    reg = {(s, k): region(lo, x) for s, k, lo, x in con.execute(
        "SELECT study_id, rank, lobe, x FROM components WHERE accept=1")}
    out = {}
    for s, b, a, c, r, thr in con.execute(
            "SELECT study_id, band, rank_a, rank_b, r, thr FROM edges WHERE thr > 0"):
        ra, rc = reg.get((s, a)), reg.get((s, c))
        if ra is None or rc is None:
            continue
        out.setdefault(s, {}).setdefault(b, []).append((a, c, pair_type(ra, rc, b), r, r / thr, thr))
    return out


def reference(con, pairs):
    st = {r[0]: dict(client=r[1] or r[0], cond=r[2], age=r[3], when=r[4] or "")
          for r in con.execute("SELECT id, client, cond, age, rec_start FROM studies WHERE status='ok'")}
    first = {}
    for sid, s in sorted(st.items(), key=lambda kv: kv[1]["when"]):
        if sid in pairs and s["cond"] in ("EC", "EO") and s["age"] and AGE_MIN <= s["age"] <= AGE_MAX:
            first.setdefault((s["client"], s["cond"]), sid)
    ref = {c: [sid for (cl, cc), sid in first.items() if cc == c] for c in ("EC", "EO")}
    return st, ref


def strength(rows):
    return 0.5 * math.log(np.mean([p[3] ** 2 for p in rows]) + 1e-6)


def _size(n):
    return math.log(max(n, 1) / 55.0)      # 55 pairs = the median recording


def _xs(age, size, thr):
    """Strength design: age curve + recording size."""
    return np.column_stack([_d(age, 2), size, thr])


def _xl(age, size):
    """Link design, without the intercept."""
    return np.column_stack([_d(age, LOGIT_DEG)[:, 1:], size])


def _logit(age, size, y):
    from sklearn.linear_model import LogisticRegression
    n1, n0 = int(y.sum()), int((1 - y).sum())
    if n1 < MIN_EVENTS or n0 < MIN_EVENTS:
        p = (n1 + 0.5) / (len(y) + 1)
        return [math.log(p / (1 - p)), 0.0, 0.0, 0.0]
    m = LogisticRegression(C=1.0, max_iter=2000).fit(_xl(age, size), y)
    return [float(m.intercept_[0]), *map(float, m.coef_[0])]


def fit(ids, st, pairs):
    """Link models (type, direction) and band-strength models from the given studies."""
    by_type = {}
    by_band = {b: [] for b in COUPLE_BANDS}
    for s in ids:
        age = st[s]["age"]
        for b, rows in pairs[s].items():
            for p in rows:
                by_type.setdefault(p[2], []).append((age, p[4], _size(len(rows))))
            if len(rows) >= MIN_PAIRS:
                by_band[b].append((age, _size(len(rows)), math.log(rows[0][5]), strength(rows)))
    links = {}
    for t, v in by_type.items():
        a = np.array(v)
        links[t] = (_logit(a[:, 0], a[:, 2], (a[:, 1] >= 1).astype(int)),
                    _logit(a[:, 0], a[:, 2], (a[:, 1] <= -1).astype(int)), len(a))
    bands = {}
    for b, v in by_band.items():
        v = np.array(v)
        age, size, thr, y = v.T
        keep = np.ones(len(y), bool)
        for _ in range(2):
            mc = np.linalg.lstsq(_xs(age[keep], size[keep], thr[keep]), y[keep], rcond=None)[0]
            res = y - _xs(age, size, thr) @ mc
            sc = np.linalg.lstsq(_d(age[keep], 1), np.abs(res[keep]) * np.sqrt(np.pi / 2), rcond=None)[0]
            sd = np.clip(_d(age, 1) @ sc, MIN_SD_S, None)
            keep = np.abs(res / sd) <= 4
        bands[b] = dict(mean=mc, sd=sc, resid=np.sort(res / sd), n=len(y))
    return dict(links=links, bands=bands, n=len(ids))


def link_prev(models, type_, u, age, n_pairs):
    """Chance of a link in this direction, for this pair type at this age and size."""
    m = models["links"].get(type_)
    if m is None:
        return None
    c = np.array(m[0 if u > 0 else 1])
    x = _xl(np.array([age], float), np.array([_size(n_pairs)]))
    return float(1 / (1 + np.exp(-(c[0] + (x @ c[1:])[0]))))


def band_score(models, band, s, age, n_pairs, thr):
    m = models["bands"][band]
    a = np.array([age], float)
    mu = float((_xs(a, np.array([_size(n_pairs)]), np.array([math.log(thr)])) @ m["mean"])[0])
    z = (s - mu) / max(float((_d(a, 1) @ m["sd"])[0]), MIN_SD_S)
    return z, float(100 * np.searchsorted(m["resid"], z, side="right") / len(m["resid"]))


def score_rows(band, rows, age, models):
    links = []
    for a, c, t, r, u, _thr in rows:
        if abs(u) >= 1:
            links.append(dict(a=a, b=c, type=t, r=r, prev=link_prev(models, t, u, age, len(rows))))
    z = pc = s = None
    if len(rows) >= MIN_PAIRS:
        s = strength(rows)
        z, pc = band_score(models, band, s, age, len(rows), rows[0][5])
    return dict(band=band, n_pairs=len(rows), links=links, strength=s, z=z, pctile=pc,
                n_uncommon=sum(1 for k in links if k["prev"] is not None and k["prev"] < UNCOMMON_PREV))


def coupling_typicality(use, res, age, cond, store=DEFAULT_STORE, client=None, frozen=None):
    """For page_networks: analyze_networks() output against age norms. None when age
    or condition are unknown. frozen: the bundle's entry for this condition (no
    database). Otherwise a client in the reference is left out of the fit."""
    if age is None or cond not in ("EC", "EO") or not AGE_MIN <= age <= AGE_MAX:
        return None
    if frozen is not None:
        models, n_ref = frozen, frozen["n"]
    else:
        con = sqlite3.connect(os.path.join(store, "sources.db"))
        pairs = load_pairs(con)
        st, ref = reference(con, pairs)
        con.close()
        ids = [s for s in ref[cond] if st[s]["client"] != client]
        if len(ids) < 50:
            return None
        models, n_ref = fit(ids, st, pairs), len(ids)
    out = {}
    for rb in res:
        thr = rb["thr"]
        rows = []
        if thr and thr > 0 and not math.isnan(thr):
            for i in range(len(use)):
                for j in range(i + 1, len(use)):
                    ra = region(use[i]["lobe"], float(use[i]["xyz"][0]))
                    rc = region(use[j]["lobe"], float(use[j]["xyz"][0]))
                    if ra and rc:
                        r = float(rb["r"][i, j])
                        rows.append((use[i]["rank"], use[j]["rank"],
                                     pair_type(ra, rc, rb["band"]), r, r / thr, thr))
        out[rb["band"]] = score_rows(rb["band"], rows, age, models)
    return dict(bands=out, n_ref=n_ref, cond=cond, age=age)


def verdict(pc):
    if pc is None:
        return "too few pairs to score", "#777"
    if pc >= 95:
        return "strongly coupled for age", "#c62828"
    if pc <= 5:
        return "weakly coupled for age", "#c62828"
    if pc >= 85 or pc <= 15:
        return "somewhat " + ("strong" if pc >= 85 else "weak") + " for age", "#b26a00"
    return "typical for age", "#2e7d32"


def build(con):
    con.executescript(SCHEMA)
    pairs = load_pairs(con)
    st, ref = reference(con, pairs)
    rng = np.random.default_rng(0)
    for cond in ("EC", "EO"):
        ids = ref[cond]
        clients = sorted({st[s]["client"] for s in ids})
        fold = dict(zip(clients, rng.permutation(len(clients)) % N_FOLDS))
        by_fold = [fit([s for s in ids if fold[st[s]["client"]] != j], st, pairs)
                   for j in range(N_FOLDS)]
        full = fit(ids, st, pairs)
        for sid, s in st.items():
            if sid not in pairs or s["cond"] != cond or not s["age"] or not AGE_MIN <= s["age"] <= AGE_MAX:
                continue
            m = by_fold[fold[s["client"]]] if s["client"] in fold else full
            for b, rows in pairs[sid].items():
                r = score_rows(b, rows, s["age"], m)
                con.execute("INSERT INTO coupling_typ VALUES (?,?,?,?,?,?,?,?)", (
                    sid, b, r["n_pairs"], len(r["links"]), r["n_uncommon"], r["strength"],
                    r["z"], r["pctile"]))
                con.executemany("INSERT INTO coupling_links VALUES (?,?,?,?,?,?,?)", [
                    (sid, b, k["a"], k["b"], k["type"], k["r"], k["prev"]) for k in r["links"]])
        print(cond, len(ids), "clients", flush=True)
    con.commit()
    return pairs, st, ref


def analyze(con, pairs, st, ref):
    from scipy.stats import spearmanr
    from label_join import auc, auc_ci
    rng = np.random.default_rng(0)
    typ = {}
    for sid, b, np_, nl, nu, s, z, pc in con.execute("SELECT * FROM coupling_typ"):
        typ.setdefault(sid, {})[b] = (np_, nl, nu, s, z, pc)
    L = ["# Source coupling against age-regressed norms\n",
         "Generated by `tools/coupling_norms.py`. **Band strength** = log RMS(r) over pairs, regressed "
         "on age, log(pairs) and log(threshold). **Link** = |r| >= the recording's family-wise "
         f"threshold; *uncommon* = under {100 * UNCOMMON_PREV:g}% of that pair type link in that "
         "direction at that age and recording size. Out-of-client. A screening population, not norms.\n"]

    L.append("## Is the recording's size removed?\n")
    L.append("Spearman rho with the number of pairs in the band (raw mean |r| vs the adjusted score).\n")
    L.append("| band | condition | mean abs r | strength z |")
    L.append("|---|---|---:|---:|")
    raw = {(r[0], r[1]): r[2] for r in con.execute(
        "SELECT study_id, band, AVG(ABS(r)) FROM edges GROUP BY 1, 2")}
    for b in COUPLE_BANDS:
        for c in ("EC", "EO"):
            ids = [s for s in ref[c] if b in typ.get(s, {}) and typ[s][b][4] is not None]
            n = [typ[s][b][0] for s in ids]
            L.append(f"| {b} | {c} | {spearmanr(n, [raw[(s, b)] for s in ids])[0]:+.2f} | "
                     f"{spearmanr(n, [typ[s][b][4] for s in ids])[0]:+.2f} |")
    L.append("")

    L.append("## Calibration by age (reference set, out-of-client)\n")
    L.append("| condition | age | studies | strength z mean | z SD | >= 95th, any band | <= 5th, any band "
             "| >= 1 link | >= 1 uncommon link |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for c in ("EC", "EO"):
        for lo, hi in ((3, 7), (8, 12), (13, 17), (18, 29), (30, 49), (50, 64), (65, 90), (3, 90)):
            ids = [s for s in ref[c] if lo <= st[s]["age"] <= hi and s in typ]
            if not ids:
                continue
            z = [v[4] for s in ids for v in typ[s].values() if v[4] is not None]
            pcs = [[v[5] for v in typ[s].values() if v[5] is not None] for s in ids]
            hi95 = np.mean([any(p >= 95 for p in q) for q in pcs])
            lo5 = np.mean([any(p <= 5 for p in q) for q in pcs])
            any_l = np.mean([sum(v[1] for v in typ[s].values()) > 0 for s in ids])
            any_u = np.mean([sum(v[2] for v in typ[s].values()) > 0 for s in ids])
            tag = " (all)" if (lo, hi) == (3, 90) else ""
            L.append(f"| {c} | {lo}-{hi}{tag} | {len(ids)} | {np.mean(z):+.2f} | "
                     f"{np.std(z):.2f} | {100 * hi95:.0f}% | {100 * lo5:.0f}% | "
                     f"{100 * any_l:.0f}% | {100 * any_u:.0f}% |")
    L.append("")

    L.append("## Most common links at age 10 / 40 / 70 (EC, 55 pairs, predicted % of such pairs)\n")
    m = fit(ref["EC"], st, pairs)
    tops = []
    for t, (pos, neg, n) in m["links"].items():
        ps = [100 * link_prev(m, t, 1, a, 55) for a in (10, 40, 70)]
        tops.append((max(ps), t, ps, n))
    L.append("| pair type | pairs | age 10 | age 40 | age 70 |")
    L.append("|---|---:|---:|---:|---:|")
    for _, t, ps, n in sorted(tops, key=lambda v: -v[0])[:12]:
        L.append(f"| {t} | {n} | {ps[0]:.1f}% | {ps[1]:.1f}% | {ps[2]:.1f}% |")
    L.append("")

    L.append("## Against the doctor's comments (rank AUC, 95% bootstrap CI; reference set)\n")
    L.append("> 0.5: higher in positives. High-confidence labels; `pdr_slow` is alpha-anchored.\n")
    L.append("| outcome | condition | pos | Theta | Alpha | Beta | uncommon links |")
    L.append("|---|---|---:|---:|---:|---:|---:|")
    lab = {}
    for sid, o, v, cf in con.execute("SELECT study_id, outcome, value, conf FROM labels"):
        if cf == "high":
            lab.setdefault(o, {})[sid] = v
    for o in ("clinical_abnorm", "drowsiness", "paroxysmal", "pdr_slow"):
        for c in ("EC", "EO"):
            ids = [s for s in ref[c] if s in lab.get(o, {}) and s in typ]
            y = np.array([lab[o][s] for s in ids])
            if y.sum() < 5 or (1 - y).sum() < 5:
                continue
            cells = []
            for b in COUPLE_BANDS:
                k = [i for i, s in enumerate(ids) if b in typ[s] and typ[s][b][4] is not None]
                x = np.array([typ[ids[i]][b][4] for i in k])
                lo, hi = auc_ci(x, y[k], rng)
                cells.append(f"{auc(x, y[k]):.2f} ({lo:.2f}-{hi:.2f})")
            x = np.array([sum(v[2] for v in typ[s].values()) for s in ids], float)
            L.append(f"| {o} | {c} | {int(y.sum())} | " + " | ".join(cells) + f" | {auc(x, y):.2f} |")
    L.append("")
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("wrote", OUT_MD)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=DEFAULT_STORE)
    a = ap.parse_args()
    con = sqlite3.connect(os.path.join(a.store, "sources.db"))
    pairs, st, ref = build(con)
    analyze(con, pairs, st, ref)
    con.close()


if __name__ == "__main__":
    main()
