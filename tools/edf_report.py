"""EDF analysis report: a plain-language cover, age-adjusted electrode-space
findings on one page, plus the cascade's source pages when a sidecar exists.

The cover (page_cover) restates the scores of the pages behind it in plain words
and lists what flagged findings have been seen in association with
(ASSOCIATIONS: textbook / review-level, never a diagnosis).

The EEG measures page is computed from the EDF alone (tools/edf_power.py: median-Welch band
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
                                   [--sidecar NPZ] [--models JSON] [--refit]

Scores come from the frozen bundle (tools/report_models.py), so no database is
needed. --refit scores from the source database instead, leaving this client
out: workstation only, and the one to use when testing accuracy on the corpus.

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
import report_models                               # noqa: E402
from files.deidentify import deidentify_label      # noqa: E402

DEFAULT_STORE = r"C:\BrainPanel\source_db"
CORPUS = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
Z_FLAG = 2.0
SUMMARY = {}          # what the cover said, for --summary: scores only, no names
MODEL_STAMP = ""      # set in main: which reference models scored this report
BRAIN_LOW = 50.0      # % of ICA variance kept as brain: under this, the source results are caveated
BRAIN_MIN = 25.0      # under this, sources and coupling are not scored at all
# Findings that can share one cause: a slower rhythm drops under the 8 Hz band edge and raises theta,
# theta/beta and frontal theta together. They count as one result. Low alpha joins only alongside one.
SLOW_CORE = {("paf_post", -1), ("tbr_cz", 1), ("rel_theta_front", 1), ("rel_theta", 1)}
SLOW_JOINS = {("rel_alpha_post", -1), ("rel_alpha", -1)}
LINE_BAD = 50.0       # % of 1-80 Hz power at the worst site
MAP_BANDS = [("rel_delta", "Delta 1-4 Hz"), ("rel_theta", "Theta 4-8 Hz"),
             ("rel_alpha", "Alpha 8-13 Hz"), ("rel_beta", "Beta 13-21 Hz")]

# feature, title, unit/format, high sentence, low sentence, evidence note
TILES = [
    ("paf_post", "Alpha peak frequency", "{:.1f} Hz",
     "Posterior alpha peak is fast for age.",
     "Posterior alpha peak is slow for age (posterior dominant rhythm slowing).",
     "In our review data a low alpha-peak z matched the reader's 'PDR slow for age' "
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
     "ln(F4) - ln(F3) alpha power. A research marker; not validated against doctors' comments."),
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


def patient_hash(path):
    """Same client key as source_batch (hash of the EDF patient field), so the
    study's own client is left out of its peers. The field itself is not kept."""
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha1(fh.read(88)[8:88].strip()).hexdigest()[:12]


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


def brain_share(data):
    """% of ICA variance in the components kept as brain, or None without a sidecar."""
    if data is None:
        return None
    tot = sum(c["pct"] for c in data["comps"]) or 1.0
    return 100 * sum(c["pct"] for c in data["comps"] if c["accept"]) / tot


def quality(cp):
    """(grade, colour, detail) from the EDF alone. The brain share stays out of the grade: at under
    25% the doctor used heavy artifact words in 1 of 13 of the newest studies, and the EDF measures
    are median-based. It gets its own sentence (plain_quality) instead."""
    line = max((cp[s]["line60"] for s in cp if np.isfinite(cp[s]["line60"])), default=np.nan)
    missing = [s for s in TOPO_SITES if s not in cp]
    hib = np.nanmean([cp[s]["rel_hibeta"] + cp[s]["rel_gamma"] for s in cp]) if cp else np.nan
    problems, info = [], []
    if missing:
        problems.append(f"{len(missing)} site(s) missing or flat ({', '.join(missing[:6])})")
    if np.isfinite(hib) and hib > 15:
        problems.append(f"21-45 Hz activity {hib:.0f}% (muscle?)")
    # Mains sits outside the 1-45 Hz every measure uses, and is present in most
    # raw QA recordings, so it only counts when it swamps the EEG (> 50% of
    # 1-80 Hz power at the worst site: suspect electrode contact).
    if np.isfinite(line) and line > LINE_BAD:
        problems.append(f"60 Hz line noise {line:.0f}% of 1-80 Hz power (electrode contact?)")
    elif np.isfinite(line) and line > 5:
        info.append(f"60 Hz line noise up to {line:.0f}% (outside the 1-45 Hz measures)")
    grade = "Good" if not problems else ("Fair" if len(problems) == 1 else "Poor")
    col = {"Good": "#2e7d32", "Fair": "#b26a00", "Poor": "#c62828"}[grade]
    detail = "; ".join(problems + info) or "all 19 sites present, low line noise, low fast activity"
    return grade, col, detail


