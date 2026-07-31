"""Targeted harvest: find EEG cases in the FULL QA archive whose Doctor's Report
reads as abnormal on a starved outcome (paroxysmal / clinical / pdr_freq), so
they can be added as rare-outcome POSITIVES.

Scans every Doctor's Report in out/reports_index.csv (whole corpus, not just the
99-case study cohort), derives the six outcomes with the current labels.py, and
for each abnormal case reports EC-panel availability, ML version, and whether it
is already in study_cohort.csv.

Output: out/abnormal_archive_candidates.csv  +  console summary.
"""
import csv, os, sys, re
import config, report_parser as rp, labels as L
import panel_parser as pp

def load(p):
    return list(csv.DictReader(open(p, encoding="utf-8")))

# Older (2022-2024) reports are space-corrupted ("N one." for "None.",
# "n o overt" for "no overt"), which defeats labels.py's substring negations and
# produces false positives. These robust detectors compact whitespace first.
def _compact(s):
    return re.sub(r"\s+", "", (s or "").lower()).replace("&gt;", ">").replace("&lt;", "<")

_PAROX_NEG = ("none", "no.", "n/a", "seebelow", "notapplicable", "")
_EPI_TERMS = ("sharp", "spike", "spikeandwave", "spike-and-wave", "epileptiform",
              "phasereversal", "paroxysm", "burstsofslow", "burst of", "polyspike",
              "generalized", "focalslow", "sharplycontoured", "3-4hz", "3hz")

def robust_paroxysmal(rep):
    """1 only if the paroxysmal field describes a real transient (not None/negation)."""
    raw = (rep.get("paroxysmal") or "")
    c = _compact(raw)
    if c.startswith("none") or c in _PAROX_NEG or c.startswith("no."):
        return 0
    if c.startswith("nooverte") or c.startswith("noepileptiform") or c.startswith("thoughno"):
        return 0
    return 1 if c else 0

_CLIN_NEG_STEMS = ("noovertabnormal", "noabnormalit", "noepileptiformabnormalit",
                   "nosignificantabnormal", "withoutabnormal", "nooverte",
                   "unremarkable", "normaleeg", "withinnormal", "nofocal")
_CLIN_POS_STEMS = ("abnormaleeg", "isabnormal", "anabnormal", "remarkablefor",
                   "epileptiform", "spikeandwave", "sharpwave", "phasereversal",
                   "focalslowing", "backgroundslowing", "slowingofbackground",
                   "dysreg", "asymmetr")

def robust_clinical(rep):
    c = _compact(rep.get("comments"))
    if any(s in c for s in _CLIN_POS_STEMS):
        # positive findings win even if a "no overt epileptiform" clause precedes
        return 1
    if any(s in c for s in _CLIN_NEG_STEMS):
        return 0
    return 0

def qeeg_of(fn):
    for t in fn.replace("_", " ").replace("-", " ").split():
        if t.isdigit() and len(t) == 4:
            return t
    return ""

