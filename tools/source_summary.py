"""One-page source summary of an IMG cascade (prototype).

The cascade spends two pages on every ICA component, so 20-40 pages. This
puts the brain sources on one page: the cortex with every ACCEPTED component's
sLORETA blob painted in its frequency band's colour, one table row per source
(where, band, typical function of its Brodmann area), and how much of the
recording the rejected (artifact) components took out.

Reads `<edf>.sources.npz`, the sidecar the cascade pass writes next to
`<edf>.imagecascade.pdf` (files/Montage_6.py). Cascades rendered before the
sidecar existed have to be re-run. Display only -- nothing here feeds a metric.

Page 2 (when the sidecar carries the component time courses) asks which of
those sources work TOGETHER: band-limited amplitude envelopes of the accepted
components, correlated over 1 s bins, tested against circular-shift
surrogates, grouped, and each group's combined source map compared with the
nodes of the default mode, salience and executive control networks.

Usage:
    py tools/source_summary.py "<edf | .sources.npz | .imagecascade.pdf>" [--out x.pdf]
Writes <edf base>.sources.pdf by default.
"""
import os
import sys
import argparse

import csv

import numpy as np
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Rectangle
from matplotlib.colors import to_rgb
from matplotlib.backends.backend_pdf import PdfPages
from scipy.signal import butter, sosfiltfilt, hilbert
from scipy.stats import rankdata
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

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
# Nodes: a component's sLORETA map often has more than one peak (a zero-lag
# network that ICA kept as ONE component, or a bilateral source). A secondary
# local maximum counts as a node only if it is >= NODE_MIN of the component's
# peak, >= NODE_SEP_MM from every stronger node, and the map dips below
# NODE_VALLEY x its value on the straight line to each of them -- 19-channel
# sLORETA is smooth and ripply, and distance alone splits one blob into many.
NODE_MIN, NODE_VALLEY, NODE_SEP_MM, MAX_NODES = 0.70, 0.75, 25.0, 3
VOXEL_CSV = os.path.join(ROOT, "MNI-BAs-6239-voxels.csv")

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


def _ba(area):
    t = str(area).split()
    return int(t[-1]) if t and t[-1].isdigit() else None


def find_nodes(vox, csd_n, tree, nbrs, labels):
    """Peak first, then secondary nodes (see NODE_* above)."""
    locmax = np.fromiter((csd_n[k] >= csd_n[nbrs[k]].max() for k in range(len(csd_n))), bool)
    cand = np.where(locmax & (csd_n >= NODE_MIN))[0]
    cand = cand[np.argsort(-csd_n[cand])]

    def valley(a, b):
        t = np.linspace(0, 1, max(3, int(np.linalg.norm(vox[a] - vox[b]) / 2.5)))
        d, j = tree.query(vox[a] + t[:, None] * (vox[b] - vox[a]))
        return np.where(d <= 6.0, csd_n[j], 0.0).min()     # off the grid = outside the brain

    keep = []
    for k in cand:
        if all(np.linalg.norm(vox[k] - vox[j]) >= NODE_SEP_MM and valley(k, j) < NODE_VALLEY * csd_n[k]
               for j in keep):
            keep.append(k)
        if len(keep) == MAX_NODES:
            break
    out = []
    for k in keep:
        lobe, region, area = labels[k]
        x = vox[k, 0]
        out.append(dict(xyz=vox[k], rel=float(csd_n[k]), side="L" if x < 0 else ("R" if x > 0 else "Mid"),
                        lobe=lobe.replace(" Lobe", ""), region=region, ba=_ba(area)))
    return out


