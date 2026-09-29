"""Source-localization page for the IMG cascade, rendered WITHOUT OpenGL.

Replaces the PyVista/VTK grid in `dummy_brain` (files/dummy_gui.py), which
needs an OpenGL 3.2+ context the AWS servers do not have (a native abort there
took the whole process down -- see CLAUDE.md, CLEANEEG_NO_BRAIN).

Everything here is numpy + matplotlib (Agg) + scipy, all already required by
the pipeline:

  * the fsaverage pial surface (mne_data/.../fsaverage/surf) is rasterised by
    a small numpy z-buffer: each front-facing triangle is sampled on a
    barycentric grid, and the nearest sample wins each pixel. The geometry is
    the same for every component, so it is computed ONCE per process and each
    component only recolours it;
  * the 6239-voxel sLORETA current density is carried onto the surface
    vertices by a Gaussian-weighted k-nearest-voxel average (same hemisphere
    only, so a medial source does not bleed across the midline);
  * three orthogonal slices through the peak voxel show the voxel grid itself
    with pial / white-matter outlines cut from the same meshes.

Display only: it reads the voxel CSD that dummy_gui already computed and
changes no metric.
"""
import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.collections import LineCollection
from matplotlib.gridspec import GridSpec
from matplotlib.backends.backend_agg import FigureCanvasAgg
from scipy import ndimage
from scipy.spatial import cKDTree

_HERE = os.path.dirname(os.path.abspath(__file__))
_SURF_DIR = os.path.join(os.path.dirname(_HERE), 'mne_data', 'MNE-fsaverage-data', 'fsaverage', 'surf')

PX_PER_MM = 2.6        # surface-view resolution
BARY_N = 4             # barycentric subdivisions per triangle (15 samples)
# Display threshold, adaptive per component. sLORETA from 19 channels is
# blurry -- on real ICA components half the grid is often >= 50% of peak, so a
# fixed cut paints the whole cortex. Colour starts at the THR_PCT percentile
# of the voxel CSD (never below THR_FLOOR of peak) and fades in over THR_FADE.
THR_PCT, THR_FLOOR, THR_FADE = 87.0, 0.50, 0.08
VOXEL_MM = 5.0         # sLORETA grid spacing
MAP_SIGMA_MM = 5.0     # voxel -> vertex Gaussian
MAP_MAXDIST_MM = 10.0  # vertices farther than this from any voxel stay gray

HEAT = LinearSegmentedColormap.from_list(
    'src_heat', ['#7a0000', '#d7191c', '#f46d43', '#fdae61', '#fee08b', '#ffffbf'])

# (name, hemispheres drawn, toward-viewer, up, horizontal labels (left, right))
_VIEWS = [
    ('Left lateral',  ('lh',),      (-1, 0, 0), (0, 0, 1), ('A', 'P')),
    ('Dorsal',        ('lh', 'rh'), (0, 0, 1),  (0, 1, 0), ('L', 'R')),
    ('Right lateral', ('rh',),      (1, 0, 0),  (0, 0, 1), ('P', 'A')),
    ('Left medial',   ('lh',),      (1, 0, 0),  (0, 0, 1), ('P', 'A')),
    ('Ventral',       ('lh', 'rh'), (0, 0, -1), (0, 1, 0), ('R', 'L')),
    ('Right medial',  ('rh',),      (-1, 0, 0), (0, 0, 1), ('A', 'P')),
]

_cache = {}


# --------------------------------------------------------------------------- IO
def _read_surface(path):
    """FreeSurfer triangle surface (lh.pial etc). Read directly because
    mne.read_surface needs nibabel, which the pipeline does not install."""
    with open(path, 'rb') as fh:
        if fh.read(3) != b'\xff\xff\xfe':
            raise ValueError('not a FreeSurfer triangle surface: ' + path)
        fh.readline(); fh.readline()                      # "created by ..." + blank
        nv, nf = np.frombuffer(fh.read(8), dtype='>i4')
        v = np.frombuffer(fh.read(12 * nv), dtype='>f4').reshape(nv, 3)
        f = np.frombuffer(fh.read(12 * nf), dtype='>i4').reshape(nf, 3)
    return v.astype(np.float64), f.astype(np.int64)


