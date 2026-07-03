"""Phase D re-validation with the corrected Global STD.

Only Global STD changed under the whitening fix (verified 0/47 other metrics),
so we take each saved report's 48 z-scores and patch ONLY index 1 (Global STD)
with the corrected z = (corrected_value - DB_AVG) / DB_STD, where the corrected
per-file values are in out/_gstd_new.tsv (row-aligned to study_cohort.csv).

Computes the published discriminants both ways (pre-fix = saved z with Global
STD pegged at 2642; post-fix = corrected) and reports the before/after for each
outcome. The std_global-weighted detectors (Artifact x3, EEG Quality x4) are the
ones that can move.
"""
import csv
import os
import sys

import numpy as np

import config
import labels as L
import panel_parser as pp
import report_parser as rp
from run_phase_d import best_operating_point, GROUPS, _pct

sys.path.insert(0, config.REPO_ROOT)
from process import discriminant  # noqa: E402

GSTD_AVG = 2.668329402241444
GSTD_STD = 0.3773898123645797


def load_corrected():
    vals = []
    for line in open(os.path.join(config.OUT_DIR, "_gstd_new.tsv"), encoding="utf-8"):
        line = line.rstrip("\n").rstrip("\r")
        if not line:
            continue
        parts = line.split("\t")
        vals.append(float(parts[1]) if len(parts) > 1 and parts[1] else float("nan"))
    return vals


def build():
    rows = list(csv.DictReader(open(os.path.join(config.OUT_DIR, "study_cohort.csv"),
                                    encoding="utf-8")))
    gvals = load_corrected()
    assert len(rows) == len(gvals), f"{len(rows)} cohort vs {len(gvals)} corrected"
    Y = {o: [] for o in L.OUTCOMES}
    S_pre = {o: [] for o in L.OUTCOMES}
    S_post = {o: [] for o in L.OUTCOMES}
    oob_pre, oob_post = [], []   # std_global OOB count each way
    print(f"Re-validating {len(rows)} cohort panels with corrected Global STD ...")
    for i, row in enumerate(rows):
        parsed = pp.parse_panel_pdf(row["ec_panel_path"])
        z_pre = list(parsed["zscores"])
        z_post = list(z_pre)
        z_post[1] = (gvals[i] - GSTD_AVG) / GSTD_STD   # corrected Global STD z
        c_pre = discriminant.compute_oob_counts(z_pre)
        c_post = discriminant.compute_oob_counts(z_post)
        oob_pre.append(c_pre["std_global"]); oob_post.append(c_post["std_global"])
        sp = {s["name"]: s["score"] for s in discriminant.compute_scores(c_pre)}
        sq = {s["name"]: s["score"] for s in discriminant.compute_scores(c_post)}
        rep = rp.parse_report(row["report_path"]) if row["report_path"] else {}
        age = int(row["age"]) if row["age"] not in ("", None) else None
        labs = L.all_labels(rep, age)
        for o in L.OUTCOMES:
            Y[o].append(labs[o][0])
            S_pre[o].append(sp[L.DISCRIMINANT_OF[o]])
            S_post[o].append(sq[L.DISCRIMINANT_OF[o]])
        if (i + 1) % 25 == 0:
            print(f"   {i + 1}/{len(rows)}")
    npize = lambda d: {o: np.array(d[o], float) for o in L.OUTCOMES}
    return ({o: np.array(Y[o]) for o in L.OUTCOMES}, npize(S_pre), npize(S_post),
            np.array(oob_pre), np.array(oob_post))


def main():
    Y, S_pre, S_post, oob_pre, oob_post = build()

    print("\nstd_global OOB count per panel:")
    print(f"  PRE-fix : mean {oob_pre.mean():.2f}, ==0 in {int((oob_pre==0).sum())}/98 "
          f"(Global STD always OOB -> std_global never 0)")
    print(f"  POST-fix: mean {oob_post.mean():.2f}, ==0 in {int((oob_post==0).sum())}/98 "
          f"(Global STD now in-range on most)")

    lines = ["# Phase D re-validation — corrected Global STD", "",
             f"n=98. Only Global STD changed; the std_global OOB count went from "
             f"always>=1 (mean {oob_pre.mean():.2f}) to mean {oob_post.mean():.2f}. "
             "Artifact (3x std_global) and EEG Quality (4x) are the affected "
             "detectors.", "",
             "| Outcome | n+ | AUC pre | AUC post | sens/spec/acc pre | sens/spec/acc post |",
             "|---|---|---|---|---|---|"]
    print(f"\n{'outcome':16s} {'n+':>3} {'AUCpre':>7} {'AUCpost':>8}   sens/spec/acc pre -> post")
    for o in L.OUTCOMES:
        y = Y[o]
        a = best_operating_point(y, S_pre[o])
        b = best_operating_point(y, S_post[o])
        if a is None or b is None:
            continue
        tag = "   <==" if abs(a["auc"] - b["auc"]) > 0.02 else ""
        print(f"{o:16s} {int(y.sum()):>3} {a['auc']:>7.2f} {b['auc']:>8.2f}   "
              f"{_pct(a['sens'])}/{_pct(a['spec'])}/{_pct(a['acc'])} -> "
              f"{_pct(b['sens'])}/{_pct(b['spec'])}/{_pct(b['acc'])}{tag}")
        lines.append(
            f"| {o} | {int(y.sum())} | {a['auc']:.2f} | {b['auc']:.2f} | "
            f"{_pct(a['sens'])}/{_pct(a['spec'])}/{_pct(a['acc'])} | "
            f"{_pct(b['sens'])}/{_pct(b['spec'])}/{_pct(b['acc'])} |")
    lines += ["",
              f"std_global OOB count: pre-fix mean {oob_pre.mean():.2f} "
              f"(0 in {int((oob_pre==0).sum())}/98) -> post-fix mean "
              f"{oob_post.mean():.2f} (0 in {int((oob_post==0).sum())}/98).",
              "", "Only Artifact and EEG Quality weight std_global, so only "
              "those AUCs can move; the other four are identical by construction."]
    with open(os.path.join(config.OUT_DIR, "phase_d_refixed_results.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\nWrote out/phase_d_refixed_results.md")


if __name__ == "__main__":
    main()
