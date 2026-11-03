"""EDF analysis report: age-adjusted electrode-space findings on one page,
plus the cascade's source pages when a sidecar exists.

Page 1 is computed from the EDF alone (tools/edf_power.py: median-Welch band
power per 10-20 site, no ICA), scored against the age-by-condition reference
models in the source database (tools/reference_ranges.py):

  * headline tiles -- posterior alpha peak, theta/beta at Cz, posterior alpha,
    frontal theta, F4/F3 alpha asymmetry, fast (21-30 Hz) activity, and a
    recording-quality grade -- each with its value, age-adjusted percentile and
    a typical range for the client's age;
  * head maps of age-adjusted z for relative delta / theta / alpha / beta;
  * findings: every tile at |z| >= 2, in plain language, with what the QA
    corpus label join (tools/label_join.py) says the feature tracks.

Pages 2-3 (optional) are tools/source_summary.py's source and network pages,
read from <edf>.sources.npz when present (or --sidecar).

THE REFERENCE IS A SCREENING POPULATION, NOT NORMS -- printed on the page.

    py tools/edf_report.py "<edf>" [--age N] [--cond EC|EO] [--out PDF]
                                   [--sidecar NPZ] [--store DIR]

Output defaults to <edf>.edfreport.pdf; for an EDF inside the Dropbox QA
corpus it goes to <store>/pdf/ instead, so nothing is written next to the
production files.
"""
import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import edf_power                                   # noqa: E402
import reference_ranges as rr                      # noqa: E402
from files.deidentify import deidentify_label      # noqa: E402

DEFAULT_STORE = r"C:\BrainPanel\source_db"
CORPUS = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
Z_FLAG = 2.0
MAP_BANDS = [("rel_delta", "Delta 1-4 Hz"), ("rel_theta", "Theta 4-8 Hz"),
             ("rel_alpha", "Alpha 8-13 Hz"), ("rel_beta", "Beta 13-21 Hz")]

# feature, title, unit/format, high sentence, low sentence, evidence note
TILES = [
    ("paf_post", "Alpha peak frequency", "{:.1f} Hz",
     "Posterior alpha peak is fast for age.",
     "Posterior alpha peak is slow for age (posterior dominant rhythm slowing).",
     "In the QA corpus a low alpha-peak z matched the reader's 'PDR slow for age' "
     "call (AUC 0.84)."),
    ("tbr_cz", "Theta/beta at Cz", "{:.2f}",
     "Theta/beta ratio at Cz is high for age.",
     "Theta/beta ratio at Cz is low for age.",
     "High theta/beta went with reader-confirmed PDR slowing (AUC 0.75) and with a "
     "clinical-abnormality comment (AUC 0.65)."),
    ("rel_alpha_post", "Posterior alpha", "{:.0f} %",
     "Posterior alpha is abundant for age.",
     "Posterior alpha is sparse for age.",
     "Relative alpha falls with drowsiness, eye opening and anxiety; read with the "
     "condition and the alpha peak."),
    ("rel_theta_front", "Frontal theta", "{:.0f} %",
     "Frontal theta is high for age.",
     "Frontal theta is low for age.",
     "Frontal theta was the strongest single marker of a clinical-abnormality comment "
     "in eyes-closed studies (AUC 0.68); it also rises with drowsiness."),
    ("alpha_asym_f4f3", "Frontal alpha asymmetry", "{:+.2f}",
     "More alpha over F4 than F3 than is usual for age (relatively less right-frontal "
     "activation).",
     "More alpha over F3 than F4 than is usual for age (relatively less left-frontal "
     "activation).",
     "ln(F4) - ln(F3) alpha power. A research marker; not validated against the QA labels."),
    ("rel_hibeta_mean", "Fast activity 21-30 Hz", "{:.1f} %",
     "Fast (21-30 Hz) activity is high for age -- muscle tension, medication "
     "(e.g. benzodiazepines) or hyperarousal.",
     "Fast (21-30 Hz) activity is low for age.",
     "Scalp muscle adds to this band; check the quality tile."),
]
TOPO_SITES = edf_power.SITES
FRONTAL = {"FP1", "FP2", "F7", "F8", "F3", "F4", "FZ"}


