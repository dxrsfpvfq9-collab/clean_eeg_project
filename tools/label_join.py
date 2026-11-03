"""Join the Doctor's QA-review labels to the source database and test which
age-adjusted features carry each label.

Matching and labelling reuse research/validation_2026 unchanged:
cascade_label_join_2026.find_report (the review .docx in the EDF's folder or
its parent with the largest identifier-token overlap, overlap >= 1),
dr_report_parser.parse_report and labels.all_labels (the six outcomes of the
2026 discriminant paper). The report path carries names, so only its hash is
stored.

Tables (sources.db): labels (study_id, outcome, value, conf, report, overlap)
and report_pdr (study_id, hz, hz_lo) -- the reader's stated PDR frequency.

Analysis (written to research/validation_2026/out/SOURCE_DB_LABEL_JOIN.md):
rank AUC of every study-level ref_z feature per outcome and condition (one
study per client per condition, high-confidence labels only), and the
reader's PDR Hz against the EDF alpha peak and the cascade's dominant
posterior source.

    py tools/label_join.py [--store DIR] [--analyze-only]
"""
import argparse
import hashlib
import os
import re
import sqlite3
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAL = os.path.join(ROOT, "research", "validation_2026")
sys.path.insert(0, VAL)

DEFAULT_STORE = r"C:\BrainPanel\source_db"
CORPUS = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
OUT_MD = os.path.join(VAL, "out", "SOURCE_DB_LABEL_JOIN.md")
MIN_POS = 15

SCHEMA = """
CREATE TABLE IF NOT EXISTS labels (
  study_id TEXT, outcome TEXT, value INTEGER, conf TEXT, report TEXT, overlap INTEGER,
  PRIMARY KEY (study_id, outcome));
CREATE TABLE IF NOT EXISTS report_pdr (study_id TEXT PRIMARY KEY, hz REAL, hz_lo REAL);
"""


_HZ = re.compile(r"(\d{1,2}(?:\.\d)?)(?:\s*-\s*(\d{1,2}(?:\.\d)?))?\s*hz")
_OTHER_BAND = ("theta", "delta", "beta", "gamma")


def pdr_hz_alpha(background):
    """Reader's PDR frequency, anchored on the ALPHA rhythm: (lower bound, mid)
    of the first 'X[-Y] Hz' that is followed within 30 characters by 'alpha',
    else the first one not followed by another band name. labels.parse_pdr_hz
    takes the first dash range anywhere, which in 42 reports is the '5-7 Hz
    theta range seen in the frontal' sentence -- it read them as PDR 5 Hz."""
    from labels import _lc
    t = _lc(background)
    t = re.sub(r"\s*\.\s*", ".", t)
    t = re.sub(r"(\d)\s+(\d)", r"", t)
    t = re.sub(r"(\d)\s+(\d)", r"", t)
    if "not clearly demonstrated" in t or "no clearly defined" in t or "not demonstrated" in t:
        return None, None
    fallback = None
    for m in _HZ.finditer(t):
        lo = float(m.group(1))
        hi = float(m.group(2)) if m.group(2) else lo
        if not (2 <= lo <= 20 and lo <= hi <= 20):
            continue
        after = t[m.end():m.end() + 30]
        if "alpha" in after:
            return lo, (lo + hi) / 2
        if fallback is None and not any(b in after for b in _OTHER_BAND):
            fallback = (lo, (lo + hi) / 2)
    return fallback or (None, None)


def pdr_slow(rep, age):
    """pdr_freq_abnorm with the alpha-anchored frequency (same floors and the
    same explicit 'PDR slowing for age' override as labels.lab_pdr_freq_abnorm)."""
    import labels as Lb
    c = Lb._lc(rep.get("comments"))
    if ("pdr slowing for" in c or "slowing for stated age" in c or "slowing for his age" in c
            or "slowing for her age" in c) and not ("no pdr slowing" in c
                                                    or "without pdr slowing" in c
                                                    or "no slowing" in c):
        return 1, "high"
    lo, _ = pdr_hz_alpha(rep.get("background"))
    if lo is None:
        return 0, "low"
    return (1 if lo < Lb._pdr_floor(age) else 0), "high"


