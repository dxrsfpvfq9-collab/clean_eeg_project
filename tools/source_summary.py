"""One-page source summary of an IMG cascade (prototype).

The cascade spends two pages on every ICA component, so 20-40 pages. This
puts the brain sources on one page: the cortex with every ACCEPTED component's
sLORETA blob painted in its frequency band's colour, one table row per source
(where, band, typical function of its Brodmann area), and how much of the
recording the rejected (artifact) components took out.

Reads `<edf>.sources.npz`, the sidecar the cascade pass writes next to
`<edf>.imagecascade.pdf` (files/Montage_6.py). Cascades rendered before the
sidecar existed have to be re-run. Display only -- nothing here feeds a metric.

Usage:
    py tools/source_summary.py "<edf | .sources.npz | .imagecascade.pdf>" [--out x.pdf]
Writes <edf base>.sources.pdf by default.
"""
import os
import sys
import argparse

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Rectangle
from matplotlib.colors import to_rgb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from process import brain_render as br  # noqa: E402

LINE_HZ = (59.0, 61.0)          # same window the cascade table marks "(line)"
BANDS = [  # (name, lo, hi, colour) -- Okabe-Ito hues, distinct for colour-blind readers
    ("Delta", 0.0, 4.0, "#7B3294"),
    ("Theta", 4.0, 8.0, "#0072B2"),
    ("Alpha", 8.0, 13.0, "#009E73"),
    ("Beta", 13.0, 30.0, "#E69F00"),
    ("Gamma", 30.0, 1e9, "#D55E00"),
]
ARTIFACT = "#9a9a9a"
# The cascade pages colour each component from its 87th voxel percentile; the
# union of 15 such blobs is the whole cortex. Here only the core is painted,
# and only for components big enough to matter.
PAINT_PCT, PAINT_FLOOR = 95.0, 0.70
MIN_DRAW_PCT = 2.0

# Textbook associations, one line each. What an area is usually involved in,
# not a finding about this client.
BA_FUNCTION = {
    1: "touch / body sense", 2: "touch / body sense", 3: "touch / body sense",
    4: "voluntary movement", 5: "body position, reaching",
    6: "movement planning", 7: "spatial attention, visuomotor",
    8: "eye movements, attention", 9: "working memory, executive",
    10: "planning, holding goals", 11: "reward, decision-making",
    13: "interoception, emotion", 17: "primary vision", 18: "visual processing",
    19: "visual association", 20: "object recognition", 21: "word meaning, semantics",
    22: "hearing / language comprehension", 23: "default mode, self-reflection",
    24: "emotion, error monitoring", 25: "mood regulation",
    27: "memory (parahippocampal)", 28: "memory (entorhinal)", 29: "spatial memory",
    30: "spatial memory", 31: "default mode, self-reflection",
    32: "cognitive control, conflict", 33: "emotion (cingulate)",
    34: "memory, smell (uncus)", 35: "memory (perirhinal)", 36: "memory, scenes",
    37: "faces and words", 38: "social / emotional meaning",
    39: "reading, numbers", 40: "phonology, body awareness",
    41: "primary hearing", 42: "hearing", 43: "taste / mouth sensation",
    44: "speech production", 45: "speech production",
    46: "attention, working memory", 47: "language, response inhibition",
}


def band_of(hz):
    for name, lo, hi, col in BANDS:
        if lo <= hz < hi:
            return name, col
    return BANDS[-1][0], BANDS[-1][3]


def resolve(path):
    base = path
    for ext in (".sources.npz", ".imagecascade.pdf", ".icale.rep.pdf", ".edf"):
        if base.lower().endswith(ext):
            base = base[:-len(ext)]
            break
    npz = base + ".sources.npz"
    if not os.path.exists(npz):
        sys.exit(f"no {os.path.basename(npz)} -- re-run the cascade (test_imagecascade.py / "
                 "run_cascade.py) with this code to write it")
    return base, npz


def load(npz):
    z = np.load(npz)
    n = len(z["pct"])
    order = [int(i) for i in z["order"]]
    comps = []
    for rank, i in enumerate(order, 1):
        hz = float(z["fft_peak"][i])
        line = LINE_HZ[0] <= hz <= LINE_HZ[1]
        lobe, region, area = (list(z["peak_label"][i]) + ["", "", ""])[:3]
        x = float(z["peak_xyz"][i][0])
        comps.append(dict(
            rank=rank, idx=i, pct=float(z["pct"][i]), hz=hz, line=line,
            accept=(str(z["user"][i]) == "Accept") and not line,
            site=str(z["max_site"][i]), lobe=lobe.replace(" Lobe", ""), region=region,
            ba=int(area.split()[-1]) if area.split() and area.split()[-1].isdigit() else None,
            side="L" if x < 0 else ("R" if x > 0 else "Mid"), xyz=z["peak_xyz"][i]))
    return dict(vox=z["vox"].astype(float), csd=z["csd"].astype(float), comps=comps,
                label=str(z["label"]), n=n)