def load(npz):
    z = np.load(npz)
    vox = z["vox"].astype(float)
    with open(VOXEL_CSV, newline="") as fh:
        labels = [row[3:6] for row in csv.reader(fh)]
    tree = cKDTree(vox)
    nbrs = tree.query_ball_point(vox, r=9.0)                 # 26-neighbourhood on the 5 mm grid
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
        csd = z["csd"][i].astype(float)
        comps[-1]["nodes"] = find_nodes(vox, csd / (csd.max() or 1.0), tree, nbrs, labels)
    src = z["sources"].astype(float) if "sources" in z.files else None
    fs = float(z["fs"]) if "fs" in z.files else 256.0
    return dict(sources=src, fs=fs, vox=vox, csd=z["csd"].astype(float), comps=comps,
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
            # node markers, only where a node sits just under the visible surface
            for kn, node in enumerate(c["nodes"] or [dict(xyz=c["xyz"])]):
                p = np.asarray(node["xyz"], float)
                pc = (p @ r["right"] - r["u0"]) * br.PX_PER_MM + r["pad"]
                pr = (r["w1"] - p @ r["up"]) * br.PX_PER_MM + r["pad"]
                ci, ri = int(round(pc)), int(round(pr))
                if 0 <= ri < r["H"] and 0 <= ci < r["W"]:
                    zb = r["zb"][ri * r["W"] + ci]
                    if np.isfinite(zb) and -10.0 < zb - p @ r["toward"] < 20.0:
                        markers.append((pc, pr, c["rank"], kn == 0))
        lit = (0.55 + 0.45 * r["shade"])[:, None]
        img = r["base"].copy()
        m = r["mask"]
        img[m] = img[m] * (1 - alpha[:, None]) + (rgb * lit) * alpha[:, None]
        out.append((r["name"], r["lr"], img.reshape(r["H"], r["W"], 3), markers))
    return out


# ------------------------------------------------------------------ page
def render(base, npz, out):
    data = load(npz)
    with PdfPages(out) as pdf:
        page_sources(data, pdf)
        if data["sources"] is not None:
            page_networks(data, pdf)
        else:
            print("sidecar has no component time courses -- re-run the cascade for the network page")
    return out


def page_sources(data, pdf):
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
        for pc, pr, rank, primary in sorted(markers, key=lambda m: m[3]):   # peaks on top
            if primary:
                a.plot(pc, pr, "o", ms=10, mfc="white", mec="#222", mew=0.8, alpha=0.9)
                a.text(pc, pr, str(rank), ha="center", va="center", fontsize=6.5, color="#111",
                       fontweight="bold")
            else:
                a.plot(pc, pr, "o", ms=8, mfc="#f2f2f2", mec="#777", mew=0.6, ls="none", alpha=0.85)
                a.text(pc, pr, str(rank), ha="center", va="center", fontsize=5.5, color="#555")
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
             f"components of {MIN_DRAW_PCT:g}% or more. Bold numbers mark peaks, small grey ones a "
             "component's other nodes; all match the table and the cascade.", fontsize=7.5, color="#555", va="top")

    # --- table
    tx, ty = 0.515, 0.80
    cols = [(0.000, "#"), (0.024, "%"), (0.060, "Band Hz"), (0.135, "Where (peak)"),
            (0.300, "Area · typically involved in")]
    for dx, h in cols:
        fig.text(tx + dx, ty, h, fontsize=8.5, fontweight="bold", color="#222")
    fig.lines.append(plt.Line2D([tx, 0.985], [ty - 0.008, ty - 0.008], transform=fig.transFigure,
                                color="#999", lw=0.6))
    rows = acc

    def also(c):
        """Other nodes, shown under the row for drawn components."""
        if 100 * c["pct"] / tot < MIN_DRAW_PCT or len(c["nodes"]) < 2:
            return ""
        return "also " + ";  ".join(
            f"{nd['side']} {nd['region'] or nd['lobe']}" + (f" BA {nd['ba']}" if nd["ba"] else "")
            + f" ({100 * nd['rel']:.0f}%)" for nd in c["nodes"][1:])

    units = sum(1 + (0.62 if also(c) else 0) for c in rows)
    step = min(0.032, (ty - 0.235) / max(units, 1))
    fs = 8.0 if step >= 0.028 else 7.0
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
        sub = also(c)
        if sub:
            y -= step * 0.62
            fig.text(tx + 0.135, y + step * 0.08, sub, fontsize=fs - 1.2, color="#666", va="center")
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

    pdf.savefig(fig, facecolor="white")
    plt.close(fig)


# ------------------------------------------------------------------ networks
# Canonical node centres (MNI mm), approximate, from the resting-state
# literature (Raichle 2001; Seeley 2007; Menon 2011). A placeholder for a
# proper atlas (Yeo 7-network) mapped onto the 6239-voxel grid.
NETWORKS = {
    "Default mode": [(0, -53, 26), (0, 52, -6), (-48, -62, 36), (50, -60, 36),
                     (-60, -20, -15), (60, -20, -15)],
    "Salience": [(4, 30, 30), (-38, 18, 0), (38, 18, 0)],
    "Executive control": [(-44, 30, 32), (44, 30, 32), (-46, -52, 46), (46, -52, 46)],
}
NET_COL = {"Default mode": "#CC79A7", "Salience": "#D55E00", "Executive control": "#0072B2"}
NODE_R_MM = 15.0
NET_ENRICH = 2.0         # template match = core mass in its nodes >= 2x chance
COUPLE_BANDS = [("Theta", 4.0, 8.0), ("Alpha", 8.0, 13.0), ("Beta", 13.0, 30.0)]
ENV_BIN_S = 1.0
N_SURR, SURR_SEED, FWE = 500, 0, 0.05
MIN_COUPLE_PCT = 1.0     # components smaller than this are left out of the coupling