# ------------------------------------------------------------------ cover page
# feature -> plain name, what it is, higher sentence, lower sentence
PLAIN = {
    "paf_post": ("Speed of the main resting rhythm", "the main rhythm at the back of the head",
                 "Faster than usual for this age.", "Slower than usual for this age."),
    "tbr_cz": ("Slow-to-fast balance", "slow compared with fast activity at the top of the head",
               "More slow activity, relative to fast, than usual.",
               "Less slow activity, relative to fast, than usual."),
    "rel_alpha_post": ("Resting rhythm strength", "how much of the back-of-head activity is resting rhythm",
                       "Stronger than usual for this age.", "Weaker than usual for this age."),
    "rel_theta_front": ("Slow activity at the front", "slower activity over the front of the head",
                        "More than usual for this age.", "Less than usual for this age."),
    "alpha_asym_f4f3": ("Left-right balance at the front", "resting rhythm on the right vs the left front",
                        "More resting rhythm on the right than usual.",
                        "More resting rhythm on the left than usual."),
    "rel_hibeta_mean": ("Very fast activity", "the fastest activity measured here (21-30 cycles per second)",
                        "More than usual for this age.", "Less than usual for this age."),
}
# (feature or band column, direction) -> (finding, seen in association with, strength of evidence).
# Textbook / review-level associations, for a clinician to weigh. Never a diagnosis.
ASSOCIATIONS = {
    ("paf_post", -1): ("Slower main rhythm",
                       "drowsiness, sedating medication, cognitive decline or dementia, and "
                       "brain injury or other medical conditions affecting the brain.",
                       "well established; matched reviewers' 'slow for age' calls in our data"),
    ("tbr_cz", 1): ("Higher slow-to-fast balance",
                    "drowsiness, and attention problems (ADHD). Group studies differ widely and it "
                    "does not identify ADHD in an individual (Arns et al. 2013).",
                    "mixed"),
    ("rel_alpha_post", -1): ("Weaker resting rhythm",
                             "drowsiness, tension or anxiety, and older age; also expected with eyes open.",
                             "moderate, not specific"),
    ("rel_alpha_post", 1): ("Stronger resting rhythm",
                            "relaxed wakefulness; raised in some studies of depression.",
                            "mixed"),
    ("rel_theta_front", 1): ("More slow activity at the front",
                             "drowsiness, sedating medication, attention problems, and some "
                             "mood or cognitive complaints.",
                             "moderate, not specific; matched reviewers' abnormality comments in our data"),
    ("alpha_asym_f4f3", -1): ("More resting rhythm on the left front",
                              "low mood and depression in research studies; pooled results do not "
                              "support it as a test for depression (van der Vinne et al. 2017).",
                              "research only, weak"),
    ("rel_hibeta_mean", 1): ("More very fast activity",
                             "muscle tension, benzodiazepine or barbiturate use, and "
                             "anxiety, hyperarousal or poor sleep.",
                             "established for these medications; otherwise moderate"),
    ("rel_delta", 1): ("More very slow activity in several areas",
                       "drowsiness, sedating medication, brain injury and other medical conditions "
                       "affecting the brain. At the front only, usually eye movement.",
                       "well established, not specific"),
    ("rel_theta", 1): ("More slow activity in several areas",
                       "drowsiness, sedating medication, and attention or cognitive complaints.",
                       "moderate, not specific"),
    ("rel_alpha", -1): ("Less resting rhythm in several areas",
                        "drowsiness, tension or anxiety, and eyes open.",
                        "moderate, not specific"),
    ("rel_beta", 1): ("More fast activity in several areas",
                      "benzodiazepine or barbiturate use, muscle tension, and anxiety or hyperarousal.",
                      "established for these medications; otherwise moderate"),
}
BAND_PLAIN = {"rel_delta": "very slow", "rel_theta": "slow", "rel_alpha": "resting-rhythm",
              "rel_beta": "fast"}


def site_z(models, age, cp, col_):
    """Age-adjusted z per 10-20 site for one band; 0 where unavailable."""
    z = []
    for s in TOPO_SITES:
        zz = score(models, f"{s}.{col_}", age, cp[s][col_]) if s in cp else (None,)
        z.append(zz[0] if zz[0] is not None else 0.0)
    return z


def group_stats(store, cond):
    """(share of this condition's studies with >= 1 of the six measures at |z| >= 2,
    median number of panel rows out of range). Nones when unavailable."""
    con = sqlite3.connect(os.path.join(store, "sources.db"))
    feats = [t[0] for t in TILES]
    row = con.execute(
        "SELECT AVG(h) FROM (SELECT MAX(ABS(r.z) >= ?) h FROM ref_z r JOIN studies s ON s.id = r.study_id "
        f"WHERE s.cond = ? AND r.feature IN ({','.join('?' * len(feats))}) GROUP BY r.study_id)",
        [Z_FLAG, cond] + feats).fetchone()
    counts = [r[0] for r in con.execute(
        "SELECT SUM(ABS(p.z) >= ?) FROM panel p JOIN studies s ON s.id = p.study_id "
        "WHERE s.cond = ? GROUP BY p.study_id", (Z_FLAG, cond))]
    con.close()
    return row[0], (float(np.median(counts)) if counts else None)


