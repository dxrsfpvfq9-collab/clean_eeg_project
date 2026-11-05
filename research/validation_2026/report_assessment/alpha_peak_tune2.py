"""Second pass on the cached spectra: a width test that only removes single-bin spikes. Aggregates only."""
import collections, json, os, sqlite3, sys
from datetime import datetime as D
import numpy as np
from scipy.stats import spearmanr
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import edf_power
from label_join import auc
ST = r"C:\BrainPanel\source_db"
con = sqlite3.connect(os.path.join(ST, "sources.db"))
meta = {r[0]: dict(cond=r[1], age=r[2], client=r[3] or r[0], when=r[4], folder=r[5]) for r in con.execute(
    "SELECT id, cond, age, client, rec_start, folder FROM studies WHERE status='ok'")}
z = np.load(os.path.join(ST, "alpha_spectra.npz"))
S = dict(zip(z["ids"].tolist(), z["P"]))
f = np.arange(z["P"].shape[1]) * 0.25
pdr = {r[0]: r[1] for r in con.execute("SELECT study_id, hz FROM report_pdr WHERE hz IS NOT NULL")}
slow = dict(con.execute("SELECT study_id, value FROM labels WHERE outcome='pdr_slow' AND conf='high'"))
V = {k: v for k, v in json.load(open(os.path.join(ST, "alpha_candidates.json"))).items() if v}
rng = np.random.default_rng(0)
clients = sorted({m["client"] for m in meta.values()})
half = dict(zip(clients, rng.permutation(len(clients)) % 2))
RULES = [(1.5, 0.0), (1.5, 0.25), (2.0, 0.0), (2.0, 0.25)]


def ev(T, get):
    vals = {s: get(s) for s in T}
    a = np.array([(vals[s], pdr[s]) for s in T if vals[s] is not None], float)
    d = np.abs(a[:, 0] - a[:, 1])
    lo = a[:, 0] < 8
    none = [s for s in T if vals[s] is None]
    Y = [s for s in T if s in slow and vals[s] is not None]
    A = auc(-np.array([vals[s] for s in Y]), np.array([slow[s] for s in Y], float))
    return (f"no peak {100 * len(none) / len(T):3.0f}%  rho {spearmanr(a[:, 0], a[:, 1])[0]:.2f}  <=1Hz {100 * np.mean(d <= 1):3.0f}%  >2Hz {100 * np.mean(d > 2):3.0f}%"
            f"  <8Hz {int(lo.sum()):3d} (reader 9+ {int((a[lo, 1] >= 9).sum()):2d})  slow AUC {A:.2f} (+{int(sum(slow[s] for s in Y))})")


for cond in ("EC", "EO"):
    seen, G = set(), []
    for s in sorted(S, key=lambda s: meta[s]["when"] or ""):
        if s in pdr and s in V and meta[s]["cond"] == cond and meta[s]["client"] not in seen:
            seen.add(meta[s]["client"]); G.append(s)
    for name, T in (("choosing", [s for s in G if half[meta[s]["client"]] == 0]), ("reporting", [s for s in G if half[meta[s]["client"]] == 1])):
        print(f"\n{cond} {name} n {len(T)}")
        print("  current     ", ev(T, lambda s: V[s]["cur"]))
        for h, w in RULES:
            print(f"  h {h} w {w:<4}", ev(T, lambda s: edf_power.posterior_peak(f, S[s], min_height=h, min_width=w)))

print("\nsingle-bin spikes (h 2.0): width 0 vs 0.25")
n = collections.Counter()
cl = set()
for s in S:
    a0 = edf_power.posterior_peak(f, S[s], 2.0, 0)
    a1 = edf_power.posterior_peak(f, S[s], 2.0, 0.25)
    if a0 != a1:
        n["changed"] += 1; cl.add(meta[s]["client"])
        if s in pdr:
            n["with reader"] += 1
            n["nearer after"] += a1 is not None and abs(a1 - pdr[s]) < abs(a0 - pdr[s])
            n["nearer before"] += a1 is not None and abs(a1 - pdr[s]) > abs(a0 - pdr[s])
            n["no peak after"] += a1 is None
print(dict(n), "clients", len(cl))

g = collections.defaultdict(list)
for s in S:
    m = meta[s]
    if m["when"] and m["cond"] in ("EC", "EO") and m["age"]:
        g[(m["client"], m["cond"], m["folder"], m["age"])].append(s)
prs = []
for v in g.values():
    v = sorted(v, key=lambda s: meta[s]["when"])
    for a, b in zip(v, v[1:]):
        dd = (D.fromisoformat(meta[b]["when"]) - D.fromisoformat(meta[a]["when"])).total_seconds() / 86400
        if 120 / 86400 <= dd <= 90 and not np.array_equal(S[a], S[b]):
            prs.append((a, b))
print("\nrepeats", len(prs))
xy = np.array([(V[a]["cur"], V[b]["cur"]) for a, b in prs if a in V and b in V and V[a]["cur"] and V[b]["cur"]], float)
print(f"  current: n {len(xy)} r {np.corrcoef(xy.T)[0, 1]:.2f} median |d| {np.median(np.abs(xy[:, 0] - xy[:, 1])):.2f}")
for h, w in RULES:
    fn = lambda s: edf_power.posterior_peak(f, S[s], h, w)
    xy = np.array([(fn(a), fn(b)) for a, b in prs if fn(a) is not None and fn(b) is not None], float)
    print(f"  h {h} w {w}: n {len(xy)} r {np.corrcoef(xy.T)[0, 1]:.2f} median |d| {np.median(np.abs(xy[:, 0] - xy[:, 1])):.2f}")
print("\nno-peak rate over all studies")
for cond in ("EC", "EO"):
    T = [s for s in S if meta[s]["cond"] == cond]
    print(cond, "current", round(100 * np.mean([not (s in V and V[s]["cur"]) for s in T])), {f"h{h} w{w}": round(100 * np.mean([edf_power.posterior_peak(f, S[s], h, w) is None for s in T])) for h, w in RULES})
