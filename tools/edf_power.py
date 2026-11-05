"""Per-channel band power straight from the EDF (no ICA, no pipeline).

The source database's study_features come from the cascade decomposition; this
adds the electrode-space numbers a BrainView-class report headlines: absolute
and relative band power per 10-20 site, theta/beta ratio, and the individual
alpha peak per site.

Read exactly as the pipeline reads (mne, latin1, x1e6 -> uV, via
epoch_reject_report.read_edf). Spectra are MEDIAN Welch over 4 s segments, as
in compare_studies.eceo, so blink and movement bursts do not dominate -- the
signal is otherwise raw (no ICA, no artifact rejection), and the numbers are
electrode-space power, not the panel's rescaled values.

    py tools/edf_power.py "<edf>"        # print the table for one study
"""
import os
import re
import sys

import numpy as np
from scipy.signal import welch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 10-20 sites; new names map to the old ones the pipeline uses
SITES = ["FP1", "FP2", "F7", "F3", "FZ", "F4", "F8", "T3", "C3", "CZ", "C4", "T4",
         "T5", "P3", "PZ", "P4", "T6", "O1", "O2"]
ALIAS = {"T7": "T3", "T8": "T4", "P7": "T5", "P8": "T6"}
BANDS = [("delta", 1.0, 4.0), ("theta", 4.0, 8.0), ("alpha", 8.0, 13.0),
         ("beta", 13.0, 21.0), ("hibeta", 21.0, 30.0), ("gamma", 30.0, 45.0)]
TOTAL = (1.0, 45.0)
PEAK_PROM = 1.5      # same peak test as compare_studies: 7-13 Hz max >= 1.5x the flanks
SEG_S = 4.0


def site_of(label):
    s = re.sub(r"^(EEG|EXG)\s*", "", label.strip(), flags=re.I)
    s = re.split(r"[-_ ]", s)[0].upper()
    return ALIAS.get(s, s)


def _power(f, p, lo, hi):
    m = (f >= lo) & (f < hi)
    trap = getattr(np, "trapezoid", None) or np.trapz
    return float(trap(p[m], f[m])) if m.sum() > 1 else float("nan")


def _paf(f, p):
    m = (f >= 7.0) & (f <= 13.0)
    flank = np.mean(p[((f >= 4) & (f <= 6)) | ((f >= 14) & (f <= 18))])
    if p[m].max() < PEAK_PROM * flank:
        return float("nan")
    # centre of the peak bin and its two neighbours (0.25 Hz bins)
    k = int(np.argmax(p[m]))
    fm, pm = f[m], p[m]
    # a maximum on the window edge is theta (or beta) rising into it, not a
    # peak -- it piled eyes-open PAFs up at 7.1 Hz
    if k == 0 or k == len(fm) - 1:
        return float("nan")
    lo, hi = max(k - 1, 0), min(k + 2, len(fm))
    return float(np.sum(fm[lo:hi] * pm[lo:hi]) / np.sum(pm[lo:hi]))


def posterior_peak(f, p, min_height=1.5, min_width=0.25):
    """Alpha peak of a posterior spectrum, or None. The 1/f slope is removed first, so a
    shoulder on a falling spectrum is not a peak. Local maxima in 7-13 Hz only (not the window
    edges); a one-bin spike (width at half height under min_width Hz) is passed over. The
    tallest left must stand min_height times over the slope.

    Tuned on half the clients against the doctor's stated frequency, checked on the other half
    (research/validation_2026/report_assessment/). Do not widen min_width: real alpha is often
    under 0.75 Hz wide, and a 0.75 Hz test moved more studies away from the doctor than towards."""
    fit = ((f >= 2) & (f <= 7)) | ((f >= 14) & (f <= 30))
    b = np.polyfit(np.log(f[fit]), np.log(p[fit] + 1e-12), 1)
    ok = f > 0
    h = np.full(len(f), 1.0)
    h[ok] = np.exp(np.log(p[ok] + 1e-12) - np.polyval(b, np.log(f[ok])))
    idx = np.where((f >= 7) & (f <= 13))[0]
    best = None
    for k in idx[1:-1]:
        if not (h[k] >= h[k - 1] and h[k] > h[k + 1]) or h[k] < min_height:
            continue
        half = 1 + (h[k] - 1) / 2
        lo = k
        while lo > 0 and h[lo - 1] >= half:
            lo -= 1
        hi = k
        while hi < len(f) - 1 and h[hi + 1] >= half:
            hi += 1
        if f[hi] - f[lo] < min_width:
            continue
        if best is None or h[k] > h[best]:
            best = k
    if best is None:
        return None
    w = h[best - 1:best + 2]
    return float(np.sum(f[best - 1:best + 2] * w) / np.sum(w))


