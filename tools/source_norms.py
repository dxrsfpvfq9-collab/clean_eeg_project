"""Are a study's brain sources typical for its age and condition?

Each accepted (non-line) ICA component is put in a coarse SOURCE CELL:
lobe of its sLORETA peak (frontal / temporal / parietal / occipital /
cingulate-deep = limbic + sub-lobar) x side (x < 0 left) x band of its FFT
peak (delta / theta / alpha / fast = beta + gamma) -- 40 cells. A study's cell
share is the % of recording variance in that cell.

PEERS of a study are the 80 clients nearest in log(age) with the same
condition, one study per client (the earliest; the study's own client is
excluded). Against them each cell gets
    prev    -- % of peers with any source in the cell (>= 0.5%)
    pctile  -- the study's share ranked among the peers' shares
and a flag:
    strong  -- share >= 2% and above EVERY peer
    rare    -- share >= 2% in a cell that fewer than 5% of peers have
    absent  -- share < 0.5% in a cell that >= 90% of peers have
Per-cell flags are for the page; with 40 cells a looser line (95th
percentile) flagged 82% of studies by chance. The study verdict is ONE score:
    atyp = sum over cells of w * -log(tail), tail = (peers at least as
           extreme + 1) / (n + 1) -- upward for a present cell, "also absent"
           for an absent one; w = the study's share (present) or the peers'
           median share (absent), so the cells holding the recording count
ranked against the same score of each peer computed against the other peers
(leave-one-out) -> atyp_pctile. >= 95 = unusual source make-up for age.

Tables: source_typ (study_id, cell, pct, prev, pctile, flag) and source_atyp.
The label analysis (AUC vs the Doctor's-Report outcomes, cell by cell and for
the study-level scores) goes to research/validation_2026/out/SOURCE_TYPICALITY.md.

A SCREENING POPULATION, NOT NORMS: "unusual" means unusual among referred
clients of that age.

    py tools/source_norms.py [--store DIR]
"""
import argparse
import os
import sqlite3
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

DEFAULT_STORE = r"C:\BrainPanel\source_db"
OUT_MD = os.path.join(ROOT, "research", "validation_2026", "out", "SOURCE_TYPICALITY.md")
N_PEERS = 80
PRESENT = 0.5        # % share that counts as "has a source in the cell"
MIN_FLAG = 2.0       # % share below which nothing is called strong/rare
RARE_PREV = 5
UNCOMMON_PREV = 25   # page wording only: 5-25% of peers have such a source
ABSENT_PREV = 90
AGE_MIN, AGE_MAX = 3, 90

LOBES = {"Frontal": "frontal", "Temporal": "temporal", "Parietal": "parietal",
         "Occipital": "occipital", "Limbic": "cingulate/deep", "Sub-lobar": "cingulate/deep"}
BANDS = {"Delta": "delta", "Theta": "theta", "Alpha": "alpha", "Beta": "fast", "Gamma": "fast"}
CELLS = [f"{s} {l} {b}" for l in dict.fromkeys(LOBES.values()) for s in ("L", "R")
         for b in dict.fromkeys(BANDS.values())]

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_typ (
  study_id TEXT, cell TEXT, pct REAL, prev REAL, pctile REAL, flag TEXT,
  PRIMARY KEY (study_id, cell));