def _read_curv(path):
    """FreeSurfer 'new' curvature format (lh.sulc): big-endian float32."""
    with open(path, 'rb') as fh:
        magic = fh.read(3)
        if magic != b'\xff\xff\xff':
            raise ValueError('not a FreeSurfer curv file: ' + path)
        nv, _nf, _vpv = np.frombuffer(fh.read(12), dtype='>i4')
        return np.frombuffer(fh.read(4 * nv), dtype='>f4').astype(np.float64)


def _vertex_normals(v, f):
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    vn = np.zeros_like(v)
    for k in range(3):
        np.add.at(vn, f[:, k], fn)
    vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
    return vn


def _load():
    if 'surf' in _cache:
        return _cache['surf']
    surf = {}
    for h in ('lh', 'rh'):
        v, f = _read_surface(os.path.join(_SURF_DIR, h + '.pial'))
        vw, fw = _read_surface(os.path.join(_SURF_DIR, h + '.white'))
        sulc = _read_curv(os.path.join(_SURF_DIR, h + '.sulc'))
        surf[h] = dict(v=v, f=f, n=_vertex_normals(v, f), sulc=sulc, vw=vw, fw=fw)
    _cache['surf'] = surf
    return surf


# -------------------------------------------------------------------- raster
def _rasterize(v, f, vn, sulc, toward, up):
    """Orthographic z-buffer of one mesh. Returns the per-pixel vertex triple and
    barycentric weights for covered pixels, plus a static shaded-gray image."""
    toward = np.asarray(toward, float)
    up = np.asarray(up, float)
    right = np.cross(up, toward)
    P = np.stack([v @ right, v @ up, v @ toward], axis=1)

    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    ff = f[fn @ toward > 0]

    pad = 6
    u0, u1 = P[:, 0].min(), P[:, 0].max()
    w0, w1 = P[:, 1].min(), P[:, 1].max()
    W = int(np.ceil((u1 - u0) * PX_PER_MM)) + 2 * pad
    H = int(np.ceil((w1 - w0) * PX_PER_MM)) + 2 * pad
    px = (P[:, 0] - u0) * PX_PER_MM + pad
    py = (w1 - P[:, 1]) * PX_PER_MM + pad

    n = BARY_N
    B = np.array([(1 - (i + j) / n, i / n, j / n)
                  for i in range(n + 1) for j in range(n + 1 - i)], dtype=np.float32)
    S = len(B)
    col = np.rint(B @ px[ff].T.astype(np.float32)).astype(np.int32)   # (S, F)
    row = np.rint(B @ py[ff].T.astype(np.float32)).astype(np.int32)
    dep = B @ P[ff, 2].T.astype(np.float32)
    pix = (row * W + col).ravel()
    dep = dep.ravel()
    order = np.lexsort((-dep, pix))
    pix_s = pix[order]
    first = np.ones(len(pix_s), bool)
    first[1:] = pix_s[1:] != pix_s[:-1]
    win = order[first]
    wpix = pix_s[first]
    s_idx, f_idx = np.divmod(win, ff.shape[0])

    vid = np.full((H * W, 3), -1, np.int32)
    wts = np.zeros((H * W, 3), np.float32)
    zb = np.full(H * W, -np.inf, np.float32)
    vid[wpix] = ff[f_idx]
    wts[wpix] = B[s_idx]
    zb[wpix] = dep[win]

    # close pinholes left by sliver triangles: copy the nearest covered pixel
    cov = (vid[:, 0] >= 0).reshape(H, W)
    # (enclosed holes of any size: small defects in the pial mesh would
    # otherwise show straight through to the white background)
    filled = ndimage.binary_fill_holes(cov) | (ndimage.binary_closing(cov, iterations=2) & ndimage.binary_dilation(cov))
    if (filled & ~cov).any():
        _, (ri, ci) = ndimage.distance_transform_edt(~cov, return_indices=True)
        src = (ri * W + ci).ravel()
        tgt = np.flatnonzero((filled & ~cov).ravel())
        vid[tgt] = vid[src[tgt]]
        wts[tgt] = wts[src[tgt]]
        zb[tgt] = zb[src[tgt]]
    mask = filled.ravel()

    # static cortex: sulcal-depth gray x Lambert lighting from upper-front-left
    nrm = np.einsum('pk,pkd->pd', wts[mask], vn[vid[mask]])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    light = toward + 0.45 * up - 0.35 * right
    light /= np.linalg.norm(light)
    lam = np.clip(nrm @ light, 0, 1)
    s = np.einsum('pk,pk->p', wts[mask], sulc[vid[mask]])
    gray = 0.80 - 0.22 * (0.5 + 0.5 * np.tanh(s / 2.0))
    shade = 0.30 + 0.70 * lam
    base = np.ones((H * W, 3), np.float32)
    base[mask] = (gray * shade)[:, None]

    return dict(H=H, W=W, mask=mask, vid=vid[mask], wts=wts[mask], shade=shade,
                base=base, zb=zb, right=right, up=up, toward=toward,
                u0=u0, w1=w1, pad=pad)


