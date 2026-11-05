"""After the peak change: the slow flag against the doctor. Reads the store. Aggregates only;
old values come from the backup made before the change."""
import collections, os, sqlite3, sys
import numpy as np
from scipy.stats import spearmanr
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from label_join import auc
ST = r"C:\BrainPanel\source_db"


def load(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    z = dict(con.execute("SELECT study_id, z FROM ref_z WHERE feature='paf_post'"))
    hz = dict(con.execute("SELECT study_id, paf_post FROM edf_features"))
    return con, z, hz


con, z_new, hz_new = load(os.path.join(ST, "sources.db"))
_c, z_old, hz_old = load(os.path.join(ST, "sources.db.before-alpha-peak"))
meta = {r[0]: dict(cond=r[1], client=r[2] or r[0], when=r[3], age=r[4]) for r in con.execute(
    "SELECT id, cond, client, rec_start, age FROM studies WHERE status='ok'")}
pdr = {r[0]: r[1] for r in con.execute("SELECT study_id, hz FROM report_pdr WHERE hz IS NOT NULL")}
slow = dict(con.execute("SELECT study_id, value FROM labels WHERE outcome='pdr_slow' AND conf='high'"))
for cond in ("EC", "EO"):
    print("\n==", cond)
    for name, z, hz in (("before", z_old, hz_old), ("after", z_new, hz_new)):
        seen, S = set(), []
        for s in sorted(meta, key=lambda s: meta[s]["when"] or ""):
            if meta[s]["cond"] == cond and s in slow and z.get(s) is not None and meta[s]["client"] not in seen:
                seen.add(meta[s]["client"]); S.append(s)
        y = np.array([slow[s] for s in S], float)
        x = np.array([z[s] for s in S])
        print(f"{name}: n {len(S)} doctor-slow {int(y.sum())} AUC z {auc(-x, y):.2f} AUC Hz {auc(-np.array([hz[s] for s in S]), y):.2f}")
        for t in (-2, -1.5, -1):
            f = x <= t
            print(f"   z <= {t}: flags {int(f.sum())}, doctor-slow caught {int(y[f].sum())}, share of flags that agree {100 * y[f].mean() if f.any() else 0:.0f}%")
        fl = [s for s in meta if meta[s]["cond"] == cond and s in pdr and z.get(s) is not None and z[s] <= -2 and hz.get(s)]
        d = [abs(hz[s] - pdr[s]) for s in fl]
        print(f"   flagged slow with a stated frequency: {len(fl)}, within 1 Hz {sum(v <= 1 for v in d)}, doctor at 9+ Hz {sum(pdr[s] >= 9 for s in fl)}")
        a = np.array([(hz[s], pdr[s]) for s in meta if meta[s]["cond"] == cond and s in pdr and hz.get(s)], float)
        dd = np.abs(a[:, 0] - a[:, 1])
        print(f"   all with stated frequency: n {len(a)} rho {spearmanr(a[:, 0], a[:, 1])[0]:.2f} within 1 Hz {100 * np.mean(dd <= 1):.0f}%, over 2 Hz {100 * np.mean(dd > 2):.0f}%, under 8 Hz {int((a[:, 0] < 8).sum())} (doctor 9+ {int(((a[:, 0] < 8) & (a[:, 1] >= 9)).sum())})")
