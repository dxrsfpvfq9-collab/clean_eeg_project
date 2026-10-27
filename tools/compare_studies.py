"""Compare two Brain Panel studies of one client -> one comparison PDF.

READ ONLY with respect to the pipeline: it reads the rendered `.icale.rep.pdf`
panels, the `.imagecascade.pdf` cascades when present, and (EC/EO mode) the
EDFs. Nothing is recomputed through the pipeline and no metric changes.

Usage:
    py tools/compare_studies.py prepost "<study A>" "<study B>" [--out X.pdf]
    py tools/compare_studies.py eceo    "<EC study>" "<EO study>" [--out X.pdf]

A study may be named by its .edf, .icale.rep.pdf or .imagecascade.pdf; the
other files are found next to it by base name. Pre/post orders A/B by EDF
recording time when both EDFs are present.

prepost -- row-by-row z change on all 48 metrics, out-of-range counts per
    group, the six discriminant scores before/after, the panel's own
    plain-English sentences for rows that resolved or newly went out of range,
    and the cascade component make-up before/after.

eceo -- alpha blocking (reactivity) on eye opening. The index comes from the
    EDFs, NOT from the panel: the panel's alpha rows are built from
    `detect_band_with_rms`, which returns abs(|alpha| - fixed threshold) on a
    signal already rescaled by 10/stdmeas, so they are neither absolute nor
    proportional to alpha amplitude and an EO/EC ratio of them is not a
    reactivity percentage. They are shown for context only. Z-scores are not
    used at all in this mode: EC_191 is an eyes-closed database.

Default output: next to study B, `<B base>.prepost.pdf` / `.eceo.pdf`.
"""
import ast
import io
import os
import re
import sys
import argparse
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "research", "validation_2026"))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import welch
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader, simpleSplit

from panel_parser import parse_panel_pdf, NAME_STRINGS
from cascade_extract import extract_pdf as extract_cascade_rows
from process.discriminant import GROUP_INDEXES, OOB_Z, compute_oob_counts, compute_scores
from files.deidentify import panel_label

W, H = letter
M = 36                      # page margin, points
NOTABLE = 1.0               # |delta |z|| shown as a notable move (display convention, not validated)
GSTD_ROW = 1                # Global STD: reads 1000 on panels issued before the 2026-10-08 fix

GROUP_TITLE = {"std_global": "Std / Global", "pdr": "PDR", "phenotypes": "Phenotypes",
               "focal": "Focal / Frontal", "diffuse": "Diffuse", "state_shift": "State Shift"}
GROUP_ORDER = ["std_global", "pdr", "phenotypes", "focal", "diffuse", "state_shift"]

ALPHA_HZ = (7.5, 13.0)
THETA_HZ = (4.0, 7.5)
PEAK_PROM = 2.0             # alpha peak must be >= 2x the 4-6/14-18 Hz flank power to count
POSTERIOR = {"O1", "O2", "OZ", "P3", "P4", "PZ", "T5", "T6"}
LEFT = {"FP1", "F7", "F3", "T3", "C3", "T5", "P3", "O1"}
RIGHT = {"FP2", "F8", "F4", "T4", "C4", "T6", "P4", "O2"}

# Panel rows shown for context in EC/EO mode (indices into NAME_STRINGS).
# Panel rows whose EC->EO change tracks EDF alpha blocking, with the direction
# they move when alpha blocks and Spearman rho vs log(EO/EC alpha power), from
# 147 same-session QA pairs (research/validation_2026/eceo_pdr_validation.py).
# Every other row, PDR Max Amplitude / Max Post. / Sinusoidal / Symmetry /
# Alpha Speed / Alpha Peak included, had |rho| <= 0.14 and is not shown.
BLOCKING_ROWS = [  # (row, direction on blocking, |rho|)
    (10, "falls", 0.39),   # PDR Burst Width
    (35, "rises", 0.33),   # Fractal Dimension
    (5, "falls", 0.22),    # PDR Magnitude (PDR Moment 1 prints the same value: identical in all 294 QA recordings)
    (3, "rises", 0.22),    # PDR Synchrony
]
LOW_AGREE = 1          # <= this many rows agreeing: worth a second look (see eceo panel text)

GREEN = (0.0, 0.5, 0.0)
RED = (0.8, 0.0, 0.0)
GREY = (0.45, 0.45, 0.45)


# ---------------------------------------------------------------- loading

def _panel_sentences():
    """The panel's own high/low sentences, read from create_report_pdf.py.

    They live as locals inside create_report_pdf(), so they are read from the
    source instead of copied here -- one copy, no drift.
    """
    src = open(os.path.join(ROOT, "files", "create_report_pdf.py"), encoding="utf-8").read()
    found = {}
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id in ("high_sentences", "low_sentences"):
                found[t.id] = ast.literal_eval(node.value)
    high, low = found.get("high_sentences", []), found.get("low_sentences", [])
    if len(high) < 48 or len(low) < 48:
        return None, None
    return high[:48], low[:48]