# ------------------------------------------------------------------ cortex
def paint(geom, data, comps):
    """One image per view: each pixel shows the accepted component that is
    strongest there, weighted by its share of the recording."""
    out = []
    for r in geom["views"]:
        npx = r["mask"].sum()
        best = np.zeros(npx)
        alpha = np.zeros(npx)
        rgb = np.zeros((npx, 3))
        markers = []
        for c in comps:
            csd = data["csd"][c["idx"]]
            csd_n = csd / (csd.max() if csd.max() > 0 else 1.0)
            lo = min(max(PAINT_FLOOR, float(np.percentile(csd_n, PAINT_PCT))), 0.92)
            hi = min(lo + br.THR_FADE, 0.98)
            vv = (r["w"] * csd_n[r["j"]]).sum(axis=1)
            vv[~r["ok"]] = 0.0
            pv = np.einsum("pk,pk->p", r["wts"], vv[r["vid"]])
            a = np.clip((pv - lo) / (hi - lo), 0, 1)
            score = a * c["pct"]
            win = score > best
            best[win] = score[win]
            alpha[win] = a[win]
            t = np.clip((pv[win] - lo) / (1 - lo), 0, 1)[:, None]
            base = np.array(to_rgb(band_of(c["hz"])[1]))
            rgb[win] = base * (0.80 + 0.20 * t) + (1 - base) * 0.25 * (1 - t)
            # peak marker, only where the peak sits just under the visible surface
            p = np.asarray(c["xyz"], float)
            pc = (p @ r["right"] - r["u0"]) * br.PX_PER_MM + r["pad"]
            pr = (r["w1"] - p @ r["up"]) * br.PX_PER_MM + r["pad"]
            ci, ri = int(round(pc)), int(round(pr))
            if 0 <= ri < r["H"] and 0 <= ci < r["W"]:
                zb = r["zb"][ri * r["W"] + ci]
                if np.isfinite(zb) and -10.0 < zb - p @ r["toward"] < 20.0:
                    markers.append((pc, pr, c["rank"]))
        lit = (0.55 + 0.45 * r["shade"])[:, None]
        img = r["base"].copy()
        m = r["mask"]
        img[m] = img[m] * (1 - alpha[:, None]) + (rgb * lit) * alpha[:, None]
        out.append((r["name"], r["lr"], img.reshape(r["H"], r["W"], 3), markers))
    return out


