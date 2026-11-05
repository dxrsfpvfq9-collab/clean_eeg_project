"""Time-resolved vigilance features for each study: how the recording CHANGES,
which whole-recording band powers cannot show. Stored in table vigil_features
(store = source database). Read straight from the EDF, as the pipeline reads it;
nothing is written next to the originals.

Drowsiness is an event in time: posterior alpha drops out, moves forward, slows,
theta takes over, eyes roll, blinks stop, muscle tone falls, spindles appear.
Every feature below is one of those, measured per epoch:

  moments    true time moments (centroid, spread, skew) of each band's power at
             O1/O2 and Cz -- what the panel's Moments are meant to be, without
             int32 wrap-around, and with time scaled 0-1 so length does not matter
  dropout    share of epochs with posterior alpha under 25% of the recording's own
             90th percentile; longest such run; spread of log alpha
  trend      slope over the recording, and last third minus first third
  takeover   share of epochs with posterior theta > alpha, and theta + delta > alpha
  anterior   frontal / posterior alpha: median, 90th percentile, slope
  slowing    per-epoch alpha peak: SD, slope, last minus first third
  eyes       F7-F8 slow power (0.3-1 Hz) and blink rate, level and trend
  tone       21-45 Hz power trend (muscle relaxes with sleepiness)
  spindles   share of central epochs with an 11-15 Hz peak above their own median

    py tools/vigilance_features.py [--workers 12]     resumable
"""
import argparse
import json
import multiprocessing as mp
import os
import sqlite3
import sys

import numpy as np
from scipy.signal import find_peaks, spectrogram

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edf_power import site_of  # noqa: E402

DEFAULT_STORE = r"C:\BrainPanel\source_db"
CORPUS = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
EPOCH_S = 4.0
BANDS = {"delta": (1, 4), "theta": (4, 8), "alpha": (8, 13), "beta": (13, 21), "fast": (21, 45)}
POST = ["O1", "O2", "P3", "P4"]
FRONT = ["F3", "F4", "FZ"]
CENT = ["CZ", "FZ", "PZ", "C3", "C4"]
MIN_EPOCHS = 30


def _band(f, s, lo, hi):
    k = (f >= lo) & (f < hi)
    return s[k].sum(axis=0) * (f[1] - f[0])


def _slope(y):
    t = np.linspace(0, 1, len(y))
    m = np.isfinite(y)
    return float(np.polyfit(t[m], y[m], 1)[0]) if m.sum() > 5 else float("nan")


def _thirds(y):
    n = len(y) // 3
    return float(np.nanmedian(y[-n:]) - np.nanmedian(y[:n]))


def _moments(p):
    """Centroid, spread, skew of a power time course, time scaled 0-1. A clipped
    power course, so one artifact burst cannot own the centroid."""
    p = np.clip(p, 0, np.nanpercentile(p, 98))
    t = np.linspace(0, 1, len(p))
    w = p / (p.sum() or 1.0)
    c = float((w * t).sum())
    sd = float(np.sqrt((w * (t - c) ** 2).sum()))
    return c, sd, float((w * (t - c) ** 3).sum() / (sd ** 3 or 1.0))