def plain_quality(grade, detail, brain=None):
    low = brain is not None and brain < BRAIN_LOW
    source = " Much of the signal was set aside as artifact, so the source results are less certain." if low else ""
    if grade == "Good":
        return ("Recording quality: good." + source) if low else "Recording quality: good. No significant problems were found."
    why = []
    if "missing" in detail:
        why.append("some electrodes gave no usable signal")
    if "muscle" in detail:
        why.append("muscle activity may have affected the fast measures")
    if "electrode contact" in detail:
        why.append("strong electrical interference suggests a poor electrode contact")
    return (f"Recording quality: {grade.lower()}. " + "; ".join(why).capitalize()
            + ". Treat these results with extra caution." + source)


def stamp(fig):
    fig.text(0.94, 0.008, MODEL_STAMP, fontsize=5.5, color="0.5", ha="right")


def page_cover(pdf, label, age, cond, rec, cp, models, notes, panel, data, typ, ctyp, stats, contents,
               drowsy=None):
    """Plain-language summary. Reuses the same scores as the pages behind it."""
    import matplotlib.pyplot as plt
    sm = edf_power.summary(cp)
    fig = plt.figure(figsize=(8.5, 11))
    L, R = 0.06, 0.94
    fig.text(L, 0.965, "BrainMaster BrainPanel / ICA Analysis Report", fontsize=18, weight="bold", color="#1a1a1a")
    fig.text(L, 0.942, label, fontsize=9, color="0.25")
    fig.text(L, 0.926, f"Age {age if age is not None else 'unknown'}   ·   "
             f"{'Eyes closed' if cond == 'EC' else 'Eyes open'}   ·   Recorded {rec or 'unknown'}",
             fontsize=9, color="0.25")

    # --- score everything first: the headline needs the count
    rows, flagged = [], []
    for f, *_ in TILES:
        name, what, hi, lo = PLAIN[f]
        v = sm.get(f)
        z, p, _rng = score(models, f, age, v)
        if f == "paf_post" and v is None:
            rows.append((name, "No clear main rhythm was found.", "Not found", "#b26a00", None))
            continue
        if z is None:
            rows.append((name, what.capitalize() + ".", "No comparison", "#777", None))
            continue
        SUMMARY.setdefault("tiles", {})[f] = dict(value=float(v), z=round(z, 3), pct=round(p, 1))
        if abs(z) >= Z_FLAG:
            flagged.append((abs(z), (f, 1 if z > 0 else -1), hi if z > 0 else lo))
        state = ("Typical" if abs(z) < 1.5 else "Slightly " if abs(z) < Z_FLAG else "")
        if state != "Typical":
            state += "higher" if z > 0 else "lower"
        rows.append((name, (hi if z > 0 else lo) if abs(z) >= 1.5 else what.capitalize() + ".",
                     state.capitalize(), zcolor(z), p))
    if drowsy:      # a soft note: never counted as a result that stands out
        if drowsy["possible"]:
            rows.append(("Signs of drowsiness",
                         "May suggest drowsiness. A reader noted it in about "
                         f"{10 * drowsy['rate']:.0f} of 10 recordings scoring this high.",
                         "Possible", "#b26a00", None))
        else:
            rows.append(("Signs of drowsiness",
                         "No clear pattern of drowsiness, though this measure can miss it.",
                         "No clear signs", "#2e7d32", None))
    assoc_keys = [(k, s) for _, k, s in sorted(flagged, key=lambda t: -t[0])]
    n_stand = len(flagged)
    if age is not None:
        for col_, _t in MAP_BANDS:
            zs = site_z(models, age, cp, col_)
            hot = [s for s, v in zip(TOPO_SITES, zs) if abs(v) >= Z_FLAG]
            if len(hot) >= 4:
                d = 1 if np.mean([v for v in zs if abs(v) >= Z_FLAG]) > 0 else -1
                n_stand += 1
                assoc_keys.append(((col_, d), f"{BAND_PLAIN[col_].capitalize()} activity is "
                                   f"{'high' if d > 0 else 'low'} at {len(hot)} of 19 sites."))

    brain = brain_share(data)
    if data is not None:
        if typ:
            ap = typ["atyp_pctile"]
            st, col = (("Unusual", "#c62828") if ap >= 95 else ("Somewhat unusual", "#b26a00")
                       if ap >= 85 else ("Typical", "#2e7d32"))
            n_stand += ap >= 95
        else:
            st, col, ap = "No comparison", "#777", None
        # no bar: for this score only the top end means unusual
        txt = f"About {brain:.0f}% of the signal's strength came from brain sources; the rest was set aside as artifact."
        label_ = "Mix: " + st.lower() if st != "No comparison" else st
        if brain < BRAIN_MIN:
            txt = (f"Only about {brain:.0f}% of the signal's strength came from brain sources, too little to "
                   "compare. The rest was set aside as blinks, muscle or similar.")
            label_, col = "Too little signal", "#b26a00"
        elif brain < BRAIN_LOW:
            txt = (f"Only about {brain:.0f}% of the signal's strength came from brain sources, so this result "
                   "is less certain. The rest was set aside as blinks, muscle or similar.")
            col = "#b26a00" if col == "#2e7d32" else col
        rows.append(("Where the activity comes from", txt, label_, col, None))
    if ctyp:
        pcs = {b: v["pctile"] for b, v in ctyp["bands"].items() if v["pctile"] is not None}
        hi_b = [b.lower() for b, p in pcs.items() if p >= 95]
        lo_b = [b.lower() for b, p in pcs.items() if p <= 5]
        n_stand += bool(hi_b or lo_b)
        n_unc = sum(v["n_uncommon"] for v in ctyp["bands"].values())
        txt = []
        if hi_b:
            txt.append("Stronger than usual in " + ", ".join(hi_b) + ".")
        if lo_b:
            txt.append("Weaker than usual in " + ", ".join(lo_b) + ".")
        if not txt:
            txt.append("How much brain areas rise and fall together.")
        if n_unc:
            txt.append(f"{n_unc} uncommon link{'s' if n_unc > 1 else ''} between areas.")
        st, col = ("Unusual", "#c62828") if hi_b or lo_b else ("Typical", "#2e7d32")
        rows.append(("How brain areas work together", " ".join(txt), st, col, None))
    if panel:
        z = np.array([np.nan if v is None else v for v in panel["z"]], float)
        if panel["values"][1] is not None and abs(panel["values"][1] - 1000) < 1e-6:
            z[1] = np.nan
        n_oob = int(np.nansum(np.abs(z) >= Z_FLAG))
        mid = f" Half of people in this group have {stats[1]:.0f} or fewer." if stats[1] is not None else ""
        adult = (" Its reference is adults with eyes closed, so more are expected here."
                 if cond == "EO" or (age is not None and age < 18) else "")
        many = n_oob >= max(8, 2 * (stats[1] or 0))
        if many:
            adult = " Its one adult eyes-closed reference differs from this report's comparison by age; see p.3."
        rows.append(("Brain Panel", f"{n_oob} of 48 measures were out of range.{mid}{adult}",
                     f"{n_oob} of 48", "#b26a00" if many else "#555", None))

    # --- findings that can share one cause count once
    n_raw, raw_keys = n_stand, [f"{k[0]}:{k[1]}" for k, _s in assoc_keys]
    slow = [k for k, _s in assoc_keys if k in SLOW_CORE]
    if slow:
        slow += [k for k, _s in assoc_keys if k in SLOW_JOINS]
    if len(slow) >= 2:
        n_stand -= len(slow) - 1
        first = next(i for i, (k, _s) in enumerate(assoc_keys) if k in slow)
        rep_k = assoc_keys[first][0]
        also = [ASSOCIATIONS[k][0].lower() for k in slow if k != rep_k]
        joined = (rep_k, "group")
        finding, seen, strength = ASSOCIATIONS[rep_k]
        grouped = ("Slower activity, seen in " + str(len(slow)) + " measures", seen
                   + " Also seen here: " + ", ".join(also) + ". These can share one cause, so they count as one result.",
                   strength)
        assoc_keys = [(joined, "") if i == first else a for i, a in enumerate(assoc_keys) if a[0] not in slow or i == first]
    else:
        joined = grouped = None

    # --- headline
    grade, _c, detail = quality(cp)
    SUMMARY.update(
        n_raw=n_raw, n_slow_grouped=len(slow) if len(slow) >= 2 else 0,
        age=age, cond=cond, n_stand=n_stand, grade=grade, quality=detail, notes=notes,
        rows=[(r[0], r[2]) for r in rows], assoc=raw_keys,
        drowsy=drowsy,
        atyp_pctile=typ["atyp_pctile"] if typ else None,
        brain_pct=brain if data is not None else None,
        coupling={b: dict(pct=v["pctile"], uncommon=v["n_uncommon"], n_pairs=v["n_pairs"])
                  for b, v in ctyp["bands"].items()} if ctyp else None,
        n_oob=n_oob if panel else None, contents=[t for _p, t in contents])
    if age is None:
        head = "No age given, so nothing could be compared by age."
    elif n_stand == 0 and grade == "Poor":
        head = "Nothing stands out for this age, but recording quality is poor."
    elif n_stand == 0:
        head = "Nothing in this recording stands out for someone of this age."
    elif n_stand == 1:
        head = "One result stands out for someone of this age."
    else:
        head = f"{n_stand} results stand out for someone of this age."
    box = "#f0f0f0" if age is None or (grade == "Poor" and not n_stand) else "#fdf1f0" if n_stand else "#eef6ef"
    fig.patches.append(plt.Rectangle((L, 0.846), R - L, 0.064, transform=fig.transFigure,
                                     facecolor=box, edgecolor="none"))
    fig.text(L + 0.015, 0.889, head, fontsize=12.5, weight="bold", color="#1a1a1a", va="center")
    fig.text(L + 0.015, 0.862, _wrap(plain_quality(grade, detail, brain), 112), fontsize=8.2, color="0.2", va="center")

    # --- at a glance
    y = 0.822
    fig.text(L, y, "Results at a glance", fontsize=11, weight="bold", color="#1a1a1a")
    fig.text(R, y, "bar: typical range for this age; mark: this recording", fontsize=7,
             color="0.4", ha="right")
    y -= 0.014
    fig.lines.append(plt.Line2D([L, R], [y, y], transform=fig.transFigure, color="0.7", lw=0.6))
    LINE2 = 0.011
    two = [len(_wrap(r[1], 104).split("\n")) > 1 for r in rows]
    step = min(0.044, (0.385 - LINE2 * sum(two)) / max(len(rows), 1))
    y -= step * 0.42
    for name, txt, st, col, p in rows:
        fig.text(L, y + 0.007, name, fontsize=8.5, weight="bold", color="#1a1a1a", va="center")
        fig.text(L, y - 0.008, _wrap(txt, 104).split("\n")[0], fontsize=7.2, color="0.3", va="center")
        if len(_wrap(txt, 104).split("\n")) > 1:
            fig.text(L, y - 0.019, _wrap(txt, 104).split("\n")[1], fontsize=7.2, color="0.3", va="center")
        fig.text(0.72, y, st, fontsize=8.2, weight="bold", color=col, va="center")
        if p is not None:
            x0, w = 0.85, R - 0.85
            fig.patches.append(plt.Rectangle((x0, y - 0.003), w, 0.006, transform=fig.transFigure,
                                             facecolor="0.88", edgecolor="none"))
            fig.patches.append(plt.Rectangle((x0 + w * 0.025, y - 0.003), w * 0.95, 0.006,
                                             transform=fig.transFigure, facecolor="0.72", edgecolor="none"))
            xp = x0 + w * min(max(p, 0), 100) / 100
            fig.lines.append(plt.Line2D([xp, xp], [y - 0.008, y + 0.008], transform=fig.transFigure,
                                        color=col, lw=2.5))
        y -= step + (LINE2 if len(_wrap(txt, 104).split("\n")) > 1 else 0)

    # --- seen in association with
    y -= 0.012
    fig.text(L, y, "What these findings have been seen with", fontsize=11, weight="bold", color="#1a1a1a")
    y -= 0.018
    shown = [(grouped if k == joined else ASSOCIATIONS[k], s) for k, s in assoc_keys
             if k == joined or k in ASSOCIATIONS]
    others = len(assoc_keys) - len(shown)
    if age is None:
        fig.text(L, y, "Nothing could be compared without an age, so there is nothing to note here.",
                 fontsize=8, color="0.3")
        y -= 0.018
    elif not n_stand:
        fig.text(L, y, "No result stands out, so there is nothing to note here.", fontsize=8, color="0.3")
        y -= 0.018
    elif not assoc_keys:
        fig.text(L, y, "The result that stands out here (brain sources or coupling) has no well-described "
                 "link to symptoms or conditions.", fontsize=8, color="0.3")
        y -= 0.018
    for (finding, seen, strength), _s in shown[:4]:
        lines = _wrap("Has been seen in association with " + seen, 112).split("\n")
        fig.text(L, y, finding, fontsize=8.2, weight="bold", color="#1a1a1a")
        fig.text(R, y, f"Evidence: {strength}", fontsize=6.6, color="0.4", ha="right", style="italic")
        y -= 0.014
        for ln in lines:
            fig.text(L, y, ln, fontsize=7.4, color="0.2")
            y -= 0.0125
        y -= 0.004
    extra = max(len(shown) - 4, 0) + others
    if extra:
        fig.text(L, y, f"+ {extra} more finding(s) with no well-described association, or not shown here; "
                 "see the pages behind.", fontsize=7.2, color="0.4")
        y -= 0.014
    if assoc_keys:
        fig.text(L, y, _wrap("These are patterns reported in groups of people. They also occur in people with no "
                 "symptoms, and they do not show that this person has any of these conditions.", 118),
                 fontsize=7.4, color="#8a4b00", va="top")
        y -= 0.03

    # --- keep in mind
    y -= 0.012
    fig.text(L, y, "Keep in mind", fontsize=11, weight="bold", color="#1a1a1a")
    y -= 0.016
    usual = (f"About {100 * stats[0]:.0f} in 100 people in this group have at least one of the six rhythm "
             "measures stand out, so one result alone is common. " if stats[0] is not None and age is not None else "")
    para = (usual + "\"Typical\" means compared with other people of this age referred for EEG screening, "
            "not with people known to be healthy. The sources and coupling results are descriptive: in our "
            "testing they did not reliably match doctors' comments. This is screening information for a "
            "qualified practitioner, not a diagnosis.")
    fig.text(L, y, _wrap(para, 122), fontsize=7.4, color="0.2", va="top", linespacing=1.3)

    # --- contents
    fig.text(L, 0.045, "In this report:  " + "   ·   ".join(f"p.{p} {t}" for p, t in contents),
             fontsize=7.2, color="0.35")
    if notes:
        fig.text(L, 0.030, _wrap(" ".join(notes), 130), fontsize=6.8, color="#b26a00", va="top")
    stamp(fig)
    pdf.savefig(fig)
    plt.close(fig)