def _vertex_weights(verts, hemi_sign, vox):
    """Sparse Gaussian map voxel -> vertex, restricted to the vertex's hemisphere."""
    tree = cKDTree(vox)
    k = 8
    d, j = tree.query(verts, k=k)
    w = np.exp(-0.5 * (d / MAP_SIGMA_MM) ** 2)
    vx = vox[j, 0]
    w[(vx * hemi_sign) < 0] = 0.0          # voxel on the other side of the midline
    w[d > MAP_MAXDIST_MM] = 0.0
    tot = w.sum(axis=1)
    ok = tot > 1e-6
    w[ok] /= tot[ok, None]
    return j, w, ok


def _geometry(vox):
    """Everything that does not depend on the component. Built once."""
    key = ('geom', vox.shape[0], float(vox.sum()))
    if key in _cache:
        return _cache[key]
    surf = _load()
    maps = {}
    for h, sign in (('lh', -1), ('rh', 1)):
        maps[h] = _vertex_weights(surf[h]['v'], sign, vox)
    views = []
    for name, hemis, toward, up, lr in _VIEWS:
        if len(hemis) == 1:
            s = surf[hemis[0]]
            v, f, vn, sulc = s['v'], s['f'], s['n'], s['sulc']
            j = maps[hemis[0]][0]; w = maps[hemis[0]][1]; ok = maps[hemis[0]][2]
        else:
            a, b = surf['lh'], surf['rh']
            off = len(a['v'])
            v = np.vstack([a['v'], b['v']]); f = np.vstack([a['f'], b['f'] + off])
            vn = np.vstack([a['n'], b['n']]); sulc = np.concatenate([a['sulc'], b['sulc']])
            j = np.vstack([maps['lh'][0], maps['rh'][0]])
            w = np.vstack([maps['lh'][1], maps['rh'][1]])
            ok = np.concatenate([maps['lh'][2], maps['rh'][2]])
        r = _rasterize(v, f, vn, sulc, toward, up)
        r.update(name=name, lr=lr, j=j, w=w, ok=ok)
        views.append(r)
    geom = dict(views=views, surf=surf)
    _cache[key] = geom
    return geom


def _thresholds(csd_norm):
    lo = max(THR_FLOOR, float(np.percentile(csd_norm, THR_PCT)))
    lo = min(lo, 0.90)
    return lo, min(lo + THR_FADE, 0.98)


def _heat(v, lo, hi):
    a = np.clip((v - lo) / (hi - lo), 0, 1)
    c = HEAT(np.clip((v - lo) / (1 - lo), 0, 1))[..., :3]
    return c, a


def _render_view(r, csd_norm, peak_xyz, lo, hi):
    vv = (r['w'] * csd_norm[r['j']]).sum(axis=1)          # per-vertex value
    vv[~r['ok']] = np.nan
    pv = np.einsum('pk,pk->p', r['wts'], np.nan_to_num(vv[r['vid']], nan=0.0))
    c, a = _heat(pv, lo, hi)
    lit = (0.55 + 0.45 * r['shade'])[:, None]
    img = r['base'].copy()
    m = r['mask']
    img[m] = img[m] * (1 - a[:, None]) + (c * lit) * a[:, None]
    img = img.reshape(r['H'], r['W'], 3)

    # peak voxel: mark it only where it lies just under the visible surface
    p = np.asarray(peak_xyz, float)
    pc = (p @ r['right'] - r['u0']) * PX_PER_MM + r['pad']
    pr = (r['w1'] - p @ r['up']) * PX_PER_MM + r['pad']
    ci, ri = int(round(pc)), int(round(pr))
    marker = None
    if 0 <= ri < r['H'] and 0 <= ci < r['W']:
        z = r['zb'][ri * r['W'] + ci]
        under = z - p @ r['toward']        # > 0: peak lies behind the visible surface
        # tolerance both ways: the grid (MNI152) and fsaverage pial (MNI305) differ by mm
        if np.isfinite(z) and -10.0 < under < 20.0:
            marker = (pc, pr)
    return img, marker


