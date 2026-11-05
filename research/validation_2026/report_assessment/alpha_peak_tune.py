"""Tune the posterior alpha-peak rule on half the clients, report on the other half.
First run caches each study's mean posterior spectrum in <store>/alpha_spectra.npz (no names).

Rule under test (edf_power.posterior_peak): remove the 1/f slope, take local maxima in 7-13 Hz,
ignore any narrower than MIN_WIDTH at half height (not brain: exact-bin spikes), keep the tallest
if it stands at least MIN_HEIGHT over the slope line.
"""
import collections, json, multiprocessing as mp, os, sqlite3, sys
from datetime import datetime as D
import numpy as np
from scipy.signal import welch
from scipy.stats import spearmanr
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import edf_power
from label_join import auc
ST = r"C:\BrainPanel\source_db"
C = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
CACHE = os.path.join(ST, "alpha_spectra.npz")
POST = ("O1", "O2", "P3", "P4", "PZ")


def spec(job):
    sid, path = job
    try:
        from epoch_reject_report import read_edf
        sigs, labels, fs = read_edf(path, 64)
        P, seen = [], set()
        for x, lab in zip(sigs, labels):
            n = edf_power.site_of(lab)
            if n in POST and n not in seen and x.std() >= 0.01:
                seen.add(n)
                f, p = welch(x - x.mean(), fs=fs, nperseg=int(4 * fs), average="median")
                P.append(p)
        if not P:
            return sid, None
        m = f <= 45
        return sid, np.mean(P, axis=0)[m]
    except Exception:
        return sid, None


