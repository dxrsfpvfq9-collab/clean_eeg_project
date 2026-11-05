"""Is the client key one person? And what does the reader say when the alpha-peak flag fires?
Counts only."""
import collections, json, os, sqlite3, sys
from datetime import datetime as D
import numpy as np
ROOT = r"C:\BrainPanel\clean_eeg_project 2025"
sys.path[:0] = [ROOT, os.path.join(ROOT, "tools")]
import edf_report as ER
con = sqlite3.connect(r"C:\BrainPanel\source_db\sources.db")
meta = {r[0]: dict(rel=r[1], folder=r[2], cond=r[3], age=r[4], client=r[5], when=r[6]) for r in con.execute(
    "SELECT id, rel_path, folder, cond, age, client, rec_start FROM studies WHERE status='ok'")}
by = collections.defaultdict(list)
for s, m in meta.items():
    by[m["client"]].append(s)
sizes = sorted((len(v) for v in by.values()), reverse=True)
print("clients", len(by), "studies", len(meta), "null key", len(by.get(None, [])), "largest", sizes[:12])
multi_top = [(len(v), len({meta[s]["folder"] for s in v}), sorted({meta[s]["age"] for s in v if meta[s]["age"] is not None})[:1] + sorted({meta[s]["age"] for s in v if meta[s]["age"] is not None})[-1:])
             for k, v in sorted(by.items(), key=lambda kv: -len(kv[1]))[:12]]
print("top keys: (studies, folders, [age min, max])", multi_top)
sus = {k for k, v in by.items() if k and (lambda a: len(a) >= 2 and max(a) - min(a) > 5)([meta[s]["age"] for s in v if meta[s]["age"] is not None])}
print("keys spanning > 5 years of age", len(sus), "holding studies", sum(len(by[k]) for k in sus))
print("keys spanning > 1 folder", sum(1 for k, v in by.items() if k and len({meta[s]["folder"] for s in v}) > 1), "| studies in them", sum(len(v) for k, v in by.items() if k and len({meta[s]["folder"] for s in v}) > 1))

tiles = [t[0] for t in ER.TILES]
z = collections.defaultdict(dict)
for sid, f, v in con.execute(f"SELECT study_id, feature, z FROM ref_z WHERE feature IN ({','.join('?' * len(tiles))})", tiles):
    z[sid][f] = v
print("\ntest-retest again, keeping pairs in the same folder with the same age")
g = collections.defaultdict(list)
for s, m in meta.items():
    if s in z and m["client"] and m["when"] and m["cond"] in ("EC", "EO") and m["age"]:
        g[(m["client"], m["cond"], m["folder"], m["age"])].append(s)
P2 = []
for v in g.values():
    v = sorted(v, key=lambda s: meta[s]["when"])
    for a, b in zip(v, v[1:]):
        d = (D.fromisoformat(meta[b]["when"]) - D.fromisoformat(meta[a]["when"])).total_seconds() / 86400
        if d >= 120 / 86400 and d <= 90 and not all(z[a].get(f) == z[b].get(f) for f in tiles):
            P2.append((a, b))
print("pairs", len(P2), "clients", len({meta[a]["client"] for a, _ in P2}))
tot_e = tot_b = 0
for f in tiles:
    xy = np.array([(z[a][f], z[b][f]) for a, b in P2 if z[a].get(f) is not None and z[b].get(f) is not None])
    if len(xy) >= 10:
        fg = np.abs(xy) >= 2
        tot_e += int(fg.any(axis=1).sum()); tot_b += int(fg.all(axis=1).sum())
        print(f"  {f}: n {len(xy)} r {np.corrcoef(xy.T)[0, 1]:.2f} median |dz| {np.median(np.abs(xy[:, 0] - xy[:, 1])):.2f}; either {int(fg.any(axis=1).sum())}, both {int(fg.all(axis=1).sum())}")
print("  all six: flagged in either", tot_e, "in both", tot_b)

print("\nalpha-peak flag vs reader's stated Hz, EC")
paf = dict(con.execute("SELECT study_id, paf_post FROM edf_features"))
pdr = {r[0]: r[1] for r in con.execute("SELECT study_id, hz FROM report_pdr")}
rows = [(paf[s], pdr[s], z[s]["paf_post"], meta[s]["age"]) for s in z if meta.get(s) and meta[s]["cond"] == "EC" and pdr.get(s) and paf.get(s) and z[s].get("paf_post") is not None]
a = np.array(rows, float)
print("n", len(a), "| |diff| > 1 Hz:", int((np.abs(a[:, 0] - a[:, 1]) > 1).sum()), "| EDF lower by > 1:", int((a[:, 1] - a[:, 0] > 1).sum()), "| EDF higher by > 1:", int((a[:, 0] - a[:, 1] > 1).sum()))
fl = a[:, 2] <= -2
print("flagged slow", int(fl.sum()), "(EDF Hz, reader Hz):", [(round(x, 1), y) for x, y in sorted(zip(a[fl, 0], a[fl, 1]))])
low = a[:, 0] < 8
print("EDF peak under 8 Hz", int(low.sum()), "| reader within 1 Hz", int((np.abs(a[low, 0] - a[low, 1]) <= 1).sum()), "| reader at 9+ Hz", int((a[low, 1] >= 9).sum()))
hi = a[:, 0] >= 8
print("EDF peak 8+ Hz", int(hi.sum()), "| reader within 1 Hz", int((np.abs(a[hi, 0] - a[hi, 1]) <= 1).sum()))