def study_base(path):
    p = os.path.abspath(path)
    for suf in (".icale.disc.rep.pdf", ".icale.rep.pdf", ".imagecascade.pdf", ".edf"):
        if p.lower().endswith(suf):
            return p[:-len(suf)]
    return p


def guess_condition(base):
    toks = re.findall(r"\b(ec|eo)\b", os.path.basename(base).lower())
    return toks[-1].upper() if toks else "?"


def edf_start(edf_path):
    """Recording start from the EDF header (bytes 168-184). Header only --
    the patient fields are never read."""
    if not os.path.exists(edf_path):
        return None
    with open(edf_path, "rb") as fh:
        h = fh.read(256)
    try:
        d, mo, y = (int(x) for x in h[168:176].decode("ascii").split("."))
        hh, mi, ss = (int(x) for x in h[176:184].decode("ascii").split("."))
        return datetime.datetime(1900 + y if y >= 85 else 2000 + y, mo, d, hh, mi, ss)
    except ValueError:
        return None


def _comp(row):
    def num(s):
        m = re.match(r"[-+]?\d+(?:\.\d+)?", (s or "").strip())
        return float(m.group()) if m else float("nan")
    return {"no": int(row["comp_no"]), "pct": num(row["pct"]), "peak": num(row["fft_peak"]),
            "site": (row["max_site"] or "").upper(), "accept": row["machine"].strip() == "Accept",
            "region": row["region"], "area": row["area"], "line": "line" in row["fft_peak"]}


def load_study(path):
    base = study_base(path)
    st = {"base": base, "label": panel_label(os.path.basename(base), width=48),
          "cond": guess_condition(base), "recorded": edf_start(base + ".edf"),
          "edf": base + ".edf" if os.path.exists(base + ".edf") else None}
    panel = base + ".icale.rep.pdf"
    if not os.path.exists(panel):
        sys.exit(f"No panel PDF for study '{st['label']}'")
    r = parse_panel_pdf(panel)
    if not r["valid"]:
        sys.exit(f"Panel for '{st['label']}' did not parse ({r['n_parsed']}/48 rows)")
    st.update(z=np.array(r["zscores"], dtype=float), values=np.array(r["values"], dtype=float),
              version=r["version"], report_date=r["report_date"])
    st["gstd_prefix"] = st["values"][GSTD_ROW] >= 999.0
    st["comps"] = None
    casc = base + ".imagecascade.pdf"
    if os.path.exists(casc):
        rows, _err = extract_cascade_rows(casc, os.path.dirname(casc))
        if rows:
            st["comps"] = [_comp(r) for r in rows]
    return st


# ---------------------------------------------------------------- cascade

def cascade_summary(comps):
    acc = [c for c in comps if c["accept"]]
    tot = sum(c["pct"] for c in comps)
    acc_tot = sum(c["pct"] for c in acc)
    alpha = [c for c in acc if ALPHA_HZ[0] <= c["peak"] < ALPHA_HZ[1]]
    theta = [c for c in acc if THETA_HZ[0] <= c["peak"] < THETA_HZ[1]]
    a_pct = sum(c["pct"] for c in alpha)
    a_left = sum(c["pct"] for c in alpha if c["site"] in LEFT)
    a_right = sum(c["pct"] for c in alpha if c["site"] in RIGHT)
    top = max(alpha, key=lambda c: c["pct"]) if alpha else None
    return {
        "n": len(comps), "n_rej": len(comps) - len(acc), "rej_pct": tot - acc_tot,
        "n_alpha": len(alpha), "alpha_pct": a_pct,
        # share of the ACCEPTED (brain) variance -- removes the dilution that
        # EO blink components cause in the raw % column
        "alpha_share": 100.0 * a_pct / acc_tot if acc_tot else float("nan"),
        "alpha_post": sum(c["pct"] for c in alpha if c["site"] in POSTERIOR),
        "alpha_lr": (a_left, a_right),
        "theta_pct": sum(c["pct"] for c in theta),
        "line_pct": sum(c["pct"] for c in comps if c["line"]),
        "top_alpha": top,
    }


CASCADE_ROWS = [
    ("Components (machine-rejected)", lambda s: f"{s['n']} ({s['n_rej']})"),
    ("Variance in rejected comps", lambda s: f"{s['rej_pct']:.1f}%"),
    ("Alpha components (accepted)", lambda s: f"{s['n_alpha']}"),
    ("Alpha variance, raw %", lambda s: f"{s['alpha_pct']:.1f}%"),
    ("Alpha share of brain variance", lambda s: f"{s['alpha_share']:.1f}%"),
    ("  of which posterior max", lambda s: f"{s['alpha_post']:.1f}%"),
    ("  left / right max site", lambda s: f"{s['alpha_lr'][0]:.1f} / {s['alpha_lr'][1]:.1f}%"),
    ("Largest alpha comp", lambda s: (f"{s['top_alpha']['pct']:.1f}% {s['top_alpha']['site']} "
                                      f"{s['top_alpha']['peak']:.1f} Hz") if s["top_alpha"] else "none"),
    ("  its region", lambda s: (f"{s['top_alpha']['region']} BA {s['top_alpha']['area']}"
                                if s["top_alpha"] else "")),
    ("Theta components, %", lambda s: f"{s['theta_pct']:.1f}%"),
    ("Mains (60 Hz) components, %", lambda s: f"{s['line_pct']:.1f}%"),
]