def features(path):
    from epoch_reject_report import read_edf
    sigs, labels, fs = read_edf(path, 64)
    chans = {}
    for x, lab in zip(sigs, labels):
        s = site_of(lab)
        if s not in chans and x.std() >= 0.01:
            chans[s] = x - x.mean()
    if not all(s in chans for s in ("O1", "O2")):
        return None
    nper = int(EPOCH_S * fs)
    spec = {}
    for s, x in chans.items():
        f, _t, S = spectrogram(x, fs=fs, nperseg=nper, noverlap=0, window="hann",
                               detrend="constant", scaling="density")
        spec[s] = S
    n = S.shape[1]
    if n < MIN_EPOCHS:
        return None

    def mean_band(sites, band):
        return np.mean([_band(f, spec[s], *BANDS[band]) for s in sites if s in spec], axis=0)

    # epochs with a wild broadband excursion on the posterior sites are left out of levels
    a = mean_band(POST, "alpha") + 1e-9
    th = mean_band(POST, "theta") + 1e-9
    de = mean_band(POST, "delta") + 1e-9
    be = mean_band(POST, "beta") + 1e-9
    fa = mean_band(POST + FRONT, "fast") + 1e-9
    la = np.log(a)
    out = {"dur_s": len(x) / fs, "n_epochs": n}

    # moments, per band, at the sites the panel uses
    for band in BANDS:
        for name, sites in (("occ", ["O1", "O2"]), ("cz", ["CZ"])):
            if all(s in spec for s in sites):
                c, sd, sk = _moments(mean_band(sites, band))
                out[f"m1_{band}_{name}"], out[f"m2_{band}_{name}"], out[f"m3_{band}_{name}"] = c, sd, sk

    # alpha dropout
    low = a < 0.25 * np.percentile(a, 90)
    out["drop_frac"] = float(low.mean())
    run = best = 0
    for v in low:
        run = run + 1 if v else 0
        best = max(best, run)
    out["drop_run"] = best / n
    out["alpha_sd"] = float(np.std(la))
    out["alpha_iqr"] = float(np.subtract(*np.percentile(la, [75, 25])))
    r1 = np.corrcoef(la[:-1], la[1:])[0, 1]
    out["alpha_ac1"] = float(r1)              # slow waxing and waning, not epoch noise

    # trends
    for nm, y in (("alpha", la), ("theta", np.log(th)), ("delta", np.log(de)), ("beta", np.log(be)),
                  ("fast", np.log(fa)), ("ta", np.log(th / a))):
        out[f"slope_{nm}"] = _slope(y)
        out[f"late_{nm}"] = _thirds(y)
    ta = np.log(th / a)
    out["ta_med"] = float(np.median(ta))
    out["ta_p90"] = float(np.percentile(ta, 90))
    out["ta_sd"] = float(np.std(ta))

    # takeover
    out["theta_gt_alpha"] = float((th > a).mean())
    out["slow_gt_alpha"] = float(((th + de) > a).mean())
    out["delta_rel"] = float(np.median(de / (de + th + a + be)))

    # anterior shift
    if any(s in spec for s in FRONT):
        fr = np.log(mean_band(FRONT, "alpha") + 1e-9) - la
        out["ant_med"] = float(np.median(fr))
        out["ant_p90"] = float(np.percentile(fr, 90))
        out["ant_slope"] = _slope(fr)
        out["ant_late"] = _thirds(fr)

    # alpha peak per epoch, where there is alpha at all
    k = (f >= 7) & (f <= 13)
    P = np.mean([spec[s] for s in POST if s in spec], axis=0)
    pk = f[k][np.argmax(P[k], axis=0)]
    keep = a >= np.median(a) * 0.5
    y = np.where(keep, pk, np.nan)
    out["paf_sd"] = float(np.nanstd(y))
    out["paf_slope"] = _slope(y)
    out["paf_late"] = _thirds(y)
    out["paf_med"] = float(np.nanmedian(y))
    out["paf_lowfrac"] = float(np.nanmean(y < np.nanmedian(y) - 1))

    # eyes: slow lateral movement and blinks
    if "F7" in chans and "F8" in chans:
        d = chans["F7"] - chans["F8"]
        fq, _t, D = spectrogram(d, fs=fs, nperseg=int(8 * fs), noverlap=0, detrend="constant")
        sl = np.log(_band(fq, D, 0.3, 1.0) + 1e-9) - np.log(_band(fq, D, 1, 45) + 1e-9)
        out["sem_med"] = float(np.median(sl))
        out["sem_p90"] = float(np.percentile(sl, 90))
        out["sem_slope"] = _slope(sl)
        out["sem_late"] = _thirds(sl)
    if "FP1" in chans and "FP2" in chans:
        v = (chans["FP1"] + chans["FP2"]) / 2
        b = int(0.1 * fs)
        v = np.convolve(v, np.ones(b) / b, mode="same")
        th_b = np.median(np.abs(v)) * 6 + 1e-6
        pk_i, _ = find_peaks(v, height=th_b, distance=int(0.3 * fs))
        dur = len(v) / fs
        out["blink_rate"] = len(pk_i) / dur * 60
        tt = pk_i / len(v)
        out["blink_late"] = float(((tt > 2 / 3).sum() - (tt < 1 / 3).sum()) / max(len(tt), 1))

    # spindles: central 11-15 Hz peak over its own median
    cent = [s for s in CENT if s in spec]
    if cent:
        sg = np.mean([_band(f, spec[s], 11, 15) for s in cent], axis=0)
        nb = np.mean([_band(f, spec[s], 15, 19) + _band(f, spec[s], 7, 9) for s in cent], axis=0)
        ratio = np.log((sg + 1e-9) / (nb + 1e-9))
        out["sigma_frac"] = float((ratio > np.median(ratio) + 1.0).mean())
        out["sigma_late"] = _thirds(ratio)
    return {k: (None if v is None or not np.isfinite(v) else round(float(v), 5)) for k, v in out.items()}


def _work(job):
    sid, path = job
    try:
        return sid, features(path), None
    except Exception as exc:
        return sid, None, type(exc).__name__


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=DEFAULT_STORE)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    con = sqlite3.connect(os.path.join(a.store, "sources.db"))
    con.execute("CREATE TABLE IF NOT EXISTS vigil_features (study_id TEXT PRIMARY KEY, feat TEXT, error TEXT)")
    done = {r[0] for r in con.execute("SELECT study_id FROM vigil_features")}
    jobs = [(s, os.path.join(CORPUS, rel)) for s, rel in con.execute(
        "SELECT id, rel_path FROM studies WHERE status='ok'") if s not in done]
    jobs = jobs[:a.limit] if a.limit else jobs
    print(len(jobs), "to do", flush=True)
    n = bad = 0
    with mp.Pool(a.workers) as pool:
        for sid, feat, err in pool.imap_unordered(_work, jobs):
            con.execute("INSERT OR REPLACE INTO vigil_features VALUES (?,?,?)",
                        (sid, json.dumps(feat) if feat else None, err))
            n += 1
            bad += feat is None
            if n % 50 == 0:
                con.commit()
                print(n, "done,", bad, "without features", flush=True)
    con.commit()
    print("finished", n, "failed", bad, flush=True)


if __name__ == "__main__":
    main()
