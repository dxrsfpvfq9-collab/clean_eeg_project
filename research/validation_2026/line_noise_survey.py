"""Survey 60 Hz line-noise contamination across the archive of Brain Panel
`.icale.rep.pdf` reports.

Two independent measures are pulled from each report:

1. **Page 1, "Diffuse 60Hz" row** -- the panel metric, with its Value, the
   database mean (Typ), the Z-Score and the normal Range. "Excess" is taken
   as Z >= 2 (the report's own out-of-bounds convention).

2. **Page 3, spectral energy display** -- the 19 overlaid channel spectra are
   recovered by measuring the plot's *pixels*. The FFT panel is embedded in
   the PDF as a 1200x1500 PNG (matplotlib figsize 12x15 @ 100 dpi), so the
   original raster is extracted losslessly and the curve envelope is read off
   it. From the envelope we take the peak at 60 Hz (mains) and at 16 Hz --
   the alias of 240 Hz (4th harmonic of 60 Hz) sampled at 256 S/s, since
   |240 - 256| = 16.

Plot geometry (files/create_report_pdf.py, "FFT PLOTTING" block)
---------------------------------------------------------------
    x = start + 40*f          with start = 20   ->  40 px-data per Hz
    y = y_min + 100 + amp/5   with y_min = -1000 ->  baseline (amp=0) at -900

    ax.axis('off'), so the only fiducials are the drawn axis furniture:
      * horizontal axis line at y = -920, spanning x = 20 .. 2580
      * seven tick marks at x = 20 + 400*i (i.e. f = 0,10,...,60 Hz),
        each running from y = -920 down to y = -950

Because the figure uses matplotlib's default subplot geometry and default
5% autoscale margins, and because the lowest drawn artist is always the
tick bottom at y = -950, the pixel row of y = -950 is a CONSTANT:

    row(-950) = 1335 - 0.05*R * (1155 / (1.1*R)) = 1335 - 52.5 = 1282.5

independent of the amplitude scale. (Verified empirically: measured
1282-1283 on every report in the archive.) That fixes the y origin; the
y *scale* then follows from the axis line, which is 30 data-units above it:

    k = (1282.5 - axis_row) / 30          [pixels per data-unit]
    amp(row) = 5 * (baseline_row - row) / k,  baseline_row = 1282.5 - 50*k

The x scale is taken from the seven ticks directly (least-squares fit), and
cross-checks against the 847-px axis-line length on every file.

Amplitude units
---------------
`myvisualsigs` is RMS-normalised to std = 10 over the whole record
(edftotextbynameplotproc.py:568) *before* the page-3 FFT is computed, so
these amplitudes are RELATIVE -- they express how much of a record's own
1.5-45 Hz energy sits at a given frequency, not absolute microvolts. The
report's clinical paragraph converts them with uV = sqrt(amp)/2, and we
report that same pseudo-microvolt figure so the numbers are directly
comparable to the "N-M uV alpha" sentence on page 3.

Caveat: the visual band-pass is 1.5-45 Hz, so the *displayed* 60 Hz peak is
attenuated by roughly 10 dB relative to the true mains amplitude. The 16 Hz
alias, by contrast, lands inside the pass-band and is shown at full strength.

Usage
-----
    py line_noise_survey.py [--root DIR] [--out DIR] [--jobs N] [--limit N]
"""
import argparse
import io
import os
import re
import csv
import math

import numpy as np
from PIL import Image
from scipy import ndimage

import fitz  # PyMuPDF

# --------------------------------------------------------------------------
# page-1 metric table
# --------------------------------------------------------------------------

