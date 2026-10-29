"""Per-component source results WITHOUT the cascade GUI.

`dummy_gui` (files/dummy_gui.py) builds a full Tk component page and, along
the way, computes the four numbers the `.sources.npz` sidecar needs. This
repeats exactly that arithmetic with no window, no rendering and no PDF, so a
corpus can be processed at the cost of one ICA pass per study instead of a
minutes-long on-screen cascade render (see CLEANEEG_SIDECAR_ONLY in
files/Montage_6.py and tools/source_batch.py).

Kept identical to dummy_gui on purpose, quirks included:
  * % of variance = sum of squares of the component's mixing column over the
    whole mixing matrix, rounded to 0.1;
  * sLORETA: the mixing column, rows re-ordered to the Discovery channel order
    and cut to 19, times the 19chan.sLoreta.none.csv transfer matrix; voxel
    CSD = |xyz| per voxel; the source point is the FIRST maximum;
  * FFT peak: epochs `np.arange(2560*(i-1), 2560*i)` for i in range(numpages)
    -- i = 0 indexes the LAST 2560 samples by negative wrap-around, exactly as
    dummy_gui does -- |FFT| smoothed by the 7-tap kernel, averaged, and
    detect_peak on the first 650 bins / 10.
Parity, 2026-10-29, QA study F (EC): every array of a CLEANEEG_SIDECAR_ONLY
sidecar (csd, peaks, labels, %, FFT peaks, decisions, order, time courses) is
identical (max |diff| 0) to the one the full on-screen cascade wrote; 21 s per
study instead of minutes.
"""
import csv
import os

import numpy as np

from process.detect_artifact import detect_peak

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISC_ORDER = ['FP1', 'F3', 'C3', 'P3', 'O1', 'F7', 'T3', 'T5', 'FZ', 'FP2', 'F4', 'C4',
              'P4', 'O2', 'F8', 'T4', 'T6', 'CZ', 'PZ', 'A2', 'AX1', 'AX2']
KERNEL = np.array([1/16, 1/8, 3/16, 1/2, 3/16, 1/8, 1/16])
_cache = {}


def _tables():
    if "t" not in _cache:
        with open(os.path.join(_ROOT, "19chan.sLoreta.none.csv")) as fh:
            tmat = np.array([row[2:21] for row in csv.reader(fh)], dtype=float)
        with open(os.path.join(_ROOT, "MNI-BAs-6239-voxels.csv")) as fh:
            loc = np.array(list(csv.reader(fh)), dtype=str)
        _cache["t"] = (tmat, loc)
    return _cache["t"]


def _ordered_mixing(ica_mixing, channel_labels_short):
    if list(channel_labels_short) == DISC_ORDER:
        return np.asarray(ica_mixing)
    pos = {s: i for i, s in enumerate(channel_labels_short)}
    rows = sorted(channel_labels_short, key=DISC_ORDER.index)
    return np.array([ica_mixing[pos[s]] for s in rows])


def compute_components(ica_mixing, channel_labels_short, myvisualsigs, n, numsamples,
                       length=2560):
    """One dict per component, in FastICA order: perc, csd, source_point, peak."""
    tmat, loc = _tables()
    mix = np.asarray(ica_mixing, dtype=float)
    ordered = _ordered_mixing(mix, channel_labels_short)
    tot = np.sum(np.square(mix))
    numpages = numsamples // length - 1
    out = []
    for i in range(n):
        perc = round(float(np.sum(np.square(mix[:, i])) / tot * 100), 1)
        vec = ordered[:, i][:19]
        if tmat.shape[1] != len(vec):
            vec = vec[:-1]
        csd = np.linalg.norm((tmat @ vec).reshape(-1, 3), axis=1)
        sp = loc[int(np.argmax(csd)), :]
        amps = []
        for e in range(numpages):
            sig = myvisualsigs[i, np.arange(2560 * (e - 1), 2560 * e, 1)]
            amps.append(np.convolve(np.abs(np.fft.fft(sig)), KERNEL, mode="same"))
        avg = sum(amps) / len(amps)
        out.append(dict(perc=perc, csd=csd, source_point=sp, peak=detect_peak(avg[:650]) / 10))
    return out, loc