def build(con):
    import dr_report_parser as P
    import labels as Lb
    from cascade_label_join_2026 import find_report
    con.execute("DELETE FROM labels")
    con.execute("DELETE FROM report_pdr")
    rows = con.execute("SELECT id, rel_path, age FROM studies WHERE status='ok'").fetchall()
    cache, n = {}, 0
    for k, (sid, rel, age) in enumerate(rows, 1):
        path = os.path.join(CORPUS, rel)
        rp, ov = find_report(os.path.dirname(path), os.path.basename(path)[:-4])
        if not rp or ov < 1:
            continue
        if rp not in cache:
            try:
                cache[rp] = P.parse_report(rp)
            except Exception:
                cache[rp] = None
        rep = cache[rp]
        if not rep or not rep.get("valid"):
            continue
        rh = hashlib.sha1(os.path.relpath(rp, CORPUS).lower().encode("utf-8")).hexdigest()[:12]
        labs = Lb.all_labels(rep, age)
        labs["pdr_slow"] = pdr_slow(rep, age)       # alpha-anchored pdr_freq_abnorm
        for outc, (val, conf) in labs.items():
            con.execute("INSERT INTO labels VALUES (?,?,?,?,?,?)", (sid, outc, int(val), conf, rh, ov))
        lo, mid = pdr_hz_alpha(rep.get("background"))
        con.execute("INSERT INTO report_pdr VALUES (?,?,?)", (sid, mid, lo))
        n += 1
        if k % 200 == 0:
            print(f"  {k}/{len(rows)} scanned, {n} labelled", flush=True)
    con.commit()
    print(f"{n} of {len(rows)} studies labelled from {len([v for v in cache.values() if v])} reports")


def auc(x, y):
    """Rank AUC of x for y==1 (ties averaged); 0.5 = no signal."""
    from scipy.stats import rankdata
    r = rankdata(x)
    n1 = int(y.sum())
    n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def auc_ci(x, y, rng, n_boot=500):
    a = [auc(x[i], y[i]) for i in (rng.integers(0, len(y), len(y)) for _ in range(n_boot))
         if 0 < y[i].sum() < len(i)]
    return np.percentile(a, [2.5, 97.5])