# Canonical 48-metric order; must match panel_parser.NAME_STRINGS.
NAME_STRINGS = [
    'STD Raw', 'Global STD', 'PDR Symmetry', 'PDR Synchrony', 'PDR Regulation',
    'PDR Magnitude', 'PDR Sinusoidal', 'PDR Max Post.', 'PDR FFT Width',
    'PDR Max Amplitude', 'PDR Burst Width', 'Beta Max Front', 'Front Alpha Asym',
    'XS Temp. Alpha', 'Alpha Speed', 'Alpha Peak', 'Midline Beta',
    'Focal Delta Index', 'Focal Delta Amp.', 'Focal Theta Index',
    'Focal Theta Amp.', 'Focal HiBeta Index', 'Focal HiBeta Amp.',
    'Focal Beta Index', 'Focal Beta Amp.', 'Frontal Delta', 'Frontal Theta',
    'Frontal Gamma', 'Front Gamma Asym', 'Diffuse Delta', 'Diffuse Theta',
    'Diffuse Hibeta', 'Diffuse Beta', 'Diffuse Gamma', 'Diffuse 60Hz',
    'Fractal Dimension', 'PDR Moment 1', 'PDR Moment 2', 'PDR Moment 3',
    'Beta Moment 1', 'Beta Moment 2', 'Beta Moment 3', 'Theta Moment 1',
    'Theta Moment 2', 'Theta Moment 3', 'Delta Moment 1', 'Delta Moment 2',
    'Delta Moment 3',
]
IDX_60HZ = NAME_STRINGS.index('Diffuse 60Hz')

_NUM_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_RANGE_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)-([+-]?\d+(?:\.\d+)?)$")
_WS_RE = re.compile(r"\s+")
_DB_RE = re.compile(r"Database Used:\s*(\S+)")
_NFILES_RE = re.compile(r"Number of files:\s*(\d+)")


def _classify_version(header, database, n_files, has_z):
    if not has_z:
        return "legacy2013_noZ"
    if not (database.startswith("EC_191") and n_files == "192"):
        return "other_db"
    return "v2025_brainml" if "BrainML" in header else "v2023_autoscan_192"


def parse_page1(doc):
    """Pull the 48-row metric table (values + z-scores) off page 1/2."""
    text = "\n".join(doc[i].get_text() for i in range(min(2, doc.page_count)))
    lines = [_WS_RE.sub(" ", l.strip()) for l in text.splitlines() if l.strip()]
    name_set = set(NAME_STRINGS)
    has_z = "Z-Score" in text

    out = {
        "header": lines[0] if lines else "",
        "database": (_DB_RE.search(text).group(1) if _DB_RE.search(text) else "?"),
        "n_files": (_NFILES_RE.search(text).group(1) if _NFILES_RE.search(text) else "?"),
        "n_parsed": 0,
        "z": [math.nan] * 48,
        "val": [math.nan] * 48,
        "typ": [math.nan] * 48,
        "rng_lo": math.nan,
        "rng_hi": math.nan,
    }
    out["version"] = _classify_version(out["header"], out["database"],
                                       out["n_files"], has_z)

    cursor = 0
    for mi, name in enumerate(NAME_STRINGS):
        idx = None
        for j in range(cursor, len(lines)):
            if lines[j] == name:
                idx = j
                break
        if idx is None:
            continue
        nums, k = [], idx + 1
        while k < len(lines) and len(nums) < 3:
            cell = lines[k]
            if cell in name_set:
                break
            if _NUM_RE.match(cell):
                nums.append(float(cell))
            k += 1
        if len(nums) == 3:
            out["val"][mi], out["typ"][mi], out["z"][mi] = nums
            out["n_parsed"] += 1
            if mi == IDX_60HZ:
                # the 4th cell on the row is the normal Range "lo-hi"
                while k < len(lines) and lines[k] not in name_set:
                    m = _RANGE_RE.match(lines[k])
                    if m:
                        out["rng_lo"], out["rng_hi"] = float(m.group(1)), float(m.group(2))
                        break
                    k += 1
        cursor = idx + 1
    return out


# --------------------------------------------------------------------------
# page-3 spectrum
# --------------------------------------------------------------------------

