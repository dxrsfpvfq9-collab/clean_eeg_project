"""Alpha-peak thresholds, reader agreement, test-retest, doctor's artifact wording. Aggregates only."""
import collections, glob, json, os, re, sqlite3, sys
from datetime import datetime as D
import numpy as np
ROOT = r"C:\BrainPanel\clean_eeg_project 2025"
sys.path[:0] = [ROOT, os.path.join(ROOT, "research", "validation_2026"), os.path.join(ROOT, "tools")]
import dr_report_parser as P
from cascade_label_join_2026 import find_report
from label_join import auc
import edf_report as ER
from scipy.stats import spearmanr
STORE = r"C:\BrainPanel\source_db"
C = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
OUT = os.path.join(STORE, "pdf", "recent100")
order = json.load(open(os.path.join(OUT, "order.json")))["order"]
con = sqlite3.connect(os.path.join(STORE, "sources.db"))
meta = {r[0]: dict(rel=r[1], cond=r[2], age=r[3], client=r[4], when=r[5]) for r in con.execute(
    "SELECT id, rel_path, cond, age, client, rec_start FROM studies")}
R = {s: json.load(open(os.path.join(OUT, "refit", s + ".json"))) for s in order}
pdr = {r[0]: r[1] for r in con.execute("SELECT study_id, hz FROM report_pdr")}
tiles = [t[0] for t in ER.TILES]
z = collections.defaultdict(dict)
for sid, f, v in con.execute(f"SELECT study_id, feature, z FROM ref_z WHERE feature IN ({','.join('?' * len(tiles))})", tiles):
    z[sid][f] = v
paf = dict(con.execute("SELECT study_id, paf_post FROM edf_features"))
lab = collections.defaultdict(dict)
for s, o, v in con.execute("SELECT study_id, outcome, value FROM labels WHERE conf='high'"):
    lab[s][o] = v

print("== newest 100: report alpha peak vs reader, EC")
rows = [(R[s]["tiles"]["paf_post"]["value"], pdr[s]) for s in order if s in pdr and pdr[s] and meta[s]["cond"] == "EC" and R[s].get("tiles", {}).get("paf_post")]
a = np.array(rows)
print("n", len(a), "rho", round(spearmanr(a[:, 0], a[:, 1])[0], 2), "median |diff|", round(np.median(np.abs(a[:, 0] - a[:, 1])), 2),
      "over 1 Hz", [(round(x, 1), y) for x, y in rows if abs(x - y) > 1])

print("\n== all labelled EC, one study per client: alpha-peak z thresholds vs reader-slow")
seen, S = set(), []
for s in sorted(z, key=lambda s: meta[s]["when"] or ""):
    k = meta[s]["client"] or s
    if meta[s]["cond"] == "EC" and "pdr_slow" in lab[s] and z[s].get("paf_post") is not None and k not in seen:
        seen.add(k); S.append(s)
y = np.array([lab[s]["pdr_slow"] for s in S], float)
x = np.array([z[s]["paf_post"] for s in S])
h = np.array([paf[s] for s in S], float)
print("n", len(y), "reader slow", int(y.sum()), "| AUC z", round(auc(-x, y), 2), "| AUC raw Hz", round(auc(-h, y), 2))
print("reader-slow z quartiles", np.percentile(x[y == 1], [25, 50, 75]).round(2), "| others", np.percentile(x[y == 0], [25, 50, 75]).round(2))
print("reader-slow Hz quartiles", np.percentile(h[y == 1], [25, 50, 75]).round(1), "| others", np.percentile(h[y == 0], [25, 50, 75]).round(1))
for t in (-2, -1.5, -1, -0.5):
    f = x <= t
    print(f"  z <= {t}: flags {int(f.sum())} ({100 * f.mean():.0f}%), reader-slow caught {int(y[f].sum())}/{int(y.sum())}, positive predictive {100 * y[f].mean():.0f}%")