def analyze(con):
    from scipy.stats import spearmanr
    rng = np.random.default_rng(0)
    out = []
    w = out.append
    w("# Source database features vs Doctor's-Report labels\n")
    w("Generated by `tools/label_join.py`. Labels from the matched STS QA review "
      "(`dr_report_parser` + `labels.all_labels`); features are age-by-condition "
      "z-scores from `tools/reference_ranges.py` (a screening population, not norms). "
      "One study per client per condition (earliest), high-confidence labels only.\n")

    studies = {r[0]: r[1:] for r in con.execute(
        "SELECT id, client, cond, rec_start FROM studies WHERE status='ok'")}
    first = {}
    for sid, (cl, cond, when) in sorted(studies.items(), key=lambda kv: kv[1][2] or ""):
        if cond in ("EC", "EO"):
            first.setdefault((cl or sid, cond), sid)
    keep = set(first.values())

    lab = {}
    for sid, outc, val, conf in con.execute("SELECT study_id, outcome, value, conf FROM labels"):
        if conf == "high" and sid in keep:
            lab.setdefault(outc, {})[sid] = val
    feats = [r[0] for r in con.execute(
        "SELECT DISTINCT feature FROM ref_models WHERE feature NOT LIKE '%.%' ORDER BY feature")]
    z = {}
    for sid, f, zv in con.execute("SELECT study_id, feature, z FROM ref_z WHERE feature NOT LIKE '%.%'"):
        z.setdefault(f, {})[sid] = zv

    w("## Coverage\n")
    w("| outcome | EC labelled | EC positive | EO labelled | EO positive |")
    w("|---|---:|---:|---:|---:|")
    for outc in sorted(lab):
        cells = []
        for cond in ("EC", "EO"):
            ids = [s for s in lab[outc] if studies[s][1] == cond]
            cells += [len(ids), sum(lab[outc][s] for s in ids)]
        w(f"| {outc} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} |")
    w("")

    w(f"## Rank AUC of each age-adjusted feature (outcomes with >= {MIN_POS} positives)\n")
    w("AUC > 0.5: higher z goes with the label; < 0.5: lower z. Bracket = bootstrap 95% CI. "
      "Top 6 features by |AUC - 0.5| per outcome and condition; * = CI excludes 0.5.\n")
    for outc in sorted(lab):
        for cond in ("EC", "EO"):
            ids = [s for s in lab[outc] if studies[s][1] == cond]
            npos = sum(lab[outc][s] for s in ids)
            if npos < MIN_POS or len(ids) - npos < MIN_POS:
                continue
            res = []
            for f in feats:
                sel = [s for s in ids if s in z.get(f, {}) and np.isfinite(z[f][s])]
                if len(sel) < 2 * MIN_POS:
                    continue
                x = np.array([z[f][s] for s in sel])
                y = np.array([lab[outc][s] for s in sel])
                if not 0 < y.sum() < len(y):
                    continue
                res.append((f, auc(x, y), x, y))
            res.sort(key=lambda t: -abs(t[1] - 0.5))
            w(f"**{outc} — {cond}** (n={len(ids)}, positive {npos}, {100 * npos / len(ids):.0f}%)\n")
            w("| feature | AUC | 95% CI | n |")
            w("|---|---:|---|---:|")
            for f, a, x, y in res[:6]:
                lo, hi = auc_ci(x, y, rng)
                star = "*" if lo > 0.5 or hi < 0.5 else ""
                w(f"| {f} | {a:.2f}{star} | {lo:.2f}-{hi:.2f} | {len(y)} |")
            w("")

    w("## Reader's PDR frequency vs measured alpha peak\n")
    pdr = {r[0]: r[1] for r in con.execute("SELECT study_id, hz FROM report_pdr WHERE hz IS NOT NULL")}
    ef = {r[0]: r[1:] for r in con.execute("SELECT study_id, paf_post FROM edf_features")}
    sf = {r[0]: r[1:] for r in con.execute("SELECT study_id, dom_post_hz FROM study_features")}
    w("Reader's Hz is the midpoint of the stated alpha range (`pdr_hz_alpha`); "
      "measured values are the EDF posterior alpha peak and the cascade's dominant "
      "posterior 8-13 Hz source.\n")
    w("| condition | measure | n | Spearman rho | median abs diff (Hz) | median measured - reader |")
    w("|---|---|---:|---:|---:|---:|")
    for cond in ("EC", "EO"):
        for name, src in (("EDF paf_post", ef), ("cascade dom_post_hz", sf)):
            ids = [s for s in pdr if s in keep and studies[s][1] == cond and s in src
                   and src[s][0] is not None]
            if len(ids) < 20:
                continue
            a = np.array([pdr[s] for s in ids])
            b = np.array([src[s][0] for s in ids])
            rho = spearmanr(a, b)[0]
            w(f"| {cond} | {name} | {len(ids)} | {rho:.2f} | {np.median(np.abs(b - a)):.2f} | "
              f"{np.median(b - a):+.2f} |")
    w("")
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(out))
    print("wrote", OUT_MD)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=DEFAULT_STORE)
    ap.add_argument("--analyze-only", action="store_true")
    a = ap.parse_args()
    con = sqlite3.connect(os.path.join(a.store, "sources.db"), timeout=60)
    con.executescript(SCHEMA)
    if not a.analyze_only:
        build(con)
    analyze(con)


if __name__ == "__main__":
    main()