# ------------------------------------------------------------------- slices
def _plane_segments(v, f, axis, c):
    d = v[:, axis] - c
    df = d[f]
    hit = (df.min(axis=1) < 0) & (df.max(axis=1) > 0)
    tri = f[hit]; dt = df[hit]
    segs = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        cross = (dt[:, a] * dt[:, b]) < 0
        t = dt[:, a] / (dt[:, a] - dt[:, b] + 1e-12)
        pt = v[tri[:, a]] + t[:, None] * (v[tri[:, b]] - v[tri[:, a]])
        segs.append((cross, pt))
    # every crossing triangle has exactly two crossing edges
    pts = np.full((len(tri), 2, 3), np.nan)
    cnt = np.zeros(len(tri), int)
    for cross, pt in segs:
        pts[cross, np.minimum(cnt[cross], 1)] = pt[cross]
        cnt += cross
    return pts[cnt == 2]


def _draw_slice(ax, vol, lo, thr, surf, axis, peak, dip, title, hlab, vlab):
    # slice axes: (horizontal world axis, vertical world axis)
    hv = {2: (0, 1), 1: (0, 2), 0: (1, 2)}[axis]
    k = int(round((peak[axis] - lo[axis]) / VOXEL_MM))
    sl = np.take(vol, k, axis=axis)                       # dims ordered x,y,z minus axis
    img = sl.T                                            # rows = vertical axis
    # The sLORETA grid is gray-matter only, so a raw slice is a ragged lattice.
    # Normalised convolution (smooth the values and the support separately,
    # then divide) gives a continuous field without diluting it at the edges.
    msk = np.isfinite(img).astype(float)
    num = ndimage.gaussian_filter(np.nan_to_num(img), 0.8)
    den = ndimage.gaussian_filter(msk, 0.8)
    img = np.where(den > 1e-3, num / np.maximum(den, 1e-3), 0.0)
    z = 6
    val = ndimage.zoom(img, z, order=3)
    mk = ndimage.zoom(den, z, order=1) / max(den.max(), 1e-6)
    h0 = lo[hv[0]] - VOXEL_MM / 2; h1 = h0 + img.shape[1] * VOXEL_MM
    v0 = lo[hv[1]] - VOXEL_MM / 2; v1 = v0 + img.shape[0] * VOXEL_MM
    ext = [h0, h1, v0, v1]

    rgba = np.ones(val.shape + (4,))
    rgba[..., :3] = 1.0
    gm = mk > 0.22
    rgba[gm, :3] = 0.93
    col, a = _heat(val, *thr)
    a = a * gm
    rgba[..., :3] = rgba[..., :3] * (1 - a[..., None]) + col * a[..., None]
    ax.imshow(rgba, origin='lower', extent=ext, interpolation='bilinear')

    for h in ('lh', 'rh'):
        for key_v, key_f, colr, lw in (('vw', 'fw', '#9a9a9a', 0.6), ('v', 'f', '#3a3a3a', 0.8)):
            seg = _plane_segments(surf[h][key_v], surf[h][key_f], axis, peak[axis])
            if len(seg):
                ax.add_collection(LineCollection(seg[:, :, list(hv)], colors=colr, linewidths=lw))

    ax.axhline(peak[hv[1]], color='#1f78b4', lw=0.7, ls='--')
    ax.axvline(peak[hv[0]], color='#1f78b4', lw=0.7, ls='--')
    d2 = np.array([dip[hv[0]], dip[hv[1]]])
    if np.linalg.norm(d2) > 0.05:
        L = 28.0 * d2
        ax.annotate('', xy=(peak[hv[0]] + L[0], peak[hv[1]] + L[1]),
                    xytext=(peak[hv[0]], peak[hv[1]]),
                    arrowprops=dict(arrowstyle='-|>', color='#00a2ff', lw=2.0, mutation_scale=14))
    ax.plot(peak[hv[0]], peak[hv[1]], 'o', ms=6, mfc='none', mec='#00a2ff', mew=1.8)

    ax.set_xlim(-78, 78) if hv[0] == 0 else ax.set_xlim(-112, 80)
    ax.set_ylim(-112, 80) if hv[1] == 1 else ax.set_ylim(-60, 85)
    ax.set_aspect('equal')
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title(title, fontsize=11, color='#222')
    kw = dict(transform=ax.transAxes, fontsize=11, fontweight='bold', color='#555')
    ax.text(0.01, 0.5, hlab[0], ha='left', va='center', **kw)
    ax.text(0.99, 0.5, hlab[1], ha='right', va='center', **kw)
    ax.text(0.5, 0.99, vlab[1], ha='center', va='top', **kw)
    ax.text(0.5, 0.01, vlab[0], ha='center', va='bottom', **kw)