def main():
    con = sqlite3.connect(os.path.join(ST, "sources.db"))
    meta = {r[0]: dict(cond=r[1], age=r[2], client=r[3] or r[0], when=r[4], folder=r[5], rel=r[6]) for r in con.execute(
        "SELECT id, cond, age, client, rec_start, folder, rel_path FROM studies WHERE status='ok'")}
    if not os.path.exists(CACHE):
        jobs = [(s, os.path.join(C, m["rel"])) for s, m in meta.items() if os.path.exists(os.path.join(C, m["rel"]))]
        with mp.Pool(12) as pool:
            res = [r for r in pool.imap_unordered(spec, jobs) if r[1] is not None]
        res = [r for r in res if len(r[1]) == 181]
        np.savez_compressed(CACHE, ids=np.array([r[0] for r in res]), P=np.array([r[1] for r in res]))
    z = np.load(CACHE)
    ids, P = z["ids"].tolist(), z["P"]
    f = np.arange(P.shape[1]) * 0.25
    S = dict(zip(ids, P))
    print("spectra", len(ids))
    pdr = {r[0]: r[1] for r in con.execute("SELECT study_id, hz FROM report_pdr WHERE hz IS NOT NULL")}
    slow = dict(con.execute("SELECT study_id, value FROM labels WHERE outcome='pdr_slow' AND conf='high'"))
    V = {k: v for k, v in json.load(open(os.path.join(ST, "alpha_candidates.json"))).items() if v}
    rng = np.random.default_rng(0)
    clients = sorted({m["client"] for m in meta.values()})
    half = dict(zip(clients, rng.permutation(len(clients)) % 2))

    def groups(cond):
        seen, out = set(), []
        for s in sorted(S, key=lambda s: meta[s]["when"] or ""):
            if s in pdr and meta[s]["cond"] == cond and meta[s]["client"] not in seen:
                seen.add(meta[s]["client"]); out.append(s)
        return out

    def row(T, fn):
        vals = {s: fn(S[s]) for s in T}
        a = np.array([(vals[s], pdr[s]) for s in T if vals[s] is not None], float)
        d = np.abs(a[:, 0] - a[:, 1])
        lo = a[:, 0] < 8
        none = [s for s in T if vals[s] is None]
        nd = 100 * np.mean([abs(V[s]["cur"] - pdr[s]) <= 1 for s in none if s in V and V[s]["cur"]]) if none else 0
        Y = [s for s in T if s in slow and vals[s] is not None]
        A = auc(-np.array([vals[s] for s in Y]), np.array([slow[s] for s in Y], float))
        return (f"nopeak {100 * len(none) / len(T):4.0f}%  rho {spearmanr(a[:, 0], a[:, 1])[0]:.2f}  <=1Hz {100 * np.mean(d <= 1):3.0f}%  >2Hz {100 * np.mean(d > 2):3.0f}%"
                f"  <8Hz: {int(lo.sum()):3d} (reader 9+ {int((a[lo, 1] >= 9).sum()):2d})  slowAUC {A:.2f}")

    def rule(h, w):
        return lambda p: edf_power.posterior_peak(f, p, min_height=h, min_width=w)

    for cond in ("EC", "EO"):
        G = groups(cond)
        pick = [s for s in G if half[meta[s]["client"]] == 0]
        rep = [s for s in G if half[meta[s]["client"]] == 1]
        print(f"\n{cond}: choosing half n {len(pick)}")
        print(f"  {'current':14}", "cur:", end=" ")
        cur = lambda T: np.array([(V[s]["cur"], pdr[s]) for s in T if s in V and V[s]["cur"]], float)
        a = cur(pick); d = np.abs(a[:, 0] - a[:, 1]); print(f"<=1Hz {100 * np.mean(d <= 1):.0f}%  >2Hz {100 * np.mean(d > 2):.0f}%  <8Hz {int((a[:, 0] < 8).sum())} (reader 9+ {int(((a[:, 0] < 8) & (a[:, 1] >= 9)).sum())})")
        for h in (1.25, 1.5, 2.0, 3.0):
            for w in (0, 0.75, 1.0):
                print(f"  h {h:<4} w {w:<4}", row(pick, rule(h, w)))
        print(f"{cond}: reporting half n {len(rep)}")
        a = cur(rep); d = np.abs(a[:, 0] - a[:, 1]); print(f"  current: <=1Hz {100 * np.mean(d <= 1):.0f}%  >2Hz {100 * np.mean(d > 2):.0f}%  <8Hz {int((a[:, 0] < 8).sum())} (reader 9+ {int(((a[:, 0] < 8) & (a[:, 1] >= 9)).sum())})")
        for h, w in ((1.5, 0.75), (2.0, 0.75), (2.0, 1.0), (3.0, 0.75)):
            print(f"  h {h:<4} w {w:<4}", row(rep, rule(h, w)))

    print("\nstudies whose whole-spectrum maximum in the window is a spike narrower than 0.75 Hz")
    n = collections.Counter()
    for s in S:
        a0 = edf_power.posterior_peak(f, S[s], min_height=2.0, min_width=0)
        a1 = edf_power.posterior_peak(f, S[s], min_height=2.0, min_width=0.75)
        if a0 != a1:
            n["changed"] += 1
            n[meta[s]["cond"]] += 1
            if s in pdr:
                n["with reader"] += 1
                n["reader nearer after"] += (a1 is not None and abs(a1 - pdr[s]) < abs(a0 - pdr[s]))
                n["reader nearer before"] += (a1 is not None and abs(a1 - pdr[s]) > abs(a0 - pdr[s]))
                n["no peak after"] += a1 is None
    print(dict(n), "clients", len({meta[s]["client"] for s in S if edf_power.posterior_peak(f, S[s], min_height=2.0, min_width=0) != edf_power.posterior_peak(f, S[s], min_height=2.0, min_width=0.75)}))
    print("\nrepeats")
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
    for h, w in ((1.5, 0.75), (2.0, 0.75), (3.0, 0.75)):
        fn = rule(h, w)
        xy = np.array([(fn(S[a]), fn(S[b])) for a, b in prs if fn(S[a]) is not None and fn(S[b]) is not None], float)
        print(f"  h {h} w {w}: n {len(xy)} of {len(prs)} r {np.corrcoef(xy.T)[0, 1]:.2f} median |d| {np.median(np.abs(xy[:, 0] - xy[:, 1])):.2f}")


if __name__ == "__main__":
    main()