ages = np.array([meta[s]["age"] for s in S], float)
fl = x <= -2
print("flagged at z<=-2: Hz", np.sort(h[fl]).round(1).tolist(), "ages", ages[fl][np.argsort(h[fl])].astype(int).tolist(), "reader", y[fl][np.argsort(h[fl])].astype(int).tolist())
miss = (y == 1) & ~fl
print("reader-slow, not flagged: Hz", np.sort(h[miss]).round(1).tolist(), "ages", ages[miss][np.argsort(h[miss])].astype(int).tolist(), "z", x[miss][np.argsort(h[miss])].round(1).tolist())

print("\n== test-retest: same client and condition, different recording, stored z")
by = collections.defaultdict(list)
for s in z:
    if meta[s]["client"] and meta[s]["when"] and meta[s]["cond"] in ("EC", "EO") and meta[s]["age"]:
        by[(meta[s]["client"], meta[s]["cond"])].append(s)
pairs = {"same day": [], "2-90 days": [], "over 90 days": []}
for k, v in by.items():
    v = sorted(v, key=lambda s: meta[s]["when"])
    for a_, b_ in zip(v, v[1:]):
        d = (D.fromisoformat(meta[b_]["when"]) - D.fromisoformat(meta[a_]["when"])).total_seconds() / 86400
        if d < 120 / 86400 or all(z[a_].get(f) == z[b_].get(f) for f in tiles):
            continue      # the same recording filed twice, or too close to be a separate one
        pairs["same day" if d <= 1 else "2-90 days" if d <= 90 else "over 90 days"].append((a_, b_))
for name, P2 in pairs.items():
    print(name, "pairs", len(P2), "clients", len({meta[a_]["client"] for a_, _ in P2}))
    if len(P2) < 10:
        continue
    for f in tiles:
        xy = np.array([(z[a_][f], z[b_][f]) for a_, b_ in P2 if z[a_].get(f) is not None and z[b_].get(f) is not None])
        if len(xy) < 10:
            continue
        fg = np.abs(xy) >= 2
        print(f"  {f}: n {len(xy)} r {np.corrcoef(xy.T)[0, 1]:.2f} median |dz| {np.median(np.abs(xy[:, 0] - xy[:, 1])):.2f}; flagged in either {int(fg.any(axis=1).sum())}, in both {int(fg.all(axis=1).sum())}")

print("\n== doctor's artifact wording vs report grade, newest 100")
by_name = {}
for p in glob.glob(os.path.join(C, "**", "*.edf"), recursive=True):
    by_name.setdefault(os.path.basename(p).lower(), []).append(p)
tab = collections.Counter()
for s in order:
    if R[s].get("grade") is None:
        continue
    p = os.path.join(C, meta[s]["rel"])
    if not os.path.exists(p):
        h_ = by_name.get(os.path.basename(meta[s]["rel"]).lower(), [])
        if len(h_) != 1:
            continue
        p = h_[0]
    try:
        rp, _ = find_report(os.path.dirname(p), os.path.basename(p)[:-4])
        par = P._gather_paragraphs(rp)
    except Exception:
        continue
    af = (P._value_after_header(par, P._FIELD_HEADERS["artifact_free"]) or "").lower()
    ar = (P._value_after_header(par, P._FIELD_HEADERS["artifact"]) or "").lower()
    heavy = bool(re.search(r"inadequate|significant|severe|marked|excessive|limited|moderate", af + " " + ar))
    elec = "electrode" in ar
    q = R[s].get("quality", "")
    tab[("doctor: heavy artifact words", heavy, "report", R[s]["grade"])] += 1
    tab[("doctor: electrode artifact", elec, "report line-noise problem", "electrode contact" in q)] += 1
    tab[("doctor: heavy artifact words", heavy, "report muscle problem", "muscle" in q)] += 1
for k, v in sorted(tab.items(), key=str):
    print(k, v)