def component_spectrum_png(studies, titles):
    """Each component as a stem at its FFT peak, height = % variance."""
    fig, axes = plt.subplots(len(studies), 1, figsize=(7.2, 1.55 * len(studies)), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, st, title in zip(axes, studies, titles):
        ax.axvspan(*ALPHA_HZ, color="#e8f0ff", zorder=0)
        for c in st["comps"]:
            x = min(c["peak"], 34.5)
            col = "#1f5fbf" if c["accept"] else "#999999"
            ax.vlines(x, 0, c["pct"], color=col, lw=2.2)
            ax.plot(x, c["pct"], "o" if c["accept"] else "x", color=col, ms=3.5)
        ax.set_xlim(0, 35)
        ax.set_ylabel("% var", fontsize=7)
        ax.tick_params(labelsize=7)
        ax.text(0.99, 0.88, title, transform=ax.transAxes, ha="right", fontsize=7.5, weight="bold")
    axes[-1].set_xlabel("component FFT peak (Hz)   [blue = accepted, grey x = machine-rejected; "
                        "shaded = alpha; >35 Hz drawn at the edge]", fontsize=7)
    fig.tight_layout(pad=0.4)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170)
    plt.close(fig)
    buf.seek(0)
    return ImageReader(buf)


# ---------------------------------------------------------------- drawing helpers

def text(c, x, y, s, size=8, bold=False, color=(0, 0, 0), right=False):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.setFillColorRGB(*color)
    (c.drawRightString if right else c.drawString)(x, y, s)
    c.setFillColorRGB(0, 0, 0)


def para(c, x, y, s, width, size=8, lead=None, color=(0, 0, 0), bold=False):
    lead = lead or size * 1.25
    for line in simpleSplit(s, "Helvetica-Bold" if bold else "Helvetica", size, width):
        text(c, x, y, line, size, bold, color)
        y -= lead
    return y


def header(c, title, sub):
    text(c, M, H - 34, title, 14, bold=True)
    text(c, M, H - 47, sub, 8, color=GREY)
    c.setLineWidth(0.6)
    c.line(M, H - 52, W - M, H - 52)


def footer(c, page):
    text(c, M, 20, "BrainML Brain Panel comparison (prototype) - not a diagnostic report; "
                   "review with the source panels.", 6.5, color=GREY)
    text(c, W - M, 20, f"page {page}", 6.5, color=GREY, right=True)


def study_lines(c, y, studies, tags):
    for st, tag in zip(studies, tags):
        rec = st["recorded"].strftime("%Y-%m-%d %H:%M") if st["recorded"] else "recording time n/a (no EDF)"
        text(c, M, y, f"{tag}:", 8.5, bold=True)
        text(c, M + 62, y, f"{st['label']}    recorded {rec}    condition {st['cond']}    "
                           f"panel {st['version']}    cascade {'yes' if st['comps'] else 'no'}", 8)
        y -= 12
    return y


def warnings_block(c, y, warns):
    for w_ in warns:
        y = para(c, M, y, "! " + w_, W - 2 * M, 7.8, color=RED)
    return y - 4


def zbar(c, x0, x1, y, za, zb, col):
    """-3..3 strip; light band = typical (|z|<2); A hollow, B filled."""
    def X(z):
        return x0 + (np.clip(z, -3.2, 3.2) + 3.2) / 6.4 * (x1 - x0)
    c.setFillColorRGB(0.92, 0.96, 0.92)
    c.rect(X(-OOB_Z), y - 1.5, X(OOB_Z) - X(-OOB_Z), 7, stroke=0, fill=1)
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(0.4)
    c.rect(x0, y - 1.5, x1 - x0, 7, stroke=1, fill=0)
    c.line(X(0), y - 1.5, X(0), y + 5.5)
    if np.isnan(za) or np.isnan(zb):
        c.setStrokeColorRGB(0, 0, 0)
        return
    c.setStrokeColorRGB(*col)
    c.setLineWidth(1.1)
    c.line(X(za), y + 2, X(zb), y + 2)
    c.setLineWidth(0.8)
    c.circle(X(za), y + 2, 2.3, stroke=1, fill=0)
    c.setFillColorRGB(*col)
    c.circle(X(zb), y + 2, 2.3, stroke=0, fill=1)
    c.setFillColorRGB(0, 0, 0)
    c.setStrokeColorRGB(0, 0, 0)


# ---------------------------------------------------------------- pre/post

def classify(za, zb):
    if np.isnan(za) or np.isnan(zb):
        return "n/a", GREY
    oa, ob = abs(za) >= OOB_Z, abs(zb) >= OOB_Z
    if oa and ob and np.sign(za) != np.sign(zb):
        return "Flipped", RED
    if oa and not ob:
        return "Resolved", GREEN
    if ob and not oa:
        return "New", RED
    d = abs(zb) - abs(za)
    if d <= -NOTABLE:
        return "Closer", GREEN
    if d >= NOTABLE:
        return "Further", RED
    return "", GREY