# ------------------------------------------------------------------ page 2: EDF
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
    fig.text(0.06, 0.965, "EEG Measures", fontsize=16, weight="bold")
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
            grade, col, detail = quality(cp)
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
        z = site_z(models, age, cp, col_)
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
        for k_, ln_ in enumerate(_wrap(s, 112).split("\n")):
            fig.text(0.07 if k_ == 0 else 0.082, y, ("\u2022 " if k_ == 0 else "") + ln_, fontsize=8,
                     color=zcolor(z) if z is not None else "0.1")
            y -= 0.016
        if ev:
            fig.text(0.085, y, ev, fontsize=6.5, color="0.35", style="italic")
            y -= 0.016
    for n in notes:
        fig.text(0.07, y, n, fontsize=7, color="#b26a00")
        y -= 0.014

    fig.text(0.06, 0.035, _wrap(
        "Reference: age-by-condition ranges fitted on one study per client of our EEG screening database "
        f"({models.get('paf_post', {}).get('n', '?')} clients, {cond}) -- a population referred "
        "for EEG screening, not screened normals; z = 2 means unusual for that population at "
        "this age, not abnormal. Power from the raw EDF (median Welch, 4 s, no ICA). "
        "Screening information for a qualified practitioner; not a diagnosis.", 150),
        fontsize=6, color="0.35", va="bottom")
    stamp(fig)
    pdf.savefig(fig)
    plt.close(fig)