ROW_NEG950 = 1282.5     # pixel row of data y = -950 (see module docstring)
MIN_COMPONENT_WIDTH = 150   # px; curves span the plot, glyphs/ticks do not


def _find_spectrum_png(doc):
    """Return the 1200x1500 FFT raster from the last page, as an RGB array."""
    for pno in range(doc.page_count - 1, -1, -1):
        for im in doc[pno].get_images(full=True):
            info = doc.extract_image(im[0])
            if info["width"] == 1200 and info["height"] == 1500:
                return np.asarray(
                    Image.open(io.BytesIO(info["image"])).convert("RGB")
                ).astype(np.int16)
    return None


def _calibrate(gray):
    """Return (px_per_hz, x0_px, k, baseline_row) or None."""
    black = gray < 200
    counts = black.sum(1)
    axis_row = int(np.argmax(counts))
    if counts[axis_row] < 700:           # no recognisable axis line
        return None

    # tick x-positions, probed just below the axis line
    probe_row = axis_row + 8
    if probe_row >= black.shape[0]:
        return None
    cols = np.where(black[probe_row])[0]
    if len(cols) < 7:
        return None
    groups, cur = [], [cols[0]]
    for c in cols[1:]:
        if c - cur[-1] <= 3:
            cur.append(c)
        else:
            groups.append(cur)
            cur = [c]
    groups.append(cur)
    if len(groups) != 7:
        return None
    tick_x = np.array([np.mean(g) for g in groups])

    slope, intercept = np.polyfit(np.arange(7) * 10.0, tick_x, 1)
    if not (12.0 < slope < 14.5):        # sanity: expected ~13.22 px/Hz
        return None

    # sub-pixel centre of the axis line (darkness-weighted, away from ticks)
    lo, hi = max(0, axis_row - 4), min(gray.shape[0], axis_row + 5)
    band = gray[lo:hi, int(tick_x[0]) + 30:int(tick_x[-1]) - 30]
    w = np.clip(765 - band, 0, None).sum(1).astype(float)
    axis_c = (np.arange(lo, hi) * w).sum() / w.sum() if w.sum() > 0 else float(axis_row)

    k = (ROW_NEG950 - axis_c) / 30.0     # px per data-unit
    if not (0.05 < k < 40.0):
        return None
    baseline_row = ROW_NEG950 - 50.0 * k
    return slope, intercept, k, baseline_row


def _envelope(rgb, calib):
    """Topmost spectral-curve amplitude per pixel column (data units)."""
    slope, x0, k, baseline_row = calib
    gray = rgb.sum(2)
    nonwhite = gray < 730

    top = 150
    bot = int(math.floor(baseline_row)) + 1
    region = nonwhite[top:bot, :]

    # Drop the per-channel legend text, the "Alpha1/2" rail labels and the
    # black alpha peak-marker ticks: the spectral curves each span most of
    # the plot width, every other artist is narrow.
    lab, nlab = ndimage.label(region, structure=np.ones((3, 3), int))
    if nlab == 0:
        return None
    keep = np.zeros(nlab + 1, bool)
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl is not None and (sl[1].stop - sl[1].start) >= MIN_COMPONENT_WIDTH:
            keep[i] = True
    mask = keep[lab]
    if not mask.any():
        return None

    # topmost set row per column -> amplitude above the curve baseline
    has = mask.any(0)
    first = np.argmax(mask, axis=0).astype(float) + top
    amp = np.where(has, 5.0 * (baseline_row - first) / k, np.nan)
    return amp


def _band(amp, calib, f_lo, f_hi, how="max"):
    slope, x0 = calib[0], calib[1]
    a = int(round(x0 + slope * f_lo))
    b = int(round(x0 + slope * f_hi))
    a, b = max(0, a), min(len(amp), b + 1)
    if b <= a:
        return math.nan
    seg = amp[a:b]
    seg = seg[~np.isnan(seg)]
    if seg.size == 0:
        return math.nan
    return float(np.nanmax(seg)) if how == "max" else float(np.nanmedian(seg))