def prepost(a, b, out):
    if a["recorded"] and b["recorded"] and b["recorded"] < a["recorded"]:
        a, b = b, a
    za, zb = a["z"].copy(), b["z"].copy()
    warns = []
    if a["gstd_prefix"] or b["gstd_prefix"]:
        za[GSTD_ROW] = zb[GSTD_ROW] = np.nan
        warns.append("Global STD reads 1000 on a panel issued before the 2026-10-08 fix; that row is "
                     "left out of every comparison below.")
    if a["version"] != b["version"]:
        warns.append(f"Panels come from different report versions ({a['version']} vs {b['version']}); "
                     "z-scores may not be on the same footing.")
    if a["cond"] != b["cond"]:
        warns.append(f"Conditions differ ({a['cond']} vs {b['cond']}). Pre/post should compare like "
                     "with like; use 'eceo' mode for an EC/EO pair.")
    same = np.nanmax(np.abs(np.delete(a["values"] - b["values"], GSTD_ROW))) < 1e-9
    if same:
        warns.append("Every metric value is identical: these look like the SAME recording processed "
                     "twice, not two sessions.")
    if a["cond"] == "EO" or b["cond"] == "EO":
        warns.append("Z-scores are against EC_191, an eyes-closed database; on an EO study they mostly "
                     "measure the eyes-open state, not the client.")
    if a["recorded"] and b["recorded"]:
        days = (b["recorded"] - a["recorded"]).total_seconds() / 86400.0
        interval = f"{days:.0f} days" if days >= 1 else f"{days * 24 * 60:.0f} minutes"
    else:
        interval = "unknown (order as given)"

    status = [classify(za[i], zb[i]) for i in range(48)]
    ca, cb = compute_oob_counts(np.nan_to_num(za)), compute_oob_counts(np.nan_to_num(zb))
    sa, sb = compute_scores(ca), compute_scores(cb)

    c = canvas.Canvas(out, pagesize=letter)
    # ---- page 1: summary
    header(c, "Brain Panel Change Report (pre / post)",
           f"Two panels of one client compared row by row. Z-scores vs EC_191 (192 files). Interval: {interval}.")
    y = study_lines(c, H - 68, [a, b], ["A  before", "B  after"])
    y = warnings_block(c, y - 4, warns)

    tally = {k: sum(1 for s, _ in status if s == k) for k in ("Resolved", "New", "Closer", "Further", "Flipped")}
    text(c, M, y, "Out-of-range rows (|z| >= 2)", 10, bold=True)
    text(c, M + 210, y, f"A {ca['total']}   ->   B {cb['total']}", 10, bold=True,
         color=GREEN if cb["total"] < ca["total"] else RED if cb["total"] > ca["total"] else (0, 0, 0))
    y -= 13
    text(c, M, y, f"Resolved {tally['Resolved']}    newly out {tally['New']}    "
                  f"moved closer {tally['Closer']}    moved further {tally['Further']}    "
                  f"flipped sign {tally['Flipped']}      (closer/further = |z| changed by >= {NOTABLE:g})", 8)
    y -= 18
    cols = [M, M + 120, M + 175, M + 230]
    for x, h_ in zip(cols, ["Group", "rows", "OOB A", "OOB B"]):
        text(c, x, y, h_, 8, bold=True)
    y -= 11
    for g in GROUP_ORDER:
        text(c, cols[0], y, GROUP_TITLE[g], 8)
        text(c, cols[1], y, str(len(GROUP_INDEXES[g])), 8)
        text(c, cols[2], y, str(ca[g]), 8)
        text(c, cols[3], y, str(cb[g]), 8,
             color=GREEN if cb[g] < ca[g] else RED if cb[g] > ca[g] else (0, 0, 0))
        y -= 10.5
    y -= 10
    text(c, M, y, "Likelihood of findings (discriminant scores, Collura et al. 2026)", 10, bold=True)
    y -= 13
    cols = [M, M + 130, M + 300]
    for x, h_ in zip(cols, ["Category", "A  score  band", "B  score  band"]):
        text(c, x, y, h_, 8, bold=True)
    y -= 11
    for da, db in zip(sa, sb):
        text(c, cols[0], y, da["name"], 8)
        text(c, cols[1], y, f"{da['score']:>3}   {da['label']}", 8, color=da["color"])
        text(c, cols[2], y, f"{db['score']:>3}   {db['label']}", 8, color=db["color"])
        y -= 10.5
    y -= 12
    if a["comps"] and b["comps"]:
        text(c, M, y, "Image cascade: ICA components before / after", 10, bold=True)
        img = component_spectrum_png([a, b], ["A  before", "B  after"])
        iw, ih = img.getSize()
        dw = W - 2 * M
        dh = dw * ih / iw
        c.drawImage(img, M, y - 6 - dh, dw, dh)
    else:
        para(c, M, y, "Image cascade comparison skipped: a cascade PDF is missing for "
                      + ("both studies." if not (a["comps"] or b["comps"]) else "one study."), W - 2 * M, 8, color=GREY)
    footer(c, 1)
    c.showPage()

    # ---- page 2: all 48 rows
    header(c, "All 48 metrics, A -> B",
           "Hollow dot = A, filled = B, shaded band = typical range |z| < 2, strip spans z -3..+3 (clipped).")
    y = H - 72
    xs = dict(name=M, za=M + 150, zb=M + 190, bar0=M + 205, bar1=M + 405, st=M + 418, d=M + 470)
    for k, h_ in [("name", "Metric"), ("za", "z A"), ("zb", "z B"), ("st", "Change"), ("d", "|z| B-A")]:
        text(c, xs[k], y, h_, 7.5, bold=True, right=k in ("za", "zb"))
    y -= 12
    for g in GROUP_ORDER:
        text(c, M, y, GROUP_TITLE[g], 8, bold=True, color=(0.2, 0.2, 0.5))
        y -= 11
        for i in GROUP_INDEXES[g]:
            s, col = status[i]
            text(c, xs["name"] + 6, y, NAME_STRINGS[i], 7.5)
            for k, z in (("za", za[i]), ("zb", zb[i])):
                text(c, xs[k], y, "n/a" if np.isnan(z) else f"{z:+.2f}", 7.5, right=True,
                     color=RED if abs(z) >= OOB_Z else (0, 0, 0))
            zbar(c, xs["bar0"], xs["bar1"], y, za[i], zb[i], col if s else GREY)
            text(c, xs["st"], y, s, 7.5, bold=bool(s), color=col)
            if not (np.isnan(za[i]) or np.isnan(zb[i])):
                text(c, xs["d"], y, f"{abs(zb[i]) - abs(za[i]):+.2f}", 7.5)
            y -= 11.6
    footer(c, 2)
    c.showPage()

    # ---- page 3: plain English + cascade table
    header(c, "What changed, in plain English",
           "Sentences are the panel's own page-2 wording for the state each row was or is in.")
    high, low = _panel_sentences()
    y = H - 72

    def sentence(i, z):
        if high is None:
            return ""
        return (high if z > 0 else low)[i]

    sections = [
        ("Resolved - was out of range, now within it", "Resolved", GREEN, lambda i: ("was: ", za[i])),
        ("Newly out of range", "New", RED, lambda i: ("now: ", zb[i])),
        ("Flipped - out of range on the opposite side", "Flipped", RED, lambda i: ("now: ", zb[i])),
    ]
    for title, key, col, pick in sections:
        rows = [i for i in range(48) if status[i][0] == key]
        if not rows:
            continue
        text(c, M, y, f"{title} ({len(rows)})", 9.5, bold=True, color=col)
        y -= 12
        for i in rows:
            pre, z = pick(i)
            y = para(c, M + 8, y, f"{NAME_STRINGS[i]} (z {za[i]:+.2f} -> {zb[i]:+.2f}) - {pre}"
                                  f"{sentence(i, z)}", W - 2 * M - 8, 7.6)
            y -= 2
        y -= 6
    still = [i for i in range(48) if not np.isnan(za[i]) and abs(za[i]) >= OOB_Z and abs(zb[i]) >= OOB_Z
             and status[i][0] != "Flipped"]
    if still:
        text(c, M, y, f"Still out of range ({len(still)})", 9.5, bold=True)
        y -= 12
        y = para(c, M + 8, y, ";  ".join(f"{NAME_STRINGS[i]} {za[i]:+.1f} -> {zb[i]:+.1f}" for i in still),
                 W - 2 * M - 8, 7.6)
        y -= 8
    if not any(status[i][0] in ("Resolved", "New", "Flipped") for i in range(48)) and not still:
        y = para(c, M, y, "No row is out of range in either study.", W - 2 * M, 8)

    if a["comps"] and b["comps"] and y > 200:
        y -= 6
        text(c, M, y, "Image cascade make-up", 9.5, bold=True)
        y -= 12
        A, B = cascade_summary(a["comps"]), cascade_summary(b["comps"])
        for label_, fn in CASCADE_ROWS:
            text(c, M + 8, y, label_, 7.8)
            text(c, M + 190, y, fn(A), 7.8)
            text(c, M + 350, y, fn(B), 7.8)
            y -= 10.5
        y -= 4
        y = para(c, M, y, "Cascade % is each component's share of that recording's variance, so it is "
                          "relative within a study. Components are renumbered by size in every cascade, "
                          "so component numbers do not correspond between A and B.", W - 2 * M, 7, color=GREY)
    y -= 8
    para(c, M, y, f"Reading guide: 'closer'/'further' use |delta |z|| >= {NOTABLE:g} as a display convention. "
                  "The panel's test-retest variability has not been measured, so a single-row change of "
                  "about one z is not by itself evidence of a real change; look for consistent movement "
                  "across a group, and in the out-of-range counts.", W - 2 * M, 7, color=GREY)
    footer(c, 3)
    c.save()
    return a, b