# ------------------------------------------------------------------ page 2: Brain Panel
# (panel row, sign, EDF feature, title, panel-row label). sign = how the panel
# row moves when the EDF feature rises; pairs and rho from
# tools/panel_crosscheck.py (eyes-closed, n=334).
PANEL_PAIRS = [
    (15, +1, "paf_post", "Alpha peak frequency", "Alpha Peak (rho 0.74)"),
    (10, +1, "rel_alpha_post", "Posterior alpha", "PDR Burst Width (rho 0.55)"),
    (14, -1, "tbr_cz", "Theta/beta", "Alpha Speed (rho -0.37)"),
    (30, +1, "rel_theta_front", "Frontal theta", "Diffuse Theta (rho 0.39)"),
]
# What the published discriminants did against the doctor's labels in the QA
# corpus (tools/panel_crosscheck.py, applied as published, no fitting).
DISC_QA_AUC = {"Clinical Abnormality": 0.55, "PDR frequency": 0.53, "Drowsiness": 0.43,
               "Paroxysmal": 0.33}


def find_panel(edf, explicit=None):
    for p in ([explicit] if explicit else []) + [edf[:-4] + ".icale.rep.pdf"]:
        if p and os.path.exists(p):
            sys.path.insert(0, os.path.join(ROOT, "research", "validation_2026"))
            from panel_parser import parse_panel_pdf, NAME_STRINGS
            r = parse_panel_pdf(p)
            if r.get("valid"):
                return dict(values=r["values"], z=r["zscores"], names=NAME_STRINGS,
                            version=r.get("version"), date=r.get("report_date"))
    return None