def main():
    reports = load(os.path.join(config.OUT_DIR, "reports_index.csv"))
    panels  = load(os.path.join(config.OUT_DIR, "panels_index.csv"))
    cohort  = load(os.path.join(config.OUT_DIR, "study_cohort.csv"))
    cohort_keys = {r["patient_key"] for r in cohort}

    # panels by patient_key
    ec_by_key = {}
    for p in panels:
        if p["condition"] == "EC":
            ec_by_key.setdefault(p["patient_key"], []).append(p)

    # dedupe reports by patient_key (prefer the -rt version)
    best = {}
    for r in reports:
        k = r["patient_key"]
        if k not in best or (r.get("is_rt") == "True" and best[k].get("is_rt") != "True"):
            best[k] = r
    print(f"unique report-cases: {len(best)}  (from {len(reports)} report files)")

    rows = []
    n_parse_err = 0
    for i, (k, r) in enumerate(sorted(best.items()), 1):
        try:
            rep = rp.parse_report(r["path"])
        except Exception as exc:
            n_parse_err += 1
            continue
        ecs = ec_by_key.get(k, [])
        age = None
        for p in ecs:
            if p.get("age") not in ("", None):
                try: age = int(float(p["age"]))
                except Exception: pass
                break
        labs = {o: L.all_labels(rep, age)[o][0] for o in L.OUTCOMES}
        # space-robust overrides for the two corruption-prone outcomes
        labs["paroxysmal"] = robust_paroxysmal(rep)
        labs["clinical_abnorm"] = robust_clinical(rep)
        # keep only cases abnormal on a STARVED outcome
        if not (labs["paroxysmal"] or labs["clinical_abnorm"] or labs["pdr_freq_abnorm"]):
            continue
        ec = ecs[0] if ecs else None
        q = qeeg_of(r["filename"]) or (qeeg_of(ec["filename"]) if ec else "")
        rows.append({
            "qeeg": q,
            "patient_key": k,
            "year": r["year"],
            "session": r["session"],
            "age": age if age is not None else "",
            "paroxysmal": labs["paroxysmal"],
            "clinical_abnorm": labs["clinical_abnorm"],
            "pdr_freq_abnorm": labs["pdr_freq_abnorm"],
            "drowsiness": labs["drowsiness"],
            "artifact": labs["artifact"],
            "eeg_quality": labs["eeg_quality"],
            "has_ec_panel": bool(ec),
            "in_cohort": k in cohort_keys,
            "paroxysmal_txt": (rep.get("paroxysmal") or "").strip()[:80],
            "comments_txt": (rep.get("comments") or "").strip()[:100],
            "ec_panel_file": ec["filename"] if ec else "",
            "report_file": r["filename"],
            "ec_panel_path": ec["path"] if ec else "",
            "report_path": r["path"],
        })
        if i % 100 == 0:
            print(f"  scanned {i}/{len(best)} ...")

    # rank: paroxysmal first, then clinical, then pdr; usable (EC & not in cohort) on top
    def keyf(x):
        return (-(x["paroxysmal"]*4 + x["clinical_abnorm"]*2 + x["pdr_freq_abnorm"]),
                -(x["has_ec_panel"] and not x["in_cohort"]))
    rows.sort(key=keyf)

    fields = ["qeeg","patient_key","year","session","age","paroxysmal",
              "clinical_abnorm","pdr_freq_abnorm","drowsiness","artifact",
              "eeg_quality","has_ec_panel","in_cohort","paroxysmal_txt",
              "comments_txt","ec_panel_file","report_file","ec_panel_path",
              "report_path"]
    out = os.path.join(config.OUT_DIR, "abnormal_archive_candidates.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

    # ---- summary
    def cnt(pred): return sum(1 for x in rows if pred(x))
    par = cnt(lambda x: x["paroxysmal"])
    clin = cnt(lambda x: x["clinical_abnorm"])
    pdr = cnt(lambda x: x["pdr_freq_abnorm"])
    par_new = cnt(lambda x: x["paroxysmal"] and x["has_ec_panel"] and not x["in_cohort"])
    clin_new = cnt(lambda x: x["clinical_abnorm"] and x["has_ec_panel"] and not x["in_cohort"])
    pdr_new = cnt(lambda x: x["pdr_freq_abnorm"] and x["has_ec_panel"] and not x["in_cohort"])
    print(f"\nparse errors: {n_parse_err}")
    print(f"abnormal cases found: {len(rows)}")
    print(f"  paroxysmal positives : {par}   (with EC panel & NOT already in cohort: {par_new})")
    print(f"  clinical positives   : {clin}   (new & usable: {clin_new})")
    print(f"  pdr_freq positives   : {pdr}   (new & usable: {pdr_new})")
    print(f"\nTop paroxysmal candidates (new & usable):")
    for x in rows:
        if x["paroxysmal"] and x["has_ec_panel"] and not x["in_cohort"]:
            print(f"  {x['qeeg'] or x['patient_key'][:8]:10s} {x['session'][:22]:22s} "
                  f"par='{x['paroxysmal_txt'][:50]}'")
    print(f"\n-> {out}")

if __name__ == "__main__":
    main()