# ---------------------------------------------------------------- EC / EO

def _site(label):
    s = re.sub(r"^(EEG|EXG)\s*", "", label.strip(), flags=re.I)
    return re.split(r"[-_ ]", s)[0].upper()


def edf_posterior_spectra(edf):
    from epoch_reject_report import read_edf
    sigs, labels, fs = read_edf(edf, 64)
    sites = [_site(l) for l in labels]
    out = {}
    for name in ("O1", "O2", "P3", "P4"):
        if name in sites:
            x = sigs[sites.index(name)]
            # median Welch: robust to the blinks/movement bursts EO brings
            f, p = welch(x - x.mean(), fs=fs, nperseg=int(4 * fs), average="median")
            out[name] = (f, p)
    return out


def _band_power(f, p, lo, hi):
    m = (f >= lo) & (f <= hi)
    trap = getattr(np, "trapezoid", None) or np.trapz   # numpy < 2.0 on the servers
    return float(trap(p[m], f[m])) if m.any() else float("nan")


def reactivity_label(r):
    if np.isnan(r):
        return "n/a", GREY
    if r >= 50:
        return "robust blocking", GREEN
    if r >= 25:
        return "partial blocking", (0.75, 0.45, 0.0)
    if r >= 0:
        return "weak blocking", RED
    return "no blocking (alpha higher EO)", RED