def envelopes(x, fs, lo, hi):
    sos = butter(4, [lo, hi], btype="band", fs=fs, output="sos")
    env = np.abs(hilbert(sosfiltfilt(sos, x, axis=1), axis=1))
    b = int(round(ENV_BIN_S * fs))
    nb = env.shape[1] // b
    return np.log(env[:, :nb * b].reshape(len(x), nb, b).mean(axis=2) + 1e-12)


def _partial(ranks, n):
    """Partial correlation of the first n rows, given ALL other rows."""
    P = np.linalg.pinv(np.corrcoef(ranks))
    d = np.sqrt(np.diag(P))
    pc = -P / np.outer(d, d)
    np.fill_diagonal(pc, 1.0)
    return pc[:n, :n]


def coupling(e, e_art, rng):
    """Partial Spearman r between envelope pairs, holding every other accepted
    component AND the rejected (artifact) components constant, plus a
    family-wise |r| threshold from circular-shift surrogates (each envelope
    keeps its own autocorrelation).

    Plain correlation was tried first: on real studies nearly every pair is
    positive (r 0.2-0.6) -- a whole-recording factor (vigilance, overall
    amplitude, artifact bursts) -- and the groups swallowed most components.
    Partialling it out leaves the DIRECT couplings, and can show opposition."""
    n, T = e.shape
    ranks = np.apply_along_axis(rankdata, 1, np.vstack([e, e_art]) if len(e_art) else e)
    r = _partial(ranks, n)
    iu = np.triu_indices(n, 1)
    mx = np.empty(N_SURR)
    for k in range(N_SURR):
        sh = np.stack([np.roll(ranks[i], rng.integers(T // 10, T - T // 10))
                       for i in range(len(ranks))])
        mx[k] = np.abs(_partial(sh, n)[iu]).max()
    return r, float(np.quantile(mx, 1 - FWE))


def template_scores(vox, csd_n):
    core = csd_n >= max(0.7, np.percentile(csd_n, 95))
    w = csd_n * core
    out = {}
    for name, nodes in NETWORKS.items():
        inn = np.zeros(len(vox), bool)
        for nd in nodes:
            inn |= np.linalg.norm(vox - np.array(nd), axis=1) <= NODE_R_MM
        out[name] = (w[inn].sum() / (w.sum() or 1.0)) / inn.mean()
    return out


def best_template(sc):
    name = max(sc, key=sc.get)
    return (name, sc[name]) if sc[name] >= NET_ENRICH else (None, sc[name])


def page_networks(data, pdf):
    comps = data["comps"]
    tot = sum(c["pct"] for c in comps) or 1.0
    use = [c for c in comps if c["accept"] and 100 * c["pct"] / tot >= MIN_COUPLE_PCT]
    vox, fs = data["vox"], data["fs"]
    X = data["sources"][[c["idx"] for c in use]]
    A = data["sources"][[c["idx"] for c in comps if not c["accept"]]]
    rng = np.random.default_rng(SURR_SEED)
    csd_n = {c["rank"]: data["csd"][c["idx"]] / (data["csd"][c["idx"]].max() or 1.0) for c in use}
    for c in use:
        c["tmpl"] = best_template(template_scores(vox, csd_n[c["rank"]]))

    res = []
    for bname, lo, hi in COUPLE_BANDS:
        r, thr = coupling(envelopes(X, fs, lo, hi),
                          envelopes(A, fs, lo, hi) if len(A) else np.empty((0, 1)), rng)
        # groups: average linkage on 1 - r, cut at the significance threshold
        groups = []
        if len(use) > 1:
            d = np.clip(1 - r, 0, 2)
            np.fill_diagonal(d, 0)
            lab = fcluster(linkage(squareform(d, checks=False), "average"), 1 - thr, "distance")
            for g in np.unique(lab):
                mem = [i for i in range(len(use)) if lab[i] == g]
                if len(mem) < 2:
                    continue
                sub = r[np.ix_(mem, mem)][np.triu_indices(len(mem), 1)]
                w = sum(use[i]["pct"] * csd_n[use[i]["rank"]] for i in mem)
                tm = best_template(template_scores(vox, w / w.max()))
                groups.append(dict(members=mem, mean_r=float(sub.mean()), tmpl=tm,
                                   pct=100 * sum(use[i]["pct"] for i in mem) / tot))
        groups.sort(key=lambda g: -g["pct"])
        res.append(dict(band=bname, r=r, thr=thr, groups=groups))

    fig = plt.figure(figsize=(11.69, 8.27), dpi=150, facecolor="white")
    fig.text(0.03, 0.965, "Brain Sources — which ones work together", fontsize=17,
             fontweight="bold", color="#1a1a1a", va="center")
    fig.text(0.03, 0.932, f"{data['label'].replace('BMrICA: ', '')}    ·    amplitude-envelope "
             f"coupling (partial) of the {len(use)} accepted components >= {MIN_COUPLE_PCT:g}%, "
             f"{ENV_BIN_S:g} s bins", fontsize=9.5, color="#444", va="center")

    # --- matrices
    names = [str(c["rank"]) for c in use]
    for k, rb in enumerate(res):
        ax = fig.add_axes([0.035 + k * 0.165, 0.60, 0.14, 0.27])
        m = rb["r"].copy()
        np.fill_diagonal(m, np.nan)
        ax.imshow(m, cmap="RdBu_r", vmin=-0.5, vmax=0.5, interpolation="nearest")
        sig = np.argwhere(np.abs(rb["r"]) >= rb["thr"])
        for i, j in sig:
            if i != j:
                ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, ec="#111", lw=0.9))
        ax.set_xticks(range(len(names))); ax.set_yticks(range(len(names)))
        ax.set_xticklabels(names, fontsize=5.5); ax.set_yticklabels(names, fontsize=5.5)
        ax.tick_params(length=0, pad=1)
        ax.set_title(f"{rb['band']}   |r| >= {rb['thr']:.2f} boxed", fontsize=8.5, color="#222", pad=3)
    cax = fig.add_axes([0.035, 0.565, 0.47, 0.010])
    cax.imshow(np.linspace(-0.5, 0.5, 256)[None, :], cmap="RdBu_r", aspect="auto",
               extent=[-0.5, 0.5, 0, 1])
    cax.set_yticks([]); cax.tick_params(labelsize=7)
    cax.set_xlabel("partial Spearman r of band envelopes, others + artifacts held constant (blue: opposite)", fontsize=7.5,
                   color="#444", labelpad=1)

    # --- dorsal + lateral views with coupling edges
    geom = br._geometry(vox)
    vname = {"Dorsal": None, "Left lateral": None, "Right lateral": None}
    for r in geom["views"]:
        if r["name"] in vname:
            vname[r["name"]] = r
    bcol = {"Theta": "#0072B2", "Alpha": "#009E73", "Beta": "#E69F00"}
    for k, nm in enumerate(["Left lateral", "Dorsal", "Right lateral"]):
        r = vname[nm]
        ax = fig.add_axes([0.02 + k * 0.165, 0.10, 0.16, 0.40])
        img = r["base"].reshape(r["H"], r["W"], 3)
        ax.imshow(img, interpolation="antialiased")

        def proj(p):
            p = np.asarray(p, float)
            return ((p @ r["right"] - r["u0"]) * br.PX_PER_MM + r["pad"],
                    (r["w1"] - p @ r["up"]) * br.PX_PER_MM + r["pad"])

        side = {"Left lateral": -1, "Right lateral": 1, "Dorsal": 0}[nm]

        def shown(c):
            return side == 0 or np.sign(c["xyz"][0]) in (side, 0)

        for rb in res:
            for i, j in np.argwhere(np.triu(np.abs(rb["r"]) >= rb["thr"], 1)):
                ci, cj = use[i], use[j]
                if not (shown(ci) and shown(cj)):
                    continue
                (x1, y1), (x2, y2) = proj(ci["xyz"]), proj(cj["xyz"])
                pos = rb["r"][i, j] > 0
                ax.plot([x1, x2], [y1, y2], color=bcol[rb["band"]], lw=0.8 + 7 * abs(rb["r"][i, j]),
                        ls="-" if pos else (0, (2, 1.5)), alpha=0.8, solid_capstyle="round")
        for c in use:
            if shown(c):
                x, y = proj(c["xyz"])
                ax.plot(x, y, "o", ms=9, mfc="white", mec="#222", mew=0.7)
                ax.text(x, y, str(c["rank"]), ha="center", va="center", fontsize=6, fontweight="bold")
        ax.set_axis_off()
        ax.set_title(nm, fontsize=9, color="#333", pad=1)
    lx = 0.035
    for b, col in bcol.items():
        fig.lines.append(plt.Line2D([lx, lx + 0.025], [0.092, 0.092], transform=fig.transFigure,
                                    color=col, lw=2.5))
        fig.text(lx + 0.03, 0.092, b, fontsize=8, va="center")
        lx += 0.08
    fig.text(lx, 0.092, "solid = rise together, dashed = opposite; width = |r|.  Circles at each "
             "component's peak.", fontsize=7.5, color="#555", va="center")

    # --- right column: groups and template matches
    tx, y = 0.53, 0.875
    fig.text(tx, y, "Coupled groups", fontsize=11, fontweight="bold", color="#1a1a1a")
    y -= 0.032
    groups = [(rb["band"], g) for rb in res for g in rb["groups"]]
    shown_n = 0
    for band, g in groups:
        if y < 0.44:
            fig.text(tx + 0.012, y, f"+ {len(groups) - shown_n} more group(s) not shown",
                     fontsize=7.5, color="#777", va="center")
            y -= 0.03
            break
        shown_n += 1
        mem = ", ".join(str(use[i]["rank"]) for i in g["members"])
        tname, tval = g["tmpl"]
        fig.patches.append(Rectangle((tx, y - 0.007), 0.006, 0.016, transform=fig.transFigure,
                                     facecolor=bcol[band]))
        fig.text(tx + 0.012, y, f"{band}:  {mem}   ({g['pct']:.0f}% of recording, "
                 f"mean r {g['mean_r']:+.2f})", fontsize=8.3, color="#111", va="center")
        y -= 0.020
        nodes = "; ".join(f"{use[i]['side']} {use[i]['region'] or use[i]['lobe']}"
                          for i in g["members"])
        if len(nodes) > 92:
            nodes = nodes[:91] + "…"
        fig.text(tx + 0.012, y, nodes, fontsize=7, color="#555", va="center")
        y -= 0.018
        fig.text(tx + 0.012, y, (f"combined map matches {tname} ({tval:.1f}x chance)" if tname
                                 else f"combined map matches no template (best {tval:.1f}x)"),
                 fontsize=7.5, color=NET_COL.get(tname, "#777"), va="center",
                 fontweight="bold" if tname else "normal")
        y -= 0.028
    if not groups:
        fig.text(tx + 0.012, y, "No pair of components co-varies beyond the surrogate threshold "
                 "in any band.", fontsize=8.3, color="#555", va="center")
        y -= 0.035

    y = min(y, 0.38)
    fig.text(tx, y, "Single components on a network's nodes", fontsize=11, fontweight="bold",
             color="#1a1a1a")
    y -= 0.03
    hits = [c for c in use if c["tmpl"][0]]
    for c in hits[:8]:
        fig.text(tx + 0.012, y, f"{c['rank']}  {band_of(c['hz'])[0]} {c['hz']:.1f} Hz  "
                 f"{c['side']} {c['region'] or c['lobe']}  ->  {c['tmpl'][0]} ({c['tmpl'][1]:.1f}x)",
                 fontsize=7.8, color=NET_COL[c["tmpl"][0]], va="center")
        y -= 0.021
    if not hits:
        fig.text(tx + 0.012, y, "none", fontsize=8, color="#777")

    fig.lines.append(plt.Line2D([0.03, 0.97], [0.072, 0.072], transform=fig.transFigure,
                                color="#ccc", lw=0.6))
    fig.text(0.03, 0.064,
             "How to read this: ICA makes components independent sample by sample, but their band "
             "amplitudes can still rise and fall together over seconds, the timescale on which "
             "resting-state networks co-vary.\nEach r is PARTIAL: all other components and the "
             "artifact components are held constant, so a shared state or artifact burst does not "
             f"link everything. Boxed = beyond a family-wise 5% threshold from {N_SURR} circular-shift "
             "surrogates.\nAn edge is co-variation, not proof of communication. Network nodes are "
             "approximate literature centres (15 mm spheres); deep nodes (insula, hippocampus) are "
             "poorly seen from 19 channels,\nand eye artifacts localize near the salience network's "
             "anterior insula and orbitofrontal cortex, so check a salience match against the "
             "component's band (delta = suspect). Display only.",
             fontsize=6.9, color="#555", va="top", linespacing=1.45)
    pdf.savefig(fig, facecolor="white")
    plt.close(fig)


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
