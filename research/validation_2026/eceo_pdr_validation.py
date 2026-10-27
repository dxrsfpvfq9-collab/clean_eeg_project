# eceo_pdr_validation.py
# Which Brain Panel rows (and which cascade measures) track alpha blocking?
#
# Reference: EDF posterior alpha attenuation from tools/compare_studies.py
# (edf_reactivity: O1 O2 P3 P4, EC-peak +/- 2 Hz, median Welch). For every
# same-session EC/EO pair in the QA corpus, each panel row's EC->EO change is
# correlated (Spearman) with log10(EO/EC alpha power). Changes are taken two
# ways: difference (EO-EC, i.e. delta-z up to the row's DB std) and log ratio
# (only where both values are > 0).
#
# Pairs: same folder not required; same EDF patient field (compared, never
# printed), EC/EO by file name, start times <= 120 min apart, '.reviewed'
# re-runs skipped, each recording used once (closest partner wins).
#
# Usage:
#   py research/validation_2026/eceo_pdr_validation.py ["<root>"]
# Writes out/eceo_pdr_pairs.csv and out/eceo_pdr_validation.md

import os
import sys
import csv
import glob

import numpy as np
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import compare_studies as cs  # noqa: E402
from panel_parser import NAME_STRINGS  # noqa: E402

DEFAULT_ROOT = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
OUT = os.path.join(HERE, "out")