# ------------------------------------------------------------------ inputs
def guess_age_cond(base):
    m = re.search(r"AGE\s*(\d+)", base, re.IGNORECASE)
    toks = re.findall(r"(?<![a-z])(ec|eo)(?![a-z])", base.lower())
    return (int(m.group(1)) if m else None), (toks[-1].upper() if toks else None)


def edf_start(path):
    """Recording date from the EDF header ('dd.mm.yy'), or None. The patient
    fields are not read."""
    try:
        with open(path, "rb") as fh:
            h = fh.read(184)
        dd, mm, yy = (int(v) for v in h[168:176].decode("ascii").split("."))
        return f"{yy + (2000 if yy < 85 else 1900):04d}-{mm:02d}-{dd:02d}"
    except Exception:
        return None


def load_models(store, cond):
    con = sqlite3.connect(os.path.join(store, "sources.db"))
    out = {}
    for f, t, mc, sc, rz, n, amin, amax in con.execute(
            "SELECT feature, transform, mean_coef, sd_coef, resid_z, n, age_min, age_max "
            "FROM ref_models WHERE cond=?", (cond,)):
        out[f] = dict(transform=t, mean_coef=json.loads(mc), sd_coef=json.loads(sc),
                      resid_z=json.loads(rz), n=n, age_min=amin, age_max=amax)
    con.close()
    return out


def score(models, feature, age, value):
    """(z, percentile, (lo, hi) 2-SD range in feature units) or Nones."""
    m = models.get(feature)
    if m is None or age is None or value is None or not np.isfinite(value):
        return None, None, None
    z, p = rr.predict(m, [age], [value])
    mu = rr._design(np.array([age], float), 3) @ np.array(m["mean_coef"])
    sd = rr._design(np.array([age], float), 1) @ np.array(m["sd_coef"])
    rng = (float(rr.inv(m["transform"], mu - 2 * sd)[0]),
           float(rr.inv(m["transform"], mu + 2 * sd)[0]))
    return float(z[0]), float(p[0]), rng


def quality(cp, n_labels):
    """(grade, colour, detail) from the EDF alone."""
    line = max((cp[s]["line60"] for s in cp if np.isfinite(cp[s]["line60"])), default=np.nan)
    missing = [s for s in TOPO_SITES if s not in cp]
    hib = np.nanmean([cp[s]["rel_hibeta"] + cp[s]["rel_gamma"] for s in cp]) if cp else np.nan
    problems = []
    if missing:
        problems.append(f"{len(missing)} site(s) missing or flat ({', '.join(missing[:6])})")
    if np.isfinite(line) and line > 5:
        problems.append(f"60 Hz line noise up to {line:.0f}% of 1-80 Hz power")
    if np.isfinite(hib) and hib > 15:
        problems.append(f"21-45 Hz activity {hib:.0f}% (muscle?)")
    grade = "Good" if not problems else ("Fair" if len(problems) == 1 else "Poor")
    col = {"Good": "#2e7d32", "Fair": "#b26a00", "Poor": "#c62828"}[grade]
    return grade, col, "; ".join(problems) or "all 19 sites present, low line noise, low fast activity"


# ------------------------------------------------------------------ page 1
def zcolor(z):
    if z is None:
        return "#9e9e9e"
    a = abs(z)
    return "#c62828" if a >= Z_FLAG else ("#b26a00" if a >= 1.5 else "#2e7d32")