def edf_reactivity(ec_edf, eo_edf):
    """Posterior alpha blocking from two EDFs.

    Returns spec/have (for plotting), band, paf / eo_paf (NaN = no clear
    peak), all/left/right = (EC power, EO power, attenuation %) and rel =
    alpha share of 1-30 Hz per condition.
    """
    spec = {"EC": edf_posterior_spectra(ec_edf) if ec_edf else {},
            "EO": edf_posterior_spectra(eo_edf) if eo_edf else {}}
    have = [s for s in ("O1", "O2", "P3", "P4") if s in spec["EC"] and s in spec["EO"]]

    def peak(tag):
        """Posterior alpha peak, or NaN when there is no real peak: the
        7-13 Hz maximum must stand >= PEAK_PROM x above the 4-6 / 14-18 Hz
        flanks. Without this a blocked EO spectrum 'peaks' on noise."""
        if not have:
            return float("nan")
        f = spec[tag][have[0]][0]
        pm = np.mean([spec[tag][s][1] for s in have], axis=0)
        m = (f >= 7.0) & (f <= 13.0)
        flank = np.mean(pm[((f >= 4) & (f <= 6)) | ((f >= 14) & (f <= 18))])
        if pm[m].max() < PEAK_PROM * flank:
            return float("nan")
        return float(f[m][np.argmax(pm[m])])

    # Individual alpha band: EC posterior peak +/- 2 Hz (fallback 8-12)
    paf, eo_paf = peak("EC"), peak("EO")
    band = (paf - 2.0, paf + 2.0) if not np.isnan(paf) else (8.0, 12.0)

    def react(sites):
        s = [x for x in sites if x in have]
        if not s:
            return float("nan"), float("nan"), float("nan")
        pec = np.mean([_band_power(*spec["EC"][x], *band) for x in s])
        peo = np.mean([_band_power(*spec["EO"][x], *band) for x in s])
        return pec, peo, 100.0 * (pec - peo) / pec

    # relative alpha (alpha / 1-30 Hz) -- the blocking that survives an overall amplitude change
    rel = {}
    for tag in ("EC", "EO"):
        vals = [_band_power(*spec[tag][x], *band) / _band_power(*spec[tag][x], 1.0, 30.0) for x in have]
        rel[tag] = 100.0 * float(np.mean(vals)) if vals else float("nan")
    return {"spec": spec, "have": have, "band": band, "paf": paf, "eo_paf": eo_paf, "rel": rel,
            "all": react(["O1", "O2", "P3", "P4"]), "left": react(["O1", "P3"]),
            "right": react(["O2", "P4"])}