def _peak_features(amp, calib, f_c, lo_band, hi_band, half_width):
    """Characterise a spectral line near f_c.

    Returns (peak_amp, local_background, prominence_ratio, peak_hz, fwhm_hz).

    `fwhm_hz` is the width of the excursion at half the peak's height above
    the local background, measured by walking outward from the peak. It
    separates a genuine mains line (narrow, well under 1 Hz) from a broad
    physiological hump that happens to sit at the same centre frequency.
    """
    slope, x0 = calib[0], calib[1]
    a = max(0, int(round(x0 + slope * (f_c - half_width))))
    b = min(len(amp), int(round(x0 + slope * (f_c + half_width))) + 1)
    nan = (math.nan,) * 5
    if b <= a:
        return nan
    seg = amp[a:b]
    if not np.isfinite(seg).any():
        return nan
    j = int(np.nanargmax(seg))
    pk = float(seg[j])
    pk_i = a + j
    pk_hz = (pk_i - x0) / slope

    sl = _band(amp, calib, *lo_band, how="median")
    sh = _band(amp, calib, *hi_band, how="median")
    if math.isnan(sl) and math.isnan(sh):
        base = math.nan
    elif math.isnan(sl):
        base = sh
    elif math.isnan(sh):
        base = sl
    else:
        # linear interpolation of the local background across the line
        fl = 0.5 * (lo_band[0] + lo_band[1])
        fh = 0.5 * (hi_band[0] + hi_band[1])
        base = sl + (sh - sl) * (f_c - fl) / (fh - fl)
    ratio = pk / base if (base and base > 1e-9 and not math.isnan(pk)) else math.nan

    # half-height walk-out, bounded to the shoulder gap
    fwhm = math.nan
    if not math.isnan(base) and pk > base:
        half = base + 0.5 * (pk - base)
        lim_lo = max(0, int(round(x0 + slope * lo_band[1])))
        lim_hi = min(len(amp) - 1, int(round(x0 + slope * hi_band[0])))
        i = pk_i
        while i > lim_lo and np.isfinite(amp[i]) and amp[i] > half:
            i -= 1
        left = i
        i = pk_i
        while i < lim_hi and np.isfinite(amp[i]) and amp[i] > half:
            i += 1
        fwhm = (i - left) / slope
    return pk, base, ratio, pk_hz, fwhm


def analyse_spectrum(doc):
    rgb = _find_spectrum_png(doc)
    if rgb is None:
        return {"spec_ok": 0, "spec_err": "no 1200x1500 raster"}
    calib = _calibrate(rgb.sum(2))
    if calib is None:
        return {"spec_ok": 0, "spec_err": "calibration failed"}
    amp = _envelope(rgb, calib)
    if amp is None:
        return {"spec_ok": 0, "spec_err": "no curve found"}

    slope, x0, k, baseline_row = calib
    # 60 Hz mains. The 16 Hz window is deliberately wider and centred a
    # little low: the 240 Hz alias lands at |240 - fs|, so a sample clock a
    # fraction of a percent off nominal shifts it four times as far as it
    # shifts the 60 Hz line itself (observed range ~15.5-16.2 Hz).
    pk60, base60, r60, hz60, w60 = _peak_features(
        amp, calib, 60.0, (55.0, 58.0), (62.0, 63.5), 1.2)
    pk16, base16, r16, hz16, w16 = _peak_features(
        amp, calib, 15.9, (12.8, 14.6), (17.4, 18.8), 0.9)

    # global maximum of the envelope over the analysable band
    lo = int(round(x0 + slope * 1.5))
    hi = int(round(x0 + slope * 63.5))
    seg = amp[lo:hi]
    gmax = float(np.nanmax(seg)) if np.isfinite(seg).any() else math.nan
    gmax_f = ((np.nanargmax(seg) + lo) - x0) / slope if np.isfinite(seg).any() else math.nan

    def uv(a):
        return math.sqrt(a) / 2.0 if (a is not None and not math.isnan(a) and a > 0) else math.nan

    return {
        "spec_ok": 1,
        "spec_err": "",
        "px_per_hz": round(slope, 4),
        "k_px_per_unit": round(k, 4),
        "amp60": pk60, "base60": base60, "ratio60": r60, "uv60": uv(pk60),
        "hz60": hz60, "fwhm60": w60,
        "amp16": pk16, "base16": base16, "ratio16": r16, "uv16": uv(pk16),
        "hz16": hz16, "fwhm16": w16,
        "amp_max": gmax, "amp_max_hz": gmax_f, "uv_max": uv(gmax),
        "pct60_of_max": 100.0 * pk60 / gmax if (gmax and gmax > 0 and not math.isnan(pk60)) else math.nan,
        "pct16_of_max": 100.0 * pk16 / gmax if (gmax and gmax > 0 and not math.isnan(pk16)) else math.nan,
    }


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