def page_edf(pdf, label, age, cond, rec, cp, models, notes):
    import matplotlib.pyplot as plt
    import mne
    sm = edf_power.summary(cp)
    fig = plt.figure(figsize=(8.5, 11))
    fig.text(0.06, 0.965, "EDF Analysis Report", fontsize=16, weight="bold")
    fig.text(0.06, 0.945, f"{label}", fontsize=9)
    fig.text(0.06, 0.930, f"Age {age if age is not None else 'unknown'}   "
             f"Condition {cond}   Recorded {rec or 'unknown'}   "
             f"Sites {sm['n_sites']}/19", fontsize=9)
    fig.text(0.94, 0.945, f"Generated {dt.date.today():%Y-%m-%d}", fontsize=8, ha="right",
             color="0.4")

    # --- tiles: 2 rows x 4
    findings = []
    tiles = TILES + [("__quality__",)]
    W, H, x0, y0 = 0.215, 0.135, 0.06, 0.765
    for k, t in enumerate(tiles):
        r, c = divmod(k, 4)
        ax = fig.add_axes([x0 + c * (W + 0.01), y0 - r * (H + 0.012), W, H])
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.autoscale(False)     # the percentile bar must not rescale the text
        if t[0] == "__quality__":
            grade, col, detail = quality(cp, None)
            for sp in ax.spines.values():
                sp.set_color(col)
                sp.set_linewidth(2)
            ax.text(0.06, 0.86, "Recording quality", fontsize=8, weight="bold", va="top")
            ax.text(0.06, 0.58, grade, fontsize=17, color=col, weight="bold", va="center")
            ax.text(0.06, 0.30, _wrap(detail, 34), fontsize=6, va="top", color="0.25")
            if grade != "Good":
                findings.append((None, f"Recording quality {grade.lower()}: {detail}. "
                                       "Interpret the other findings with caution.", ""))
            continue
        f, title, fmt, hi_s, lo_s, ev = t
        v = sm.get(f)
        z, p, rng = score(models, f, age, v)
        col = zcolor(z)
        for sp in ax.spines.values():
            sp.set_color(col)
            sp.set_linewidth(2 if z is not None and abs(z) >= Z_FLAG else 1)
        ax.text(0.06, 0.86, title, fontsize=8, weight="bold", va="top")
        ax.text(0.06, 0.58, fmt.format(v) if v is not None else "n/a", fontsize=17,
                color=col, weight="bold", va="center")
        if z is not None:
            ax.text(0.94, 0.58, f"z {z:+.1f}\n{_ordinal(p)} pct", fontsize=7, ha="right",
                    va="center")
            ax.text(0.06, 0.22, "typical for age: " + fmt.format(rng[0]) + " to " +
                    fmt.format(rng[1]), fontsize=6, color="0.3")
            # percentile bar
            ax.add_patch(plt.Rectangle((0.06, 0.08), 0.88, 0.05, color="0.88",
                                       transform=ax.transAxes))
            ax.add_patch(plt.Rectangle((0.06 + 0.88 * 0.025, 0.08), 0.88 * 0.95, 0.05,
                                       color="0.75", transform=ax.transAxes))
            ax.plot([0.06 + 0.88 * p / 100] * 2, [0.05, 0.16], color=col, lw=2.5,
                    transform=ax.transAxes)
            if abs(z) >= Z_FLAG:
                findings.append((z, hi_s if z > 0 else lo_s, ev))
        else:
            ax.text(0.06, 0.22, "no peak" if f == "paf_post" and v is None
                    else "no age reference", fontsize=6, color="0.3")
            if f == "paf_post" and v is None:
                findings.append((None, "No clear posterior alpha peak (7-13 Hz).", ""))

    # --- head maps
    info = mne.create_info([s.capitalize() if s.startswith("FP") else
                            (s[0] + s[1:].lower() if s.endswith("Z") else s)
                            for s in TOPO_SITES], 256, "eeg")
    info.set_montage("standard_1020")
    fig.text(0.06, 0.590, "Age-adjusted z by site (relative power)", fontsize=10,
             weight="bold")
    im = None
    for k, (col_, title) in enumerate(MAP_BANDS):
        ax = fig.add_axes([0.06 + k * 0.225, 0.405, 0.2, 0.16])
        z = []
        for s in TOPO_SITES:
            zz = score(models, f"{s}.{col_}", age, cp[s][col_]) if s in cp else (None,)
            z.append(zz[0] if zz[0] is not None else 0.0)
        im, _ = mne.viz.plot_topomap(np.array(z), info, axes=ax, show=False, cmap="RdBu_r",
                                     vlim=(-3, 3), contours=0, sensors=True)
        ax.set_title(title, fontsize=8)
        hot = [s for s, v in zip(TOPO_SITES, z) if abs(v) >= Z_FLAG]
        if len(hot) >= 4:
            word = "high" if np.mean([v for v in z if abs(v) >= Z_FLAG]) > 0 else "low"
            note = ""
            if col_ == "rel_delta" and word == "high" and set(hot) <= FRONTAL:
                note = ("Frontal-only slow activity is often eye movement or blinks rather "
                        "than cortical slowing.")
            findings.append((None, f"{title.split()[0]} is {word} for age at {len(hot)} sites "
                                   f"({', '.join(hot[:8])}"
                                   f"{f' +{len(hot) - 8} more' if len(hot) > 8 else ''}).", note))
    if im is not None:
        cax = fig.add_axes([0.93, 0.425, 0.012, 0.12])
        cb = fig.colorbar(im, cax=cax)
        cb.set_ticks([-3, -2, 0, 2, 3])
        cb.ax.tick_params(labelsize=6)
        cb.set_label("z", fontsize=7)

    # --- findings
    y = 0.37
    fig.text(0.06, y, "Findings", fontsize=10, weight="bold")
    y -= 0.022
    if age is None:
        findings.insert(0, (None, "Age unknown: no age-adjusted comparison is possible; "
                                  "values only.", ""))
    if not findings:
        findings = [(None, "All headline measures within the typical range for age "
                           f"(|z| < {Z_FLAG:.0f}).", "")]
    for z, s, ev in findings[:12]:
        fig.text(0.07, y, "\u2022 " + s, fontsize=8, color=zcolor(z) if z is not None else "0.1")
        y -= 0.016
        if ev:
            fig.text(0.085, y, ev, fontsize=6.5, color="0.35", style="italic")
            y -= 0.016
    for n in notes:
        fig.text(0.07, y, n, fontsize=7, color="#b26a00")
        y -= 0.014

    fig.text(0.06, 0.035, _wrap(
        "Reference: age-by-condition ranges fitted on one study per client of the STS QA corpus "
        f"({models.get('paf_post', {}).get('n', '?')} clients, {cond}) -- a population referred "
        "for EEG screening, not screened normals; z = 2 means unusual for that population at "
        "this age, not abnormal. Power from the raw EDF (median Welch, 4 s, no ICA). "
        "Screening information for a qualified practitioner; not a diagnosis.", 150),
        fontsize=6, color="0.35", va="bottom")
    pdf.savefig(fig)
    plt.close(fig)