CREATE TABLE IF NOT EXISTS source_atyp (
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


def atyp_score(v, peers):
    """Share-weighted surprise: each cell's -log(tail) weighted by the % of the
    recording it concerns -- the study's share for a present cell, the peers'
    median share for an absent one. Unweighted, 40 small cells drowned out two
    sources holding 58% of a recording that were stronger than every peer."""
    m = len(peers)
    pres = v >= PRESENT
    up = ((peers >= v).sum(axis=0) + 1) / (m + 1)
    ab = ((peers < PRESENT).sum(axis=0) + 1) / (m + 1)
    w = np.where(pres, v, np.median(peers, axis=0)) / 100
    return float((w * -np.log(np.where(pres, up, ab))).sum())


def score(v, peers):
    """Per cell (prev, pctile, flag) for share vector v against peer matrix."""
    prev = 100 * (peers >= PRESENT).mean(axis=0)
    below = (peers < v).mean(axis=0)
    tie = (peers == v).mean(axis=0)
    pctile = 100 * (below + 0.5 * tie)
    q = peers.max(axis=0)
    flags = []
    for k in range(len(CELLS)):
        if v[k] >= MIN_FLAG and prev[k] < RARE_PREV:
            flags.append("rare")
        elif v[k] >= MIN_FLAG and v[k] > q[k]:
            flags.append("strong")
        elif v[k] < PRESENT and prev[k] >= ABSENT_PREV:
            flags.append("absent")
        else:
            flags.append("")
    return prev, pctile, flags


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


def peers_of(st, cells, ref, age, cond, client):
    pool = [p for p in ref[cond] if st[p]["client"] != client]
    la = np.log([st[p]["age"] for p in pool])
    near = np.argsort(np.abs(la - np.log(age)))[:N_PEERS]
    return np.array([cells[pool[i]] for i in near])


def atyp_pctile(v, peers):
    a0 = atyp_score(v, peers)
    sc = np.array([atyp_score(peers[i], np.delete(peers, i, axis=0)) for i in range(len(peers))])
    return a0, float(100 * (np.sum(sc < a0) + 0.5 * np.sum(sc == a0)) / len(sc))


def typicality(comps, age, cond, store=DEFAULT_STORE, client=None):
    """Typicality of one study's sources from source_summary.load()['comps'],
    for the source page. None when age/condition are unknown."""
    if age is None or cond not in ("EC", "EO") or not AGE_MIN <= age <= AGE_MAX:
        return None
    con = sqlite3.connect(os.path.join(store, "sources.db"))
    st, cells, ref = reference(con)
    con.close()
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
    peers = peers_of(st, cells, ref, age, cond, client)
    prev, pctile, flags = score(v, peers)
    _, ap = atyp_pctile(v, peers)
    per = {}
    for rank, k in cell_k.items():
        if flags[k] == "rare":
            per[rank] = (f"rare ({prev[k]:.0f}%)", "#c62828")
        elif flags[k] == "strong":
            per[rank] = ("above all peers", "#c62828")
        elif prev[k] < UNCOMMON_PREV:
            per[rank] = (f"uncommon ({prev[k]:.0f}%)", "#b26a00")
        else:
            per[rank] = (f"typical ({prev[k]:.0f}%)", "#2e7d32")
    absent = [(CELLS[k], prev[k]) for k in range(len(CELLS)) if flags[k] == "absent"]
    return dict(per_rank=per, atyp_pctile=ap, absent=absent, n_peers=len(peers), cond=cond,
                age=age)


def band_name(hz):
    for name, lo, hi in (("Delta", 0, 4), ("Theta", 4, 8), ("Alpha", 8, 13), ("Beta", 13, 30)):
        if lo <= hz < hi:
            return name
    return "Gamma"


def build(con):
    con.executescript(SCHEMA)
    con.execute("DELETE FROM source_typ")
    con.execute("DELETE FROM source_atyp")
    st, cells, ref = reference(con)
    n = 0
    for sid, s in st.items():
        if sid not in cells or s["cond"] not in ref or not s["age"] or not AGE_MIN <= s["age"] <= AGE_MAX:
            continue
        peers = peers_of(st, cells, ref, s["age"], s["cond"], s["client"])
        v = cells[sid]
        prev, pctile, flags = score(v, peers)
        con.executemany("INSERT INTO source_typ VALUES (?,?,?,?,?,?)", [
            (sid, CELLS[k], float(v[k]), float(prev[k]), float(pctile[k]), flags[k])
            for k in range(len(CELLS)) if v[k] > 0 or flags[k]])
        a0, a_pct = atyp_pctile(v, peers)
        un = [k for k in range(len(CELLS)) if flags[k] in ("strong", "rare")]
        ab = [k for k in range(len(CELLS)) if flags[k] == "absent"]
        con.execute("INSERT INTO source_atyp VALUES (?,?,?,?,?,?,?,?)", (
            sid, float(sum(v[k] for k in un)), len(un), len(ab),
            "; ".join(f"{CELLS[k]} ({flags[k]})" for k in un), "; ".join(CELLS[k] for k in ab),
            a0, float(a_pct)))
        n += 1
    con.commit()
    print(f"scored {n} studies against {N_PEERS} age peers (EC ref {len(ref['EC'])}, "
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
    for sid, cell, pctile, flag in con.execute("SELECT study_id, cell, pctile, flag FROM source_typ"):
        typ.setdefault(sid, {})[cell] = (pctile, flag)

    L = ["# Are the brain sources typical, and does unusual go with the doctor's comments?\n",
         "Generated by `tools/source_norms.py`. Each accepted ICA component -> a source cell "
         "(lobe x side x band, 40 cells); each study compared with its 80 nearest-age peers "
         "of the same condition (one study per client, own client excluded). "
         "Flags: **strong** = share >= 2% above the peers' 95th percentile; **rare** = >= 2% in a "
         "cell < 10% of peers have; **absent** = < 0.5% in a cell >= 75% of peers have. "
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
    L.append("Per cell, AUC of the study's age-peer percentile for that cell (> 0.5: more of that "
             "source than peers in positives). Top 5 per outcome/condition by |AUC - 0.5|; "
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