def chan_power(path):
    """{site: dict(abs_<band>, rel_<band>, total, tbr, paf, line60)} for every
    10-20 site present. abs in uV^2, rel as % of 1-45 Hz."""
    from epoch_reject_report import read_edf
    sigs, labels, fs = read_edf(path, 64)
    out = {}
    for x, lab in zip(sigs, labels):
        s = site_of(lab)
        if s not in SITES or s in out or x.std() < 0.01:
            continue
        f, p = welch(x - x.mean(), fs=fs, nperseg=int(SEG_S * fs), average="median")
        tot = _power(f, p, *TOTAL)
        row = {"total": tot}
        for name, lo, hi in BANDS:
            a = _power(f, p, lo, hi)
            row["abs_" + name] = a
            row["rel_" + name] = 100 * a / tot if tot > 0 else float("nan")
        row["tbr"] = row["abs_theta"] / row["abs_beta"] if row["abs_beta"] > 0 else float("nan")
        row["paf"] = _paf(f, p)
        row["_f"], row["_spec"] = f, p      # for summary()'s posterior peak; not stored
        # mains share; NaN when the sampling rate cannot see 60 Hz
        row["line60"] = (100 * _power(f, p, 58, 62) / _power(f, p, 1, 80)
                         if fs / 2 > 70 else float("nan"))
        out[s] = row
    return out


def summary(cp):
    """Study-level headline numbers from chan_power()."""
    def mean(sites, key):
        v = [cp[s][key] for s in sites if s in cp and np.isfinite(cp[s][key])]
        return float(np.mean(v)) if v else None
    post = [s for s in ("O1", "O2", "P3", "P4", "PZ") if s in cp]
    return dict(
        n_sites=len(cp),
        tbr_cz=cp["CZ"]["tbr"] if "CZ" in cp else None,
        tbr_fz=cp["FZ"]["tbr"] if "FZ" in cp else None,
        tbr_mean=mean(SITES, "tbr"),
        paf_post=(posterior_peak(cp[post[0]]["_f"], np.mean([cp[s]["_spec"] for s in post], axis=0))
                  if post else None),
        rel_alpha_post=mean(["O1", "O2", "P3", "P4", "PZ"], "rel_alpha"),
        rel_theta_front=mean(["F3", "FZ", "F4"], "rel_theta"),
        rel_delta_mean=mean(SITES, "rel_delta"),
        rel_hibeta_mean=mean(SITES, "rel_hibeta"),
        alpha_asym_f4f3=(float(np.log(cp["F4"]["abs_alpha"]) - np.log(cp["F3"]["abs_alpha"]))
                         if "F3" in cp and "F4" in cp and cp["F3"]["abs_alpha"] > 0
                         and cp["F4"]["abs_alpha"] > 0 else None),
        line60_max=max((cp[s]["line60"] for s in cp if np.isfinite(cp[s]["line60"])), default=None),
    )


if __name__ == "__main__":
    cp = chan_power(sys.argv[1])
    cols = ["rel_" + b[0] for b in BANDS] + ["tbr", "paf", "line60"]
    print("site  " + " ".join(f"{c.replace('rel_', '%'):>8}" for c in cols) + "   total uV2")
    for s in SITES:
        if s in cp:
            print(f"{s:5} " + " ".join(f"{cp[s][c]:8.2f}" for c in cols) + f"   {cp[s]['total']:9.1f}")
    for k, v in summary(cp).items():
        print(f"{k:16} {v}")