def _agree(zp, ze, sign):
    """Agreement wording for one panel row vs its EDF counterpart."""
    if zp is None or ze is None or not np.isfinite(zp) or not np.isfinite(ze):
        return "n/a", "#9e9e9e"
    fp, fe = abs(zp) >= Z_FLAG, abs(ze) >= Z_FLAG
    dp, de = np.sign(zp) * sign, np.sign(ze)
    if fp and fe:
        if dp == de:
            return "both " + ("high" if de > 0 else "low"), "#c62828"
        return "CONFLICT", "#6a1b9a"
    if not fp and not fe:
        return "both typical", "#2e7d32"
    # one flagged, the other leaning the same way (|z| >= 1.5): agreement, not a split
    other, who = (ze, "EDF") if fp else (zp, "panel")
    d_flag = dp if fp else de
    d_other = de if fp else dp
    if abs(other) >= 1.5 and d_flag == d_other:
        return f"both {'high' if d_flag > 0 else 'low'} ({who} borderline)", "#c62828"
    return ("panel only", "#b26a00") if fp else ("EDF only", "#b26a00")


def page_panel(pdf, label, age, cond, panel, cp, models, internal=False):
    import matplotlib.pyplot as plt
    from process.discriminant import compute_oob_counts, compute_scores, GROUP_INDEXES
    sm = edf_power.summary(cp)
    z = np.array([np.nan if v is None else v for v in panel["z"]], float)
    vals = panel["values"]
    std_bad = vals[1] is not None and abs(vals[1] - 1000) < 1e-6
    if std_bad:
        z[1] = np.nan
    fig = plt.figure(figsize=(8.5, 11))
    fig.text(0.06, 0.965, "Brain Panel cross-check", fontsize=16, weight="bold")
    fig.text(0.06, 0.945, label, fontsize=9)
    fig.text(0.06, 0.930, f"Brain Panel {panel.get('version') or ''}"
             f"{', dated ' + panel['date'] if panel.get('date') else ''}", fontsize=8.5)
    fig.text(0.06, 0.916, "48 measures as z against one adult eyes-closed reference, not "
             "adjusted for age", fontsize=8, color="0.35")

    # --- out-of-range rows by group
    groups = [("std_global", "Std/Global"), ("pdr", "PDR"), ("phenotypes", "Phenotypes"),
              ("focal", "Focal"), ("diffuse", "Diffuse"), ("state_shift", "State shift")]
    y = 0.895
    fig.text(0.06, y, "Out-of-range panel rows (|z| >= 2)", fontsize=10, weight="bold")
    y -= 0.024
    total = 0
    for g, title in groups:
        idx = GROUP_INDEXES[g]
        hit = [i for i in idx if np.isfinite(z[i]) and abs(z[i]) >= Z_FLAG]
        total += len(hit)
        txt = ", ".join(f"{panel['names'][i]} {z[i]:+.1f}" for i in
                        sorted(hit, key=lambda i: -abs(z[i]))) or "none"
        lines = _wrap(txt, 95).split("\n")
        fig.text(0.07, y, f"{title} ({len(hit)}/{len(idx)})", fontsize=8, weight="bold")
        for ln in lines:
            fig.text(0.22, y, ln, fontsize=7.5, color="#c62828" if hit else "0.35")
            y -= 0.015
        y -= 0.004
    fig.text(0.07, y, f"Total out of range: {total} of 48"
             + ("   (Global STD = 1000: pre-fix panel, row ignored)" if std_bad else ""),
             fontsize=8, color="0.2")
    y -= 0.04

    # --- agreement with the EDF analysis
    fig.text(0.06, y, "Does the panel agree with the EDF analysis?", fontsize=10, weight="bold")
    y -= 0.024
    for x, h in [(0.07, "Measure"), (0.27, "Panel row"), (0.52, "Panel"),
                 (0.62, "EDF (for age)"), (0.78, "Reading")]:
        fig.text(x, y, h, fontsize=8, weight="bold")
    y -= 0.018
    readings = []
    for row, sign, feat, title, prow in PANEL_PAIRS:
        zp = float(z[row]) if np.isfinite(z[row]) else None
        ze = score(models, feat, age, sm.get(feat))[0]
        word, col = _agree(zp, ze, sign)
        fig.text(0.07, y, title, fontsize=8)
        fig.text(0.27, y, prow, fontsize=7.5, color="0.3")
        fig.text(0.52, y, f"z {zp:+.1f}" if zp is not None else "n/a", fontsize=8)
        fig.text(0.62, y, f"z {ze:+.1f}" if ze is not None else "n/a", fontsize=8)
        fig.text(0.78, y, word, fontsize=8, weight="bold", color=col)
        if feat == "paf_post" and vals[row] is not None and sm.get(feat) is not None:
            y -= 0.014
            fig.text(0.27, y, f"panel {vals[row]:.1f} Hz, EDF {sm[feat]:.1f} Hz", fontsize=6.5,
                     color="0.4")
        readings.append((title, word))
        y -= 0.02
    notes = []
    young = age is not None and age < 18
    for title, word in readings:
        if word == "panel only" and young:
            notes.append(f"{title}: flagged by the panel only. The panel compares with an adult "
                         "reference; at this age the EDF's age-adjusted value is the better guide.")
        elif word == "panel only":
            notes.append(f"{title}: flagged by the panel only -- the panel row and the EDF measure "
                         "overlap only partly; read the panel row on its own terms.")
        elif word == "EDF only":
            notes.append(f"{title}: unusual for age in the EDF but not on the panel.")
        elif word.startswith(("both high", "both low")):
            notes.append(f"{title}: both analyses point {word.split()[1]} "
                         f"{'(one borderline) ' if 'borderline' in word else ''}"
                         "-- two analyses of this recording agree.")
        elif word == "CONFLICT":
            notes.append(f"{title}: the two disagree in direction -- check recording quality and "
                         "condition before relying on either.")
    if cond == "EO":
        notes.append("Eyes-open study: the panel's reference is eyes-closed, so the panel's PDR and "
                     "alpha rows are expected to read low.")
    y -= 0.006
    for n_ in notes:
        for k, ln in enumerate(_wrap(n_, 118).split("\n")):
            fig.text(0.07 if k == 0 else 0.082, y, ("\u2022 " if k == 0 else "") + ln, fontsize=7.5)
            y -= 0.015
    y -= 0.03

    # --- discriminant likelihoods: --internal only. They read High on about half of all reports,
    # often against the cover, and did not track the doctor's comments here (AUC 0.33-0.55).
    if internal:
        fig.text(0.06, y, "Panel discriminant likelihoods (Collura et al. 2026)", fontsize=10,
                 weight="bold")
        y -= 0.024
        for d in compute_scores(compute_oob_counts(np.nan_to_num(z, nan=0.0))):
            fig.text(0.07, y, d["name"], fontsize=8)
            fig.text(0.30, y, f"score {d['score']}", fontsize=8)
            fig.text(0.40, y, d["label"], fontsize=8, weight="bold", color=d["color"])
            qa = DISC_QA_AUC.get(d["name"])
            if qa is not None:
                fig.text(0.62, y, f"QA corpus AUC vs doctor: {qa:.2f}", fontsize=7, color="0.4")
            y -= 0.017
        for k, ln in enumerate(_wrap(
                "Published sensitivities/specificities come from the paper's cohort. Applied unchanged "
                "to the STS QA corpus (tools/panel_crosscheck.py), the discriminant scores did not track "
                "the matched doctor's comments (AUC 0.33-0.55, 0.5 = chance); a model of the 48 panel "
                "rows fitted to those comments reached 0.76 for PDR slowing and 0.58 for drowsiness. "
                "Read the likelihoods as pattern summaries, not diagnostic probabilities.", 140).split("\n")):
            fig.text(0.07, y - 0.006 - 0.012 * k, ln, fontsize=6.8, color="0.35")
    fig.text(0.06, 0.035, _wrap(
        "Panel values are read from the Brain Panel report; nothing is recomputed. EDF values "
        "are age-by-condition z from our EEG screening database (a screening population, not norms). "
        "Screening information for a qualified practitioner; not a diagnosis.", 150),
        fontsize=6, color="0.35", va="bottom")
    stamp(fig)
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
    ap.add_argument("--internal", action="store_true",
                    help="add the panel discriminant likelihoods to the cross-check page")
    ap.add_argument("--summary", help="also write what the cover said as JSON")
    ap.add_argument("--models", default=report_models.DEFAULT_PATH)
    ap.add_argument("--refit", action="store_true",
                    help="score from the source database, leaving this client out")
    ap.add_argument("--panel", help="production .icale.rep.pdf (default: next to the EDF)")
    a = ap.parse_args()

    base = os.path.basename(a.edf)[:-4]
    g_age, g_cond = guess_age_cond(base)
    age = a.age if a.age is not None else g_age
    cond = a.cond or g_cond
    notes = []
    if cond is None:
        cond = "EC"
        notes.append("Condition not in the file name: scored against the eyes-closed reference.")
    global MODEL_STAMP
    bundle = None
    if a.refit:
        models = load_models(a.store, cond)
        MODEL_STAMP = "Reference models: refit from the database, client left out"
    else:
        bundle = report_models.load(a.models)
        models = bundle["reference"][cond]
        MODEL_STAMP = "Reference models " + bundle["version"]
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
    # everything the cover summarizes is computed before the first page is written
    panel = find_panel(a.edf, a.panel)
    if not panel:
        print("no Brain Panel found -- cross-check page skipped")
    ss = data = typ = net = ctyp = None
    if os.path.exists(sidecar):
        import source_summary as ss
        data = ss.load(sidecar)
        try:
            import source_norms
            typ = (source_norms.typicality(data["comps"], age, cond, frozen=bundle["source"][cond]) if bundle
                   else source_norms.typicality(data["comps"], age, cond, a.store, client=patient_hash(a.edf)))
        except Exception as exc:      # no database / no reference: page without peers
            print("source typicality unavailable:", exc)
        if data["sources"] is not None:
            net = ss.analyze_networks(data)
            try:
                import coupling_norms
                ctyp = (coupling_norms.coupling_typicality(*net, age, cond, frozen=bundle["coupling"][cond]) if bundle
                        else coupling_norms.coupling_typicality(*net, age, cond, a.store,
                                                                client=patient_hash(a.edf)))
            except Exception as exc:  # no database / no reference: page without norms
                print("coupling norms unavailable:", exc)
    brain = brain_share(data)
    if brain is not None and brain < BRAIN_MIN:     # too little left to compare, or to read as networks
        typ = net = ctyp = None
    stats = tuple(bundle["group_stats"][cond]) if bundle else group_stats(a.store, cond)
    drowsy = None
    try:
        import drowsiness_model
        drowsy = (drowsiness_model.drowsy_note(a.edf, age, cond, cp, frozen=bundle["drowsiness"]) if bundle
                  else drowsiness_model.drowsy_note(a.edf, age, cond, cp, a.store, client=patient_hash(a.edf)))
    except Exception as exc:          # no database / no reference: cover without the note
        print("drowsiness note unavailable:", exc)
    contents = ["EEG measures"] + (["Brain Panel"] if panel else []) + (["brain sources"] if data else []) \
        + (["brain networks"] if net else [])
    contents = [(k + 2, t) for k, t in enumerate(contents)]

    with PdfPages(out) as pdf:
        label = deidentify_label(base)
        page_cover(pdf, label, age, cond, rec, cp, models, notes, panel, data, typ, ctyp, stats, contents, drowsy)
        page_edf(pdf, label, age, cond, rec, cp, models, notes)
        if panel:
            page_panel(pdf, label, age, cond, panel, cp, models, a.internal)
        if data is not None:
            ss.page_sources(data, pdf, typ)
            if net is not None:
                ss.page_networks(data, pdf, net, ctyp)
    if a.summary:
        with open(a.summary, "w", encoding="utf-8") as fh:
            json.dump(SUMMARY, fh, indent=1, default=float)
    print("wrote", out)


if __name__ == "__main__":
    main()
