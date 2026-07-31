"""External validation: the paroxysmal detector is trained on the strict 99-case
cohort (discriminant_v2.json, blind to these cases). Here we score the archive's
known-paroxysmal EEGs (out/paroxysmal_recoverable.csv, all ground-truth
paroxysmal=1, NOT in the training cohort) and measure the catch-rate.

Reports the detector's sensitivity on an INDEPENDENT positive sample -- the thing
the n=5 in-cohort CV cannot estimate.
"""
import csv, os
import numpy as np
import config, panel_parser as pp
from discriminant_v2 import score_panel

def cohort_ec_files():
    return {r["ec_panel_file"].lower()
            for r in csv.DictReader(open(os.path.join(config.OUT_DIR, "study_cohort.csv"),
                                         encoding="utf-8"))}

def main():
    inco = cohort_ec_files()
    rec = list(csv.DictReader(open(os.path.join(config.OUT_DIR,
                              "paroxysmal_recoverable.csv"), encoding="utf-8")))
    # held-out = genuine paroxysmal, has v2025 EC panel, NOT already in cohort
    held = []
    for r in rec:
        f = r["ec_panel_file"]
        if not f or r["ec_panel_version"] != "v2025_brainml":
            continue
        if f.lower() in inco:
            continue
        path = os.path.join(r["folder"], f)
        if not os.path.isfile(path):
            continue
        held.append((r, path))
    print(f"held-out paroxysmal cases to score: {len(held)}")

    hp = []          # held-out paroxysmal probs
    detail = []
    for r, path in held:
        parsed = pp.parse_panel_pdf(path)
        if not parsed.get("parse_ok"):
            detail.append((r["qeeg"], None, "parse-fail")); continue
        z = np.asarray(parsed["zscores"], float)
        probs = score_panel(z)
        hp.append(probs["paroxysmal"])
        detail.append((r["qeeg"] or r["ec_panel_file"][:14], probs["paroxysmal"],
                       r["paroxysmal_txt"][:52]))
    hp = np.array([x for x in hp if x is not None], float)

    # cohort distribution (training set) for thresholding + pseudo-external ROC
    d = np.load(os.path.join(config.OUT_DIR.replace("out", "out_structure"),
                             "cohort_cache.npz"))
    Z = d["Z"]; y = d["Y_paroxysmal"]
    cp = np.array([score_panel(Z[i])["paroxysmal"] for i in range(len(Z))], float)
    pos_c, neg_c = cp[y == 1], cp[y == 0]

    # thresholds from the TRAINING cohort
    from sklearn.metrics import roc_auc_score
    # (a) Youden J on cohort
    ts = np.unique(cp)
    def sens_spec(t):
        return (pos_c >= t).mean(), (neg_c < t).mean()
    youden = max(ts, key=lambda t: sum(sens_spec(t)) - 1)
    # (b) threshold at ~80% specificity on cohort negatives
    t80 = np.quantile(neg_c, 0.80)

    print("\n=== held-out case scores (paroxysmal prob) ===")
    for q, p, txt in sorted(detail, key=lambda x: -(x[1] or -1)):
        ps = f"{p:.3f}" if p is not None else "  -  "
        print(f"  {q:16} p={ps}  {txt}")

    def catch(t): return (hp >= t).mean()
    print("\n=== cohort (training) score summary ===")
    print(f"  paroxysmal positives n={int(y.sum())}, negatives n={int((y==0).sum())}")
    print(f"  cohort pos median prob {np.median(pos_c):.3f}, neg median {np.median(neg_c):.3f}")
    print(f"  Youden threshold={youden:.3f}  (cohort sens {sens_spec(youden)[0]:.2f}, spec {sens_spec(youden)[1]:.2f})")
    print(f"  80%-spec threshold={t80:.3f}")

    print("\n=== EXTERNAL RESULT: catch-rate on held-out known-paroxysmal EEGs ===")
    print(f"  n held-out scored: {len(hp)}")
    print(f"  catch-rate @ Youden thr : {catch(youden)*100:4.0f}%  ({int((hp>=youden).sum())}/{len(hp)})")
    print(f"  catch-rate @ 80%-spec   : {catch(t80)*100:4.0f}%  ({int((hp>=t80).sum())}/{len(hp)})")
    print(f"  held-out median prob    : {np.median(hp):.3f}  (vs cohort neg median {np.median(neg_c):.3f})")
    # pseudo-external ROC: held-out positives vs cohort negatives
    yy = np.r_[np.ones(len(hp)), np.zeros(len(neg_c))]
    ss = np.r_[hp, neg_c]
    print(f"  pseudo-external AUC (held-out pos vs cohort neg): {roc_auc_score(yy, ss):.3f}")

if __name__ == "__main__":
    main()
