"""Summarise out/line_noise_survey.csv -> out/LINE_NOISE_60HZ.md + summary.json."""
import csv, json, os, re, math
import numpy as np
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
rows = list(csv.DictReader(open(os.path.join(OUT, "line_noise_survey.csv"), encoding="utf-8")))


def fv(r, k):
    try:
        return float(r[k])
    except Exception:
        return math.nan


def year_of(r):
    m = re.search(r"(20\d\d)", r["folder"])
    if m:
        return int(m.group(1))
    m = re.search(r"(20\d\d)", r["path"])
    return int(m.group(1)) if m else None


# ---- de-duplicate on report basename (same recording re-filed in several
# review folders); keep the first occurrence.
seen, uniq = set(), []
for r in rows:
    if r["file"] in seen:
        continue
    seen.add(r["file"])
    uniq.append(r)

S = {}
S["n_pdf_total"] = len(rows)
S["n_unique"] = len(uniq)
S["versions"] = dict(Counter(r["version"] for r in uniq))

# ==== 1. page-1 Diffuse 60Hz ==============================================
ec = [r for r in uniq if r["version"] in ("v2025_brainml", "v2023_autoscan_192")]
z = np.array([fv(r, "d60_z") for r in ec])
val = np.array([fv(r, "d60_value") for r in ec])
typ = np.array([fv(r, "d60_typ") for r in ec])
mz = np.isfinite(z)
S["panel"] = {
    "n": int(mz.sum()),
    "typ_db_mean": float(np.nanmedian(typ)),
    "rng_hi": float(np.nanmedian([fv(r, "d60_rng_hi") for r in ec])),
    "value_pcts": {str(p): float(np.nanpercentile(val[mz], p)) for p in (25, 50, 75, 90, 95, 99)},
    "z_pcts": {str(p): float(np.percentile(z[mz], p)) for p in (5, 25, 50, 75, 90, 95, 99)},
    "z_max": float(z[mz].max()),
    "frac": {str(t): float(np.mean(z[mz] >= t)) for t in (1, 1.5, 2, 3, 5, 10)},
    "n_ge": {str(t): int(np.sum(z[mz] >= t)) for t in (1, 1.5, 2, 3, 5, 10)},
}

# ==== 2. page-3 spectrum ==================================================
ok = [r for r in uniq if r["spec_ok"] == "1"]
r60 = np.array([fv(r, "ratio60") for r in ok])
p60 = np.array([fv(r, "pct60_of_max") for r in ok])
u60 = np.array([fv(r, "uv60") for r in ok])
h60 = np.array([fv(r, "hz60") for r in ok])
w60 = np.array([fv(r, "fwhm60") for r in ok])
r16 = np.array([fv(r, "ratio16") for r in ok])
u16 = np.array([fv(r, "uv16") for r in ok])
h16 = np.array([fv(r, "hz16") for r in ok])
w16 = np.array([fv(r, "fwhm16") for r in ok])
umax = np.array([fv(r, "uv_max") for r in ok])

DET = 2.0          # prominence ratio at which a line is called "present"
present = r60 >= DET


def band_of(i):
    if not (r60[i] >= DET):
        return "none"
    if p60[i] >= 99.99:
        return "dominant"
    if p60[i] >= 50:
        return "severe"
    if p60[i] >= 10:
        return "moderate"
    return "minor"


bands = [band_of(i) for i in range(len(ok))]
bc = Counter(bands)
ORDER = ["none", "minor", "moderate", "severe", "dominant"]
S["spec"] = {
    "n": len(ok),
    "bands": {b: bc.get(b, 0) for b in ORDER},
    "band_frac": {b: bc.get(b, 0) / len(ok) for b in ORDER},
    "frac_present": float(np.nanmean(present)),
    "ratio60_pcts": {str(p): float(np.nanpercentile(r60, p)) for p in (25, 50, 75, 90, 95, 99)},
    "pct60_pcts": {str(p): float(np.nanpercentile(p60, p)) for p in (25, 50, 75, 90, 95, 99)},
    "uv60_pcts": {str(p): float(np.nanpercentile(u60, p)) for p in (25, 50, 75, 90, 95, 99)},
    "uv60_max": float(np.nanmax(u60)),
    "hz60_median": float(np.nanmedian(h60[present])),
    "hz60_p05_p95": [float(np.nanpercentile(h60[present], 5)), float(np.nanpercentile(h60[present], 95))],
    "fwhm60_median": float(np.nanmedian(w60[present])),
    "uvmax_median": float(np.nanmedian(umax)),
}