def find_pairs(root):
    recs = []
    for p in glob.glob(os.path.join(root, "**", "*.icale.rep.pdf"), recursive=True):
        base = p[:-len(".icale.rep.pdf")]
        if ".reviewed" in base.lower() or not os.path.exists(base + ".edf"):
            continue
        cond, t = cs.guess_condition(base), cs.edf_start(base + ".edf")
        if cond in ("EC", "EO") and t:
            with open(base + ".edf", "rb") as fh:
                pid = fh.read(88)[8:88].strip()
            if pid:
                recs.append((cond, t, base, pid))
    cands = []
    for e in (r for r in recs if r[0] == "EC"):
        for o in (r for r in recs if r[0] == "EO"):
            if e[3] == o[3]:
                gap = abs((o[1] - e[1]).total_seconds()) / 60.0
                if gap <= 120:
                    cands.append((gap, e[2], o[2]))
    cands.sort()
    used, pairs = set(), []
    for gap, ec, eo in cands:
        if ec not in used and eo not in used:
            used |= {ec, eo}
            pairs.append((ec, eo, gap))
    return pairs


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROOT
    pairs = find_pairs(root)
    print(f"same-session EC/EO pairs: {len(pairs)}")
    rows = []
    for i, (ec_b, eo_b, gap) in enumerate(pairs, 1):
        try:
            ec, eo = cs.load_study(ec_b + ".edf"), cs.load_study(eo_b + ".edf")
            r = cs.edf_reactivity(ec["edf"], eo["edf"])
        except (SystemExit, Exception) as exc:   # unparsable panel / unreadable EDF
            print(f"  skip pair {i}: {type(exc).__name__}")
            continue
        pec, peo, attn = r["all"]
        if not (pec > 0 and peo > 0):
            continue
        rec = {"pair": i, "gap_min": round(gap), "attn": attn, "lr_edf": np.log10(peo / pec),
               "rel_ec": r["rel"]["EC"], "rel_eo": r["rel"]["EO"], "paf_ec": r["paf"], "paf_eo": r["eo_paf"],
               "ec_gstd_prefix": ec["gstd_prefix"], "eo_gstd_prefix": eo["gstd_prefix"]}
        for k in range(48):
            rec[f"ec_{k}"], rec[f"eo_{k}"] = ec["values"][k], eo["values"][k]
        if ec["comps"] and eo["comps"]:
            A, B = cs.cascade_summary(ec["comps"]), cs.cascade_summary(eo["comps"])
            for key in ("alpha_post", "alpha_share", "alpha_pct"):
                rec[f"casc_{key}_ec"], rec[f"casc_{key}_eo"] = A[key], B[key]
        rows.append(rec)
        if i % 20 == 0:
            print(f"  {i}/{len(pairs)}")
    os.makedirs(OUT, exist_ok=True)
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k[:3] in ("ec_", "eo_"), k))
    with open(os.path.join(OUT, "eceo_pdr_pairs.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    y = np.array([r["lr_edf"] for r in rows])
    results = []

    def score(label, ec_v, eo_v, kind):
        ec_v, eo_v = np.asarray(ec_v, float), np.asarray(eo_v, float)
        ok = ~(np.isnan(ec_v) | np.isnan(eo_v))
        if kind == "ratio":
            ok &= (ec_v > 0) & (eo_v > 0)
            x = np.log10(np.where(ok, eo_v, 1) / np.where(ok, ec_v, 1))
        else:
            x = eo_v - ec_v
        if ok.sum() < 20 or np.nanstd(x[ok]) == 0:
            return
        rho, p = spearmanr(x[ok], y[ok])
        # direction agreement: blocked pairs (attn > 0) moving the row's majority way
        sgn = np.sign(rho)
        blocked = ok & (y < 0)
        agree = np.mean(np.sign(x[blocked]) == -sgn) if blocked.any() else np.nan
        results.append((label, kind, int(ok.sum()), rho, p, agree))

    gstd_ok = np.array([not (r["ec_gstd_prefix"] or r["eo_gstd_prefix"]) for r in rows])
    for k in range(48):
        ec_v = np.array([r[f"ec_{k}"] for r in rows])
        eo_v = np.array([r[f"eo_{k}"] for r in rows])
        if k == cs.GSTD_ROW:
            ec_v, eo_v = np.where(gstd_ok, ec_v, np.nan), np.where(gstd_ok, eo_v, np.nan)
        for kind in ("diff", "ratio"):
            score(f"panel: {NAME_STRINGS[k]}", ec_v, eo_v, kind)
    for key in ("alpha_post", "alpha_share", "alpha_pct"):
        ec_v = [r.get(f"casc_{key}_ec", np.nan) for r in rows]
        eo_v = [r.get(f"casc_{key}_eo", np.nan) for r in rows]
        score(f"cascade: {key}", ec_v, eo_v, "diff")
    score("EDF: relative alpha (share 1-30 Hz)", [r["rel_ec"] for r in rows], [r["rel_eo"] for r in rows], "ratio")

    results.sort(key=lambda t: -abs(t[3]))
    attn = np.array([r["attn"] for r in rows])
    lines = [
        "# Which panel / cascade measures track EC->EO alpha blocking?",
        "",
        f"{len(rows)} same-session EC/EO pairs (of {len(pairs)} found). Reference = EDF posterior alpha "
        "attenuation (O1 O2 P3 P4, EC peak +/- 2 Hz). Spearman rho of each measure's EC->EO change "
        "vs log10(EO/EC alpha power): POSITIVE rho = the measure falls when alpha blocks "
        "(negative = it rises, e.g. Fractal Dimension).",
        "",
        f"EDF attenuation across pairs: median {np.median(attn):.0f}%, IQR {np.percentile(attn, 25):.0f}-"
        f"{np.percentile(attn, 75):.0f}%, 10th pct {np.percentile(attn, 10):.0f}%, "
        f"{np.mean(attn < 0) * 100:.0f}% paradoxical (< 0).",
        "",
        "`agree` = among pairs with any blocking, share where the measure moved in its blocking direction.",
        "",
        "| measure | change | n | rho | p | agree |",
        "|---|---|---|---|---|---|",
    ]
    for label, kind, n, rho, p, agree in results:
        lines.append(f"| {label} | {kind} | {n} | {rho:+.2f} | {p:.1g} | {agree * 100:.0f}% |")
    md = "\n".join(lines) + "\n"
    with open(os.path.join(OUT, "eceo_pdr_validation.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    print(md)


if __name__ == "__main__":
    main()