FIELDS = [
    "path", "file", "folder", "version", "database", "n_files", "n_parsed",
    "d60_value", "d60_typ", "d60_z", "d60_rng_lo", "d60_rng_hi", "stdraw_value",
    "n_oob_total",
    "spec_ok", "spec_err", "px_per_hz", "k_px_per_unit",
    "amp60", "base60", "ratio60", "uv60", "pct60_of_max", "hz60", "fwhm60",
    "amp16", "base16", "ratio16", "uv16", "pct16_of_max", "hz16", "fwhm16",
    "amp_max", "amp_max_hz", "uv_max",
]


def analyse_one(path):
    row = {k: "" for k in FIELDS}
    row["path"] = path
    row["file"] = os.path.basename(path)
    row["folder"] = os.path.basename(os.path.dirname(path))
    try:
        doc = fitz.open(path)
    except Exception as exc:
        row["spec_ok"] = 0
        row["spec_err"] = f"open: {type(exc).__name__}"
        return row
    try:
        p1 = parse_page1(doc)
        row["version"] = p1["version"]
        row["database"] = p1["database"]
        row["n_files"] = p1["n_files"]
        row["n_parsed"] = p1["n_parsed"]
        row["d60_value"] = p1["val"][IDX_60HZ]
        row["d60_typ"] = p1["typ"][IDX_60HZ]
        row["d60_z"] = p1["z"][IDX_60HZ]
        row["d60_rng_lo"] = p1["rng_lo"]
        row["d60_rng_hi"] = p1["rng_hi"]
        row["stdraw_value"] = p1["val"][NAME_STRINGS.index("STD Raw")]
        zs = np.array(p1["z"], float)
        row["n_oob_total"] = int(np.sum(np.abs(zs) >= 2.0)) if np.isfinite(zs).any() else ""
    except Exception as exc:
        row["spec_err"] = f"page1: {type(exc).__name__}: {exc}"
    try:
        row.update({k: v for k, v in analyse_spectrum(doc).items() if k in FIELDS})
    except Exception as exc:
        row["spec_ok"] = 0
        row["spec_err"] = f"spec: {type(exc).__name__}: {exc}"
    finally:
        doc.close()
    return row


def find_reports(root):
    out = []
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith(".icale.rep.pdf"):
                out.append(os.path.join(dp, f))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    files = find_reports(args.root)
    if args.limit:
        files = files[:args.limit]
    print(f"{len(files)} reports under {args.root}", flush=True)

    rows = []
    if args.jobs > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            for i, r in enumerate(ex.map(analyse_one, files, chunksize=4), 1):
                rows.append(r)
                if i % 50 == 0:
                    print(f"  {i}/{len(files)}", flush=True)
    else:
        for i, p in enumerate(files, 1):
            rows.append(analyse_one(p))
            if i % 50 == 0:
                print(f"  {i}/{len(files)}", flush=True)

    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, "line_noise_survey.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("wrote", csv_path)


if __name__ == "__main__":
    main()