# ------------------------------------------------------------------ page
def render(base, npz, out):
    data = load(npz)
    comps = data["comps"]
    acc = [c for c in comps if c["accept"]]
    rej = [c for c in comps if not c["accept"]]
    tot = sum(c["pct"] for c in comps) or 1.0
    acc_pct = 100 * sum(c["pct"] for c in acc) / tot
    rej_pct = 100 - acc_pct

    geom = br._geometry(data["vox"])
    drawn = [c for c in acc if 100 * c["pct"] / tot >= MIN_DRAW_PCT]
    views = paint(geom, data, drawn)

    fig = plt.figure(figsize=(11.69, 8.27), dpi=150, facecolor="white")
    fig.text(0.03, 0.965, "Brain Sources — one-page summary", fontsize=17, fontweight="bold",
             color="#1a1a1a", va="center")
    label = data["label"].replace("BMrICA: ", "")
    fig.text(0.03, 0.932, f"{label}    ·    from the ICA image cascade "
             f"({data['n']} components, sLORETA source of each)", fontsize=9.5, color="#444",
             va="center")

    # --- variance bar: what the recording is made of
    ax = fig.add_axes([0.03, 0.855, 0.94, 0.03])
    x = 0.0
    for c in acc + rej:
        w = 100 * c["pct"] / tot
        col = band_of(c["hz"])[1] if c["accept"] else ARTIFACT
        ax.add_patch(Rectangle((x, 0), w, 1, facecolor=col, edgecolor="white", lw=0.8,
                               hatch=None if c["accept"] else "////"))
        if w >= 3.2:
            ax.text(x + w / 2, 0.5, str(c["rank"]), ha="center", va="center", fontsize=7.5,
                    color="white", fontweight="bold")
        x += w
    ax.set_xlim(0, 100); ax.set_ylim(0, 1); ax.set_axis_off()
    ax.text(0, 1.35, f"Brain sources {acc_pct:.0f}% of the recording ({len(acc)} components)",
            fontsize=10, fontweight="bold", color="#1a1a1a", transform=ax.transData)
    rsites = ", ".join(sorted({c["site"] for c in rej}))
    ax.text(100, 1.35, f"Removed as artifact {rej_pct:.0f}% ({len(rej)}: {rsites})"
            if rej else "No components removed", fontsize=10, color="#555", ha="right",
            transform=ax.transData)

    # --- cortex, 2 x 3
    gs = GridSpec(2, 3, left=0.02, right=0.49, top=0.80, bottom=0.17, wspace=0.02, hspace=0.10)
    for k, (name, lr, img, markers) in enumerate(views):
        a = fig.add_subplot(gs[k // 3, k % 3])
        a.imshow(img, interpolation="antialiased")
        for pc, pr, rank in markers:
            a.plot(pc, pr, "o", ms=10, mfc="white", mec="#222", mew=0.8, alpha=0.9)
            a.text(pc, pr, str(rank), ha="center", va="center", fontsize=6.5, color="#111",
                   fontweight="bold")
        a.set_axis_off()
        a.set_title(name, fontsize=9, color="#333", pad=1)
        kw = dict(transform=a.transAxes, fontsize=8, fontweight="bold", color="#888")
        a.text(0.0, 0.02, lr[0], ha="left", va="bottom", **kw)
        a.text(1.0, 0.02, lr[1], ha="right", va="bottom", **kw)

    # band legend with the share of brain-source variance in each band
    share = {b[0]: 0.0 for b in BANDS}
    for c in acc:
        share[band_of(c["hz"])[0]] += 100 * c["pct"] / tot
    lx = 0.03
    for name, lo, hi, col in BANDS:
        fig.patches.append(Rectangle((lx, 0.128), 0.014, 0.018, transform=fig.transFigure,
                                     facecolor=col, edgecolor="none"))
        rng = f"{lo:g}-{hi:g} Hz" if hi < 1e8 else f">{lo:g} Hz"
        fig.text(lx + 0.018, 0.137, f"{name} {rng}  {share[name]:.0f}%", fontsize=8.5,
                 va="center", color="#222")
        lx += 0.128
    fig.text(0.03, 0.112, "Each area is coloured by the band of the accepted component that is "
             "strongest there (weighted by its share).\nOnly each source's core is painted, for "
             f"components of {MIN_DRAW_PCT:g}% or more. Numbers mark peaks and match the table "
             "and the cascade.", fontsize=7.5, color="#555", va="top")

    # --- table
    tx, ty = 0.515, 0.80
    cols = [(0.000, "#"), (0.024, "%"), (0.060, "Band Hz"), (0.135, "Where (peak)"),
            (0.300, "Area · typically involved in")]
    for dx, h in cols:
        fig.text(tx + dx, ty, h, fontsize=8.5, fontweight="bold", color="#222")
    fig.lines.append(plt.Line2D([tx, 0.985], [ty - 0.008, ty - 0.008], transform=fig.transFigure,
                                color="#999", lw=0.6))
    rows = acc
    step = min(0.034, (ty - 0.20) / max(len(rows), 1))
    fs = 8.0 if step >= 0.03 else 7.0
    y = ty - 0.008 - step * 0.75
    for c in rows:
        bname, bcol = band_of(c["hz"])
        fig.patches.append(Rectangle((tx - 0.008, y - 0.006), 0.005, 0.014,
                                     transform=fig.transFigure, facecolor=bcol))
        where = f"{c['side']} {c['region'] or c['lobe']}"
        if len(where) > 27:
            where = where[:26] + "…"
        func = f"BA {c['ba']} · {BA_FUNCTION.get(c['ba'], '')}" if c["ba"] else ""
        small = 100 * c["pct"] / tot < MIN_DRAW_PCT
        vals = [str(c["rank"]), f"{100 * c['pct'] / tot:.1f}", f"{bname} {c['hz']:.1f}",
                where, func]
        for (dx, _), v in zip(cols, vals):
            fig.text(tx + dx, y, v, fontsize=fs, color="#888" if small else "#111", va="center")
        y -= step
    if rej:
        y -= step * 0.4
        txt = "Removed: " + ", ".join(
            f"{c['rank']} ({c['site']}{', line' if c['line'] else ''})" for c in rej)
        fig.text(tx, y, txt, fontsize=7.5, color="#666", va="top", wrap=True)

    # --- footer
    fig.lines.append(plt.Line2D([0.03, 0.97], [0.085, 0.085], transform=fig.transFigure,
                                color="#ccc", lw=0.6))
    fig.text(0.03, 0.07,
             "How to read this: sources are estimated from 19 scalp channels by sLORETA, so each "
             "location is approximate (on the order of a centimetre or more) and deep or midline "
             "peaks are least certain.\nThe 'typically involved in' column is a textbook association "
             "for the Brodmann area, not a finding about this person. Removed components are the "
             "cascade's artifact rejects plus any power-line (59-61 Hz) component.\n"
             "Per-component detail (waveforms, spectrum, full source maps) is in the image cascade "
             "PDF. Display only: nothing here changes the Brain Panel metrics.",
             fontsize=7.2, color="#555", va="top", linespacing=1.45)

    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("study")
    ap.add_argument("--out")
    a = ap.parse_args()
    base, npz = resolve(a.study)
    out = a.out or base + ".sources.pdf"
    print("wrote", render(base, npz, out))


if __name__ == "__main__":
    main()