# --------------------------------------------------------------------- page
def render_source_page(source_point, location_matrix, max_value, max_index,
                       reshaped_list, voxel_csd, out_png, title=None, label=None, dpi=120):
    """Write the source-localization page for one ICA component to `out_png`.

    Arguments are exactly what dummy_gui() returns / dummy_brain() receives.
    `label` is the small study line printed at the top of the other cascade
    pages ("BMrICA: <de-identified file name> <date>"); pass it already
    de-identified -- it is drawn as given.
    """
    vox = np.asarray(location_matrix[:, 0:3], dtype=float)
    csd = np.asarray(voxel_csd, dtype=float)
    cmax = csd.max() if csd.max() > 0 else 1.0
    csd_n = csd / cmax
    peak = np.asarray([float(c) for c in source_point[:3]])
    dvec = np.asarray(reshaped_list[max_index, :], dtype=float)
    dip = dvec / (np.linalg.norm(dvec) + 1e-12)

    geom = _geometry(vox)
    thr = _thresholds(csd_n)
    surf = geom['surf']

    lo = vox.min(axis=0)
    shape = np.rint((vox.max(axis=0) - lo) / VOXEL_MM).astype(int) + 1
    vol = np.full(shape, np.nan)
    ii = np.rint((vox - lo) / VOXEL_MM).astype(int)
    vol[ii[:, 0], ii[:, 1], ii[:, 2]] = csd_n

    fig = plt.Figure(figsize=(14.85, 10.5), dpi=dpi, facecolor='white')
    FigureCanvasAgg(fig)
    gs = GridSpec(3, 4, figure=fig, left=0.015, right=0.985, top=0.89, bottom=0.02,
                  wspace=0.04, hspace=0.12, width_ratios=[1, 1, 1, 0.92],
                  height_ratios=[1, 1, 1.05])

    lobe, region, area = (list(source_point[3:6]) + ['', '', ''])[:3]
    hemi = 'Left hemisphere' if peak[0] < 0 else ('Right hemisphere' if peak[0] > 0 else 'Midline')
    if label:
        fig.text(0.015, 0.99, label, fontsize=9, color='#222', va='top')
    fig.text(0.015, 0.955, title or 'Source Localization', fontsize=18, fontweight='bold',
             color='#1a1a1a', va='center')
    fig.text(0.015, 0.922, f'sLORETA current density  —  peak: {lobe}, {region}, {area}',
             fontsize=12.5, color='#333', va='center')

    for i, r in enumerate(geom['views']):
        ax = fig.add_subplot(gs[i // 3, i % 3])
        img, marker = _render_view(r, csd_n, peak, *thr)
        ax.imshow(img, interpolation='antialiased')
        if marker is not None:
            ax.plot(*marker, 'o', ms=9, mfc='none', mec='#00a2ff', mew=2)
        ax.set_axis_off()
        ax.set_title(r['name'], fontsize=11, color='#222', pad=2)
        kw = dict(transform=ax.transAxes, fontsize=10, fontweight='bold', color='#777')
        ax.text(0.0, 0.03, r['lr'][0], ha='left', va='bottom', **kw)
        ax.text(1.0, 0.03, r['lr'][1], ha='right', va='bottom', **kw)

    _draw_slice(fig.add_subplot(gs[2, 0]), vol, lo, thr, surf, 2, peak, dip,
                f'Axial  z = {peak[2]:+.0f} mm', ('L', 'R'), ('P', 'A'))
    _draw_slice(fig.add_subplot(gs[2, 1]), vol, lo, thr, surf, 1, peak, dip,
                f'Coronal  y = {peak[1]:+.0f} mm', ('L', 'R'), ('I', 'S'))
    _draw_slice(fig.add_subplot(gs[2, 2]), vol, lo, thr, surf, 0, peak, dip,
                f'Sagittal  x = {peak[0]:+.0f} mm', ('P', 'A'), ('I', 'S'))

    # --- info column
    ax = fig.add_subplot(gs[0:2, 3]); ax.set_axis_off()
    n50 = int((csd_n >= 0.5).sum()); n80 = int((csd_n >= 0.8).sum())
    cen = (vox[csd_n >= 0.5] * csd_n[csd_n >= 0.5, None]).sum(0) / csd_n[csd_n >= 0.5].sum()
    lines = [
        ('Peak source', None),
        ('Lobe', lobe), ('Region', region), ('Area', area), ('Side', hemi),
        ('MNI (x, y, z)', f'{peak[0]:+.0f}, {peak[1]:+.0f}, {peak[2]:+.0f} mm'),
        ('', ''),
        ('Distribution', None),
        ('Voxels ≥ 50% max', f'{n50}  ({n50 * 0.125:.0f} cm³)'),
        ('Voxels ≥ 80% max', f'{n80}  ({n80 * 0.125:.0f} cm³)'),
        ('Centroid ≥ 50%', f'{cen[0]:+.0f}, {cen[1]:+.0f}, {cen[2]:+.0f} mm'),
        ('', ''),
        ('Dipole at peak', None),
        ('Direction', f'{dip[0]:+.2f}, {dip[1]:+.2f}, {dip[2]:+.2f}'),
        ('Magnitude', f'{max_value:.4g}'),
    ]
    y = 0.97
    for k, val in lines:
        if val is None:
            ax.text(0.04, y, k, fontsize=13, fontweight='bold', color='#1a1a1a', transform=ax.transAxes)
            y -= 0.055
        elif k == '':
            y -= 0.025
        else:
            ax.text(0.04, y, k, fontsize=10.5, color='#666', transform=ax.transAxes)
            ax.text(0.04, y - 0.033, val, fontsize=11.5, color='#111', transform=ax.transAxes)
            y -= 0.075

    cax = fig.add_axes([0.775, 0.30, 0.19, 0.018])
    grad = np.linspace(thr[0], 1, 256)[None, :]
    rgb, a = _heat(grad, *thr)
    cax.imshow(rgb * a[..., None] + 0.86 * (1 - a[..., None]), aspect='auto',
               extent=[thr[0] * 100, 100, 0, 1])
    cax.set_yticks([])
    ticks = sorted({round(thr[0] * 100), round((thr[0] + 1) * 50), 100})
    cax.set_xticks(ticks)
    cax.set_xticklabels([f'{t}' for t in ticks[:-1]] + ['100%'], fontsize=9)
    cax.set_title('Current density, % of component peak', fontsize=9.5, color='#333')
    n_col = int((csd_n >= thr[0]).sum())
    fig.text(0.775, 0.262, f'Coloured: {n_col} voxels ({100 * n_col / len(csd_n):.0f}% of grid) '
             f'≥ {thr[0] * 100:.0f}% of peak', fontsize=8.5, color='#444')

    fig.text(0.775, 0.225,
             'Circle / crosshair: peak voxel.  Arrow: dipole\n'
             'direction at the peak, projected into the slice.\n'
             'Cortex: fsaverage pial surface, sulci darker.\n'
             'Views are neurological (L on the left) except\n'
             'Ventral, which is seen from below.',
             fontsize=8.5, color='#666', va='top', linespacing=1.4)

    fig.savefig(out_png, dpi=dpi, facecolor='white')
    return str(source_point[3:])