# ---- 16 Hz alias
narrow = w16 < 1.2
S["alias16"] = {
    "n": len(ok),
    "ratio16_pcts": {str(p): float(np.nanpercentile(r16, p)) for p in (50, 75, 90, 95, 99)},
    "n_ge": {str(t): int(np.nansum(r16 >= t)) for t in (1.5, 2, 3, 5)},
    "frac_ge": {str(t): float(np.nanmean(r16 >= t)) for t in (1.5, 2, 3, 5)},
    "n_ge_narrow": {str(t): int(np.nansum((r16 >= t) & narrow)) for t in (1.5, 2, 3, 5)},
    "hz16_detected": [float(np.nanmin(h16[r16 >= 2])), float(np.nanmedian(h16[r16 >= 2])), float(np.nanmax(h16[r16 >= 2]))],
    "fwhm16_median_det": float(np.nanmedian(w16[r16 >= 2])),
    "uv16_pcts": {str(p): float(np.nanpercentile(u16, p)) for p in (50, 90, 99)},
}
# co-occurrence with heavy 60 Hz
hi16 = r16 >= 2
S["alias16"]["co_ratio60_ge10_when_alias"] = float(np.nanmean(r60[hi16] >= 10))
S["alias16"]["co_ratio60_ge10_baserate"] = float(np.nanmean(r60[~hi16] >= 10))
S["alias16"]["median_ratio60_when_alias"] = float(np.nanmedian(r60[hi16]))

# ==== 3. the two measures against each other ==============================
both = [r for r in ok if r["version"] in ("v2025_brainml", "v2023_autoscan_192") and np.isfinite(fv(r, "d60_z"))]
bz = np.array([fv(r, "d60_z") for r in both])
bp = np.array([fv(r, "pct60_of_max") for r in both])
br = np.array([fv(r, "ratio60") for r in both])
bsr = np.array([fv(r, "stdraw_value") for r in both])
bv = np.array([fv(r, "d60_value") for r in both])
S["cross"] = {
    "n": len(both),
    "panel_flags_z2": int(np.sum(bz >= 2)),
    "spec_flags_present": int(np.sum(br >= DET)),
    "spec_flags_mod_plus": int(np.sum((br >= DET) & (bp >= 10))),
    "both": int(np.sum((bz >= 2) & (br >= DET) & (bp >= 10))),
    "panel_only": int(np.sum((bz >= 2) & ~((br >= DET) & (bp >= 10)))),
    "spec_only": int(np.sum(~(bz >= 2) & ((br >= DET) & (bp >= 10)))),
}
o = np.argsort(br); rk = np.empty_like(o, float); rk[o] = np.arange(1, len(br) + 1)
y = bz >= 2
S["cross"]["auc_ratio60_vs_z2"] = float((rk[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum()))
hi = bz >= 10
S["cross"]["gain_group"] = {
    "n": int(hi.sum()),
    "stdraw_median_hi": float(np.nanmedian(bsr[hi])),
    "stdraw_median_rest": float(np.nanmedian(bsr[~hi])),
    "d60value_median_hi": float(np.nanmedian(bv[hi])),
    "d60value_median_rest": float(np.nanmedian(bv[~hi])),
}

# ==== 4. by review year ===================================================
byyear = defaultdict(list)
for i, r in enumerate(ok):
    yy = year_of(r)
    if yy and 2015 <= yy <= 2030:
        byyear[yy].append(i)
S["by_year"] = {
    str(yy): {
        "n": len(ix),
        "frac_present": float(np.nanmean(r60[ix] >= DET)),
        "frac_mod_plus": float(np.nanmean((r60[ix] >= DET) & (p60[ix] >= 10))),
        "median_pct60": float(np.nanmedian(p60[ix])),
    }
    for yy, ix in sorted(byyear.items()) if len(ix) >= 15
}

# ==== worst offenders =====================================================
idx = np.argsort(-np.nan_to_num(p60 * 1000 + np.minimum(r60, 999)))
S["worst"] = [
    {"file": ok[i]["file"], "folder": ok[i]["folder"], "ratio60": round(float(r60[i]), 1),
     "pct60": round(float(p60[i]), 1), "uv60": round(float(u60[i]), 1),
     "d60_z": ok[i]["d60_z"], "band": band_of(i)}
    for i in idx[:15]
]
S["alias_list"] = [
    {"file": ok[i]["file"], "ratio16": round(float(r16[i]), 2), "hz16": round(float(h16[i]), 2),
     "fwhm16": round(float(w16[i]), 2), "uv16": round(float(u16[i]), 1),
     "ratio60": round(float(r60[i]), 1), "d60_z": ok[i]["d60_z"]}
    for i in np.argsort(-np.nan_to_num(r16))[:15]
]

json.dump(S, open(os.path.join(OUT, "line_noise_summary.json"), "w"), indent=1)
print(json.dumps(S, indent=1))
