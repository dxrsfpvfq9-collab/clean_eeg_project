"""Phase A (corpus index + EC pairing) and Phase B (panel feature extraction).

Outputs (all under out/, git-ignored):
  panels_index.csv          - every Brain Panel found (EC + EO), with metadata
  reports_index.csv         - every Doctor's Report found
  manifest_ec.csv           - one row per EC panel, paired to a report
  panel_features.csv        - 6 OOB group counts per EC panel (Phase B)
  manifest_ec_features.csv  - manifest_ec joined with panel_features
  phase_ab_summary.txt      - coverage / diagnostics
"""
import csv
import os
import sys

import config
import corpus_index as ci
import panel_parser as pp

sys.path.insert(0, config.REPO_ROOT)
from process import discriminant  # noqa: E402

OOB_GROUPS = ["std_global", "pdr", "focal", "diffuse", "state_shift", "total"]


def _w(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        wr.writeheader()
        for r in rows:
            wr.writerow(r)


def _tok(s):
    return " ".join(sorted(s)) if s else ""


def main():
    print("Phase A: walking corpus ...")
    panels, reports = ci.walk_corpus()
    print(f"  found {len(panels)} Brain Panels, {len(reports)} Doctor's Reports")

    # ---- indexes
    _w(os.path.join(config.OUT_DIR, "panels_index.csv"),
       [{**p, "strong_tokens": _tok(p["strong_tokens"]),
         "weak_tokens": _tok(p["weak_tokens"])} for p in panels],
       ["patient_key", "year", "session", "condition", "age", "is_clean",
        "strong_tokens", "weak_tokens", "filename", "path"])
    _w(os.path.join(config.OUT_DIR, "reports_index.csv"),
       [{**r, "strong_tokens": _tok(r["strong_tokens"]),
         "weak_tokens": _tok(r["weak_tokens"])} for r in reports],
       ["patient_key", "year", "session", "is_rt", "strong_tokens",
        "weak_tokens", "filename", "path"])

    # ---- EC pairing
    manifest = ci.pair_ec_panels(panels, reports)
    _w(os.path.join(config.OUT_DIR, "manifest_ec.csv"), manifest,
       ["patient_key", "year", "session", "age", "match_conf",
        "n_report_candidates", "ec_panel_file", "report_file", "is_clean",
        "ec_panel_path", "report_path"])
    print(f"  EC panels (deduped): {len(manifest)}")

    # ---- Phase B: parse z-scores -> OOB counts for each EC panel
    print("Phase B: parsing Brain Panel PDFs ...")
    feat_rows, joined = [], []
    n_ok = n_partial = n_err = 0
    for i, m in enumerate(manifest, 1):
        parsed = pp.parse_panel_pdf(m["ec_panel_path"])
        if parsed["error"]:
            n_err += 1
        elif parsed["parse_ok"]:
            n_ok += 1
        else:
            n_partial += 1
        try:
            counts = discriminant.compute_oob_counts(parsed["zscores"])
        except Exception as exc:
            counts = {g: "" for g in OOB_GROUPS}
            parsed["error"] = parsed["error"] or f"oob: {exc}"
        in_coh = config.in_cohort(parsed)
        feat = {
            "patient_key": m["patient_key"],
            "ec_panel_file": m["ec_panel_file"],
            "version": parsed["version"],
            "database": parsed["database"],
            "n_files": parsed["n_files"],
            "report_year": parsed["report_year"] or "",
            "valid": parsed["valid"],
            "in_cohort": in_coh,
            "paired": m["match_conf"] in ("strong", "weak"),
            "in_study": in_coh and m["match_conf"] in ("strong", "weak"),
            "n_parsed": parsed["n_parsed"],
            "parse_ok": parsed["parse_ok"],
            "error": parsed["error"] or "",
            **{f"oob_{g}": counts.get(g, "") for g in OOB_GROUPS},
        }
        feat_rows.append(feat)
        joined.append({**m, **{k: feat[k] for k in feat if k not in ("patient_key", "ec_panel_file")}})
        if i % 50 == 0:
            print(f"    {i}/{len(manifest)}")

    feat_fields = ["patient_key", "ec_panel_file", "version", "database",
                   "n_files", "report_year", "valid", "in_cohort", "paired",
                   "in_study", "n_parsed", "parse_ok", "error"] + \
                  [f"oob_{g}" for g in OOB_GROUPS]
    _w(os.path.join(config.OUT_DIR, "panel_features.csv"), feat_rows, feat_fields)
    _w(os.path.join(config.OUT_DIR, "manifest_ec_features.csv"), joined,
       ["patient_key", "year", "session", "age", "version", "report_year",
        "in_cohort", "paired", "in_study", "match_conf", "n_report_candidates",
        "n_parsed", "valid"] +
       [f"oob_{g}" for g in OOB_GROUPS] +
       ["ec_panel_file", "report_file", "error", "ec_panel_path", "report_path"])

    # study cohort = in_cohort AND paired with a Doctor's Report
    study = [j for j in joined if j["in_cohort"] and j["paired"]]
    _w(os.path.join(config.OUT_DIR, "study_cohort.csv"), study,
       ["patient_key", "year", "session", "age", "version", "report_year",
        "match_conf", "n_parsed"] + [f"oob_{g}" for g in OOB_GROUPS] +
       ["ec_panel_file", "report_file", "ec_panel_path", "report_path"])

    # ---- summary
    def cnt(pred):
        return sum(1 for m in manifest if pred(m))
    conf = {c: cnt(lambda m, c=c: m["match_conf"] == c)
            for c in ("strong", "weak", "ambiguous", "none")}
    paired = conf["strong"] + conf["weak"]
    by_year = {}
    for m in manifest:
        y = m["year"]
        by_year.setdefault(y, [0, 0])
        by_year[y][0] += 1
        if m["match_conf"] in ("strong", "weak"):
            by_year[y][1] += 1

    lines = [
        "PHASE A/B SUMMARY",
        "=" * 60,
        f"Brain Panels found (EC+EO) : {len(panels)}",
        f"Doctor's Reports found     : {len(reports)}",
        f"EC panels (deduped)        : {len(manifest)}",
        "",
        "EC -> Report pairing confidence:",
        f"  strong (alnum code)      : {conf['strong']}",
        f"  weak (numeric clip id)   : {conf['weak']}",
        f"  ambiguous (>1 candidate) : {conf['ambiguous']}",
        f"  none (unpaired)          : {conf['none']}",
        f"  ---> usable paired EC    : {paired}  "
        f"({100 * paired / max(len(manifest), 1):.0f}% of EC panels)",
        "",
        "Paired EC panels by year (paired / total):",
    ]
    for y in sorted(by_year, key=lambda x: (x is None, x)):
        tot, pr = by_year[y][0], by_year[y][1]
        lines.append(f"  {y}: {pr}/{tot}")
    from collections import Counter
    ver = Counter(j["version"] for j in joined)
    lines += [
        "",
        "Phase B PDF parse:",
        f"  fully parsed (48/48)     : {n_ok}",
        f"  partial (47, valid)      : {n_partial}",
        f"  errors (unreadable)      : {n_err}",
        "",
        "EC panels by ML version:",
    ]
    for v, c in ver.most_common():
        lines.append(f"  {v:22s}: {c}")
    n_cohort = sum(1 for j in joined if j["in_cohort"])
    n_study = len(study)
    cohort_years = sorted({j["report_year"] for j in study if j["report_year"]})
    lines += [
        "",
        f"COHORT_VERSIONS = {config.COHORT_VERSIONS}, MIN_REPORT_YEAR = {config.MIN_REPORT_YEAR}",
        f"  in-cohort EC panels      : {n_cohort}",
        f"  >>> STUDY COHORT (cohort & paired with report): {n_study}",
        f"      report years         : {cohort_years}",
        "",
        "Outputs in out/: panels_index, reports_index, manifest_ec, "
        "panel_features, manifest_ec_features, study_cohort.csv",
        "Next: review out/study_cohort.csv, then build Phase C "
        "(Doctor's Report labelling).",
    ]
    summary = "\n".join(lines)
    with open(os.path.join(config.OUT_DIR, "phase_ab_summary.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(summary + "\n")
    print("\n" + summary)


if __name__ == "__main__":
    main()