def _wrap(s, n):
    import textwrap
    return "\n".join(textwrap.wrap(s, n))


def _ordinal(p):
    p = int(round(min(max(p, 1), 99)))
    suf = "th" if 10 <= p % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(p % 10, "th")
    return f"{p}{suf}"


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edf")
    ap.add_argument("--age", type=int)
    ap.add_argument("--cond", choices=["EC", "EO"])
    ap.add_argument("--out")
    ap.add_argument("--sidecar")
    ap.add_argument("--store", default=DEFAULT_STORE)
    a = ap.parse_args()

    base = os.path.basename(a.edf)[:-4]
    g_age, g_cond = guess_age_cond(base)
    age = a.age if a.age is not None else g_age
    cond = a.cond or g_cond
    notes = []
    if cond is None:
        cond = "EC"
        notes.append("Condition not in the file name: scored against the eyes-closed reference.")
    models = load_models(a.store, cond)
    if age is not None and "paf_post" in models and not (
            models["paf_post"]["age_min"] <= age <= models["paf_post"]["age_max"]):
        notes.append(f"Age {age} is outside the reference ages "
                     f"({models['paf_post']['age_min']:.0f}-{models['paf_post']['age_max']:.0f}); "
                     "ranges are extrapolated.")

    rec = edf_start(a.edf)
    cp = edf_power.chan_power(a.edf)

    out = a.out
    if not out:
        if os.path.abspath(a.edf).lower().startswith(CORPUS.lower()):
            import hashlib
            rel = os.path.relpath(a.edf, CORPUS)
            sid = hashlib.sha1(rel.lower().encode("utf-8")).hexdigest()[:12]
            out = os.path.join(a.store, "pdf", sid + ".edfreport.pdf")
        else:
            out = a.edf[:-4] + ".edfreport.pdf"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.backends.backend_pdf import PdfPages
    sidecar = a.sidecar or (a.edf[:-4] + ".sources.npz")
    with PdfPages(out) as pdf:
        page_edf(pdf, deidentify_label(base), age, cond, rec, cp, models, notes)
        if os.path.exists(sidecar):
            import source_summary as ss
            data = ss.load(sidecar)
            ss.page_sources(data, pdf)
            if data["sources"] is not None:
                ss.page_networks(data, pdf)
    print("wrote", out)


if __name__ == "__main__":
    main()
