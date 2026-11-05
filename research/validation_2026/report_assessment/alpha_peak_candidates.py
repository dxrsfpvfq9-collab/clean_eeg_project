"""Alpha-peak measures side by side, for every study that has the doctor's stated frequency
or a repeat recording. Stored by study id in <store>/alpha_candidates.json, no names.

    cur      the report's measure: mean over posterior sites of each site's 7-13 Hz maximum
    median   the same per-site peaks, median instead of mean
    pooled   maximum of the mean posterior spectrum
    detrend  pooled, after removing the 1/f slope (fit on 2-7 and 14-30 Hz, log-log)
    epoch    median over 4 s epochs of the posterior maximum, epochs with alpha >= half its median
    top      detrended peak of the spectrum averaged over the top half of epochs by alpha power
"""
import json
import multiprocessing as mp
import os
import sqlite3
import sys

import numpy as np
from scipy.signal import spectrogram, welch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from edf_power import _paf, site_of  # noqa: E402

STORE = r"C:\BrainPanel\source_db"
C = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
POST = ["O1", "O2", "P3", "P4", "PZ"]


def centroid(f, p, k):
    lo, hi = max(k - 1, 0), min(k + 2, len(f))
    return float(np.sum(f[lo:hi] * p[lo:hi]) / np.sum(p[lo:hi]))


def plain_peak(f, p):
    m = (f >= 7) & (f <= 13)
    k = int(np.argmax(p[m]))
    return None if k in (0, m.sum() - 1) else centroid(f[m], p[m], k)


def detrended(f, p):
    """(Hz, height over the 1/f line as a power ratio), or Nones when the maximum is on an edge."""
    fit = ((f >= 2) & (f <= 7)) | ((f >= 14) & (f <= 30))
    b = np.polyfit(np.log(f[fit]), np.log(p[fit] + 1e-12), 1)
    r = np.log(p + 1e-12) - np.polyval(b, np.log(np.maximum(f, 1e-3)))
    m = (f >= 7) & (f <= 13)
    k = int(np.argmax(r[m]))
    if k in (0, m.sum() - 1):
        return None, None
    return centroid(f[m], np.exp(r[m]), k), float(np.exp(r[m][k]))


def candidates(path):
    from epoch_reject_report import read_edf
    sigs, labels, fs = read_edf(path, 64)
    x = {}
    for s, lab in zip(sigs, labels):
        n = site_of(lab)
        if n in POST and n not in x and s.std() >= 0.01:
            x[n] = s - s.mean()
    if len(x) < 2:
        return None
    nper = int(4 * fs)
    spec, peaks = [], []
    for s in x.values():
        f, p = welch(s, fs=fs, nperseg=nper, average="median")
        spec.append(p)
        peaks.append(_paf(f, p))
    peaks = np.array(peaks, float)
    pool = np.mean(spec, axis=0)
    out = dict(cur=float(np.nanmean(peaks)) if np.isfinite(peaks).any() else None,
               median=float(np.nanmedian(peaks)) if np.isfinite(peaks).any() else None,
               spread=float(np.nanmax(peaks) - np.nanmin(peaks)) if np.isfinite(peaks).any() else None,
               pooled=plain_peak(f, pool))
    out["detrend"], out["detrend_h"] = detrended(f, pool)
    # per-epoch
    S = []
    for s in x.values():
        fe, _t, Sx = spectrogram(s, fs=fs, nperseg=nper, noverlap=0, window="hann", detrend="constant")
        S.append(Sx)
    S = np.mean(S, axis=0)
    a = S[(fe >= 8) & (fe < 13)].sum(axis=0)
    m = (fe >= 7) & (fe <= 13)
    pk = fe[m][np.argmax(S[m], axis=0)]
    out["epoch"] = float(np.median(pk[a >= 0.5 * np.median(a)]))
    top = a >= np.median(a)
    out["top"], out["top_h"] = detrended(fe[1:], S[1:][:, top].mean(axis=1))
    return out


def work(job):
    sid, path = job
    try:
        return sid, candidates(path)
    except Exception:
        return sid, None


def main():
    con = sqlite3.connect(os.path.join(STORE, "sources.db"))
    rows = con.execute("SELECT id, rel_path FROM studies WHERE status='ok'").fetchall()
    jobs = [(s, os.path.join(C, r)) for s, r in rows if os.path.exists(os.path.join(C, r))]
    print(len(jobs), "studies", flush=True)
    res = {}
    with mp.Pool(12) as pool:
        for k, (sid, v) in enumerate(pool.imap_unordered(work, jobs)):
            res[sid] = v
            if k % 200 == 0:
                print(k, flush=True)
    json.dump(res, open(os.path.join(STORE, "alpha_candidates.json"), "w"))
    print("done", len(res), "without values", sum(v is None for v in res.values()), flush=True)


if __name__ == "__main__":
    main()