def eceo(ec, eo, out):
    warns = []
    if ec["cond"] == "EO" or eo["cond"] == "EC":
        warns.append(f"File names read {ec['cond']} for the first study and {eo['cond']} for the second; "
                     "this mode expects EC first, EO second.")
    if np.nanmax(np.abs(np.delete(ec["values"] - eo["values"], GSTD_ROW))) < 1e-9:
        warns.append("Every panel value is identical: these look like the same recording twice.")
    if ec["recorded"] and eo["recorded"]:
        gap = abs((eo["recorded"] - ec["recorded"]).total_seconds()) / 60.0
        if gap > 120:
            warns.append(f"Recordings are {gap / 60:.0f} h apart; reactivity is best read from the same session.")

    r = edf_reactivity(ec["edf"], eo["edf"])
    spec, have, band, paf, eo_paf, rel = r["spec"], r["have"], r["band"], r["paf"], r["eo_paf"], r["rel"]
    allr, left, right = r["all"], r["left"], r["right"]
    if not have:
        warns.append("No EDF (or no posterior channels) for one study: the EDF-based blocking index is "
                     "unavailable; only panel context and cascade are shown.")

    def hz(v):
        return "not measurable" if np.isnan(v) else f"{v:.2f} Hz"

    c = canvas.Canvas(out, pagesize=letter)
    header(c, "Alpha Blocking and Reactivity (EC vs EO)",
           "How much the posterior dominant rhythm attenuates when the eyes open. Same client, same session.")
    y = study_lines(c, H - 68, [ec, eo], ["EC", "EO"])
    y = warnings_block(c, y - 4, warns)

    lab, col = reactivity_label(allr[2])
    text(c, M, y, "Alpha blocking:", 13, bold=True)
    text(c, M + 112, y, f"{lab.upper()}" + ("" if np.isnan(allr[2]) else f"   ({allr[2]:.0f}% attenuation)"),
         13, bold=True, color=col)
    y -= 16
    y = para(c, M, y, f"Posterior (O1 O2 P3 P4) alpha power, band {band[0]:.1f}-{band[1]:.1f} Hz "
                      + ("(EC peak +/- 2 Hz)" if not np.isnan(paf) else "(fixed: no clear EC peak)")
                      + ", read from the EDFs in microvolts. Guide: >= 50% robust, 25-50% "
                      "partial, < 25% weak. These are conventional reading bands, not validated cut-offs.",
             W - 2 * M, 7.6, color=GREY)
    y -= 6
    cols = [M, M + 120, M + 200, M + 280, M + 350]
    for x, h_ in zip(cols, ["", "EC uV^2", "EO uV^2", "attenuation", "reading"]):
        text(c, x, y, h_, 8, bold=True)
    y -= 11
    for name, r in (("Posterior (all 4)", allr), ("Left  (O1 P3)", left), ("Right (O2 P4)", right)):
        l_, cl = reactivity_label(r[2])
        text(c, cols[0], y, name, 8)
        text(c, cols[1], y, "n/a" if np.isnan(r[0]) else f"{r[0]:.1f}", 8)
        text(c, cols[2], y, "n/a" if np.isnan(r[1]) else f"{r[1]:.1f}", 8)
        text(c, cols[3], y, "n/a" if np.isnan(r[2]) else f"{r[2]:.0f}%", 8, color=cl)
        text(c, cols[4], y, l_, 8, color=cl)
        y -= 10.5
    if not (np.isnan(left[2]) or np.isnan(right[2])):
        d = left[2] - right[2]
        lr = (f"Left/right reactivity differ by {abs(d):.0f} points ("
              f"{'left' if d < 0 else 'right'} blocks less)") if abs(d) >= 20 else \
             f"Left and right block alike (difference {abs(d):.0f} points)."
        text(c, M, y, lr, 8, bold=abs(d) >= 20, color=RED if abs(d) >= 20 else (0, 0, 0))
        y -= 10.5
    text(c, M, y, f"Relative alpha (share of 1-30 Hz): EC {rel['EC']:.0f}%  ->  EO {rel['EO']:.0f}%      "
                  f"Peak alpha frequency: EC {hz(paf)}  ->  EO {hz(eo_paf)}", 8)
    y -= 14

    if have:
        fig, ax = plt.subplots(figsize=(7.2, 2.1))
        for tag, colr in (("EC", "#1f5fbf"), ("EO", "#d2691e")):
            f = spec[tag][have[0]][0]
            pm = np.mean([spec[tag][s][1] for s in have], axis=0)
            m = (f >= 1) & (f <= 30)
            ax.semilogy(f[m], pm[m], color=colr, lw=1.4, label=f"{tag} posterior mean")
        ax.axvspan(*band, color="#e8f0ff", zorder=0)
        ax.set_xlabel("Hz", fontsize=7)
        ax.set_ylabel("uV^2/Hz", fontsize=7)
        ax.tick_params(labelsize=7)
        ax.legend(fontsize=7, frameon=False)
        fig.tight_layout(pad=0.4)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=170)
        plt.close(fig)
        buf.seek(0)
        img = ImageReader(buf)
        iw, ih = img.getSize()
        dw = W - 2 * M
        dh = dw * ih / iw
        c.drawImage(img, M, y - dh, dw, dh)
        y -= dh + 10

    text(c, M, y, "Brain Panel rows that track blocking (supporting evidence)", 9.5, bold=True)
    y -= 11
    y = para(c, M, y, "Raw panel values, no z-scores (EC_191 is an eyes-closed database). Across 147 "
                      "same-session QA pairs these four rows were the only ones whose EC->EO change tracked "
                      "the EDF attenuation, and only weakly (rho shown). Read the count of consistent rows as "
                      "corroboration of the EDF figure, never as a measure of blocking by itself.",
             W - 2 * M, 7, color=GREY)
    y -= 2
    cols = [M, M + 120, M + 180, M + 240, M + 300, M + 380, M + 420]
    for x, h_ in zip(cols, ["Metric", "EC", "EO", "change", "on blocking", "rho", "consistent?"]):
        text(c, x, y, h_, 8, bold=True)
    y -= 10.5
    blocked = not np.isnan(allr[2]) and allr[2] > 0
    n_ok = 0
    for i, direction, rho in BLOCKING_ROWS:
        ve, vo = ec["values"][i], eo["values"][i]
        ok = (vo < ve) == (direction == "falls")
        if not blocked:
            ok = not ok      # no blocking in the EDF: the rows should NOT move the blocking way
        n_ok += ok
        text(c, cols[0], y, NAME_STRINGS[i], 7.8)
        text(c, cols[1], y, f"{ve:.2f}", 7.8)
        text(c, cols[2], y, f"{vo:.2f}", 7.8)
        if ve:
            text(c, cols[3], y, f"{100.0 * (vo - ve) / abs(ve):+.0f}%", 7.8)
        text(c, cols[4], y, direction, 7.8)
        text(c, cols[5], y, f"{rho:.2f}", 7.8)
        text(c, cols[6], y, "yes" if ok else "no", 7.8, color=GREEN if ok else RED)
        y -= 10
    y -= 3
    low = n_ok <= LOW_AGREE
    text(c, M, y, f"{n_ok} of {len(BLOCKING_ROWS)} panel rows agree with the EDF reading"
                  + (" - worth a second look at the EC record." if low else "."), 8, bold=True,
         color=(0.75, 0.45, 0.0) if low else (0, 0, 0))
    y -= 10
    y = para(c, M, y, f"In the QA pairs, {LOW_AGREE} or fewer agreeing occurred in 17% of robust-blocking "
                      "pairs but 59% of paradoxical ones, and in 49% (vs 21%) of pairs whose EC alpha peak was "
                      "slow (< 8 Hz) or absent - a soft prompt to check the EC record for drowsiness, mislabeled "
                      "conditions or artifact, not a finding.", W - 2 * M, 7, color=GREY)
    y -= 2
    text(c, M, y, f"STD Raw (absolute uV): EC {ec['values'][0]:.2f} -> EO {eo['values'][0]:.2f}", 7.8, color=GREY)
    footer(c, 1)
    c.showPage()

    header(c, "Image cascade: alpha sources EC vs EO",
           "Which ICA sources carry the alpha, and how much of the brain variance they hold in each condition.")
    y = H - 72
    if ec["comps"] and eo["comps"]:
        img = component_spectrum_png([ec, eo], ["EC", "EO"])
        iw, ih = img.getSize()
        dw = W - 2 * M
        dh = dw * ih / iw
        c.drawImage(img, M, y - dh, dw, dh)
        y -= dh + 14
        A, B = cascade_summary(ec["comps"]), cascade_summary(eo["comps"])
        for x, h_ in zip([M + 8, M + 190, M + 350], ["", "EC", "EO"]):
            text(c, x, y, h_, 8, bold=True)
        y -= 11
        for label_, fn in CASCADE_ROWS:
            text(c, M + 8, y, label_, 7.8)
            text(c, M + 190, y, fn(A), 7.8)
            text(c, M + 350, y, fn(B), 7.8)
            y -= 10.5
        y -= 6
        drop = A["alpha_post"] - B["alpha_post"]
        y = para(c, M, y, f"Posterior alpha sources fall from {A['alpha_post']:.0f}% to {B['alpha_post']:.0f}% "
                          f"of the variance on eye opening ({drop:+.0f} points)." if drop >= 0 else
                          f"Posterior alpha sources RISE from {A['alpha_post']:.0f}% to {B['alpha_post']:.0f}% "
                          "of the variance on eye opening.", W - 2 * M, 8.5, bold=True)
        y -= 4
        para(c, M, y, "Posterior = alpha components whose maximum is at O1 O2 OZ P3 P4 PZ T5 T6. Cascade % "
                      "is relative within each recording, so when all alpha shrinks together its total share "
                      "barely moves; the shift of alpha AWAY from posterior sites is the cascade's sign of "
                      "blocking. The absolute change is the EDF figure on page 1. Each cascade is a separate "
                      "decomposition, so components do not correspond one-to-one between EC and EO.",
             W - 2 * M, 7, color=GREY)
    else:
        para(c, M, y, "Cascade comparison skipped: an .imagecascade.pdf is missing for "
                      + ("both studies." if not (ec["comps"] or eo["comps"]) else "one study.")
                      + " Render with run_cascade.py.", W - 2 * M, 8, color=GREY)
    footer(c, 2)
    c.save()
    summ = {"attn": allr[2], "attn_left": left[2], "attn_right": right[2], "band": band,
            "paf_ec": paf, "paf_eo": eo_paf, "rel_ec": rel["EC"], "rel_eo": rel["EO"],
            "reading": reactivity_label(allr[2])[0], "warnings": warns, "panel_agree": n_ok}
    if ec["comps"] and eo["comps"]:
        summ["casc_post"] = (A["alpha_post"], B["alpha_post"])
    return summ


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["prepost", "eceo"])
    ap.add_argument("first")
    ap.add_argument("second")
    ap.add_argument("--out")
    args = ap.parse_args()
    a, b = load_study(args.first), load_study(args.second)
    if args.mode == "prepost":
        if a["recorded"] and b["recorded"] and b["recorded"] < a["recorded"]:
            a, b = b, a
        out = args.out or b["base"] + ".prepost.pdf"
        prepost(a, b, out)
    else:
        out = args.out or b["base"] + ".eceo.pdf"
        eceo(a, b, out)
    print("Wrote", out)


if __name__ == "__main__":
    main()
