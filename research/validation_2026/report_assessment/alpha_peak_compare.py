"""Score alpha_peak_candidates.py's measures: against the doctor's stated frequency (a half of
the clients to choose on, the other half to report), and against repeats, which do not depend on
the doctor. One study per client for the reader comparison. Aggregates only."""
import collections, json, os, sqlite3, sys
from datetime import datetime as D
import numpy as np
from scipy.stats import spearmanr
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from label_join import auc
STORE = r"C:\BrainPanel\source_db"
con = sqlite3.connect(os.path.join(STORE, "sources.db"))
V = {k: v for k, v in json.load(open(os.path.join(STORE, "alpha_candidates.json"))).items() if v}
meta = {r[0]: dict(cond=r[1], age=r[2], client=r[3] or r[0], when=r[4], folder=r[5]) for r in con.execute(
    "SELECT id, cond, age, client, rec_start, folder FROM studies WHERE status='ok'")}
pdr = {r[0]: r[1] for r in con.execute("SELECT study_id, hz FROM report_pdr WHERE hz IS NOT NULL")}
slow = dict(con.execute("SELECT study_id, value FROM labels WHERE outcome='pdr_slow' AND conf='high'"))
NAMES = ["cur", "median", "pooled", "detrend", "epoch", "top"]
print("studies with values", len(V), "| reader Hz", sum(s in pdr for s in V))
rng = np.random.default_rng(0)
clients = sorted({m["client"] for m in meta.values()})
half = dict(zip(clients, rng.permutation(len(clients)) % 2))


def table(S, title):
    print(title, "n", len(S))
    print(f"  {'measure':8} {'no peak':>7} {'rho':>5} {'med|d|':>7} {'<=1Hz':>6} {'>2Hz':>5} {'<8 Hz: n, reader <=1Hz, reader 9+':>34}")
    for n in NAMES:
        P = [(V[s][n], pdr[s]) for s in S if V[s].get(n) is not None]
        a = np.array(P, float)
        d = np.abs(a[:, 0] - a[:, 1])
        lo = a[:, 0] < 8
        print(f"  {n:8} {100 * (1 - len(P) / len(S)):6.0f}% {spearmanr(a[:, 0], a[:, 1])[0]:5.2f} {np.median(d):7.2f} {100 * np.mean(d <= 1):5.0f}% {100 * np.mean(d > 2):4.0f}%"
              f" {int(lo.sum()):>12} {int((d[lo] <= 1).sum()):>8} {int((a[lo, 1] >= 9).sum()):>8}")


for cond in ("EC", "EO"):
    seen, S = set(), []
    for s in sorted(V, key=lambda s: meta[s]["when"] or "" if s in meta else ""):
        if s in meta and s in pdr and meta[s]["cond"] == cond and meta[s]["client"] not in seen:
            seen.add(meta[s]["client"]); S.append(s)
    table([s for s in S if half[meta[s]["client"]] == 0], f"\n{cond} choosing half")
    table([s for s in S if half[meta[s]["client"]] == 1], f"{cond} reporting half")
    T = [s for s in S if s in slow]
    y = np.array([slow[s] for s in T], float)
    for n in NAMES:
        k = [V[s].get(n) is not None for s in T]
        x = np.array([V[s][n] for s, q in zip(T, k) if q], float)
        print(f"  doctor-slow AUC {n:8} {auc(-x, y[np.array(k)]):.2f}  (positives {int(y[np.array(k)].sum())})")

print("\nrepeats: same client, condition, folder, age, 2 min - 90 days apart")
g = collections.defaultdict(list)
for s, m in meta.items():
    if s in V and m["when"] and m["cond"] in ("EC", "EO") and m["age"]:
        g[(m["client"], m["cond"], m["folder"], m["age"])].append(s)
P2 = []
for v in g.values():
    v = sorted(v, key=lambda s: meta[s]["when"])
    for a, b in zip(v, v[1:]):
        d = (D.fromisoformat(meta[b]["when"]) - D.fromisoformat(meta[a]["when"])).total_seconds() / 86400
        if 120 / 86400 <= d <= 90 and V[a]["cur"] != V[b]["cur"]:
            P2.append((a, b))
for n in NAMES:
    xy = np.array([(V[a][n], V[b][n]) for a, b in P2 if V[a].get(n) is not None and V[b].get(n) is not None], float)
    print(f"  {n:8} n {len(xy)} r {np.corrcoef(xy.T)[0, 1]:.2f} median |d| {np.median(np.abs(xy[:, 0] - xy[:, 1])):.2f} Hz")

print("\nsame session, eyes closed vs open")
ses = collections.defaultdict(dict)
for s, m in meta.items():
    if s in V and m["when"]:
        ses[(m["client"], m["when"][:10])][m["cond"]] = s
pairs = [(v["EC"], v["EO"]) for v in ses.values() if "EC" in v and "EO" in v]
for n in NAMES:
    xy = np.array([(V[a][n], V[b][n]) for a, b in pairs if V[a].get(n) is not None and V[b].get(n) is not None], float)
    print(f"  {n:8} n {len(xy)} r {np.corrcoef(xy.T)[0, 1]:.2f}")

print("\nwhy the current measure goes low: EC, cur < 8, reader 9+")
bad = [s for s in V if s in pdr and meta.get(s) and meta[s]["cond"] == "EC" and V[s]["cur"] and V[s]["cur"] < 8 and pdr[s] >= 9]
print(" n", len(bad), "site spread Hz median", np.median([V[s]["spread"] for s in bad]).round(2), "vs all EC", np.median([V[s]["spread"] for s in V if meta.get(s) and meta[s]["cond"] == "EC" and V[s]["spread"] is not None]).round(2))
for n in NAMES[1:]:
    w = [V[s][n] for s in bad if V[s].get(n) is not None]
    print(f"  {n:8} got {len(w)}, median {np.median(w):.1f} Hz, within 1 Hz of reader {sum(abs(V[s][n] - pdr[s]) <= 1 for s in bad if V[s].get(n) is not None)}")
h = [V[s]["detrend_h"] for s in V if V[s].get("detrend_h")]
print("detrend height percentiles", np.percentile(h, [5, 25, 50, 75, 95]).round(2))
for t in (1.1, 1.25, 1.5, 2.0):
    S = [s for s in V if s in pdr and meta.get(s) and meta[s]["cond"] == "EC" and V[s].get("detrend_h")]
    a = np.array([(V[s]["detrend"], pdr[s], V[s]["detrend_h"]) for s in S], float)
    k = a[:, 2] >= t
    print(f"  height >= {t}: keeps {100 * k.mean():.0f}% EC, <=1 Hz of reader {100 * np.mean(np.abs(a[k, 0] - a[k, 1]) <= 1):.0f}%; dropped ones {100 * np.mean(np.abs(a[~k, 0] - a[~k, 1]) <= 1) if (~k).any() else 0:.0f}%")
