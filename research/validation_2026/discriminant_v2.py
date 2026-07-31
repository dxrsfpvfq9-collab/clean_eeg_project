"""
discriminant_v2 -- the new direction-aware, outcome-matched discriminants.

Each of the six clinical detectors uses the feature basis that generalized best
on the 98-file cohort (see combined_discriminants.py / PHASE_D_AXIS_FINDINGS):

  outcome          basis      what it uses                              cv-AUC (paper)
  clinical_abnorm  axes       6 signed covariance axes                  0.67 (0.63)  [low n]
  drowsiness       axes       6 signed axes  (fixes paper's inversion)  0.72 (0.44)
  artifact         groups     6 a-priori OOB group counts               0.68 (0.57)
  paroxysmal       axes       6 signed axes                             0.61 (0.60)  [low n]
  pdr_freq_abnorm  published  (only 2 positives -> not learnable here)  0.56
  eeg_quality      combined   signed metrics + axes + group + n_high    0.82 (0.76)

Unlike the paper's |z|>=2 COUNTING (direction-blind), every detector here is a
signed weighted score -- the sign of each deviation matters.

Frozen weights live in out_structure/discriminant_v2.json (fit on the cohort).
NOTE: prototype. Labels are auto-extracted, single cohort; validate on an
adjudicated hold-out before shipping.  score_panel(z48) -> {outcome: prob}.
"""
import os, json, math, numpy as np
from panel_signature import AXIS_NAMES, NAXES

HERE = os.path.dirname(os.path.abspath(__file__))
OUTS = os.path.join(HERE, "out_structure")
V2 = json.load(open(os.path.join(OUTS, "discriminant_v2.json")))
AXM = json.load(open(os.path.join(OUTS, "axis_model.json")))
ASSIGN = np.array(AXM["assign"]); SIGN = np.array(AXM["sign"])
AX_MU = np.array(AXM["ax_mu"]); AX_SD = np.array(AXM["ax_sd"]); LABELS = AXM["labels"]
GROUPS = ["std_global", "pdr", "phenotypes", "focal", "diffuse", "state_shift"]
# 48-row index ranges per a-priori group (matches process/discriminant.GROUP_INDEXES)
GIDX = {"std_global": range(0, 2), "pdr": range(2, 11), "phenotypes": range(11, 17),
        "focal": range(17, 29), "diffuse": range(29, 36), "state_shift": range(36, 48)}

def _axis_scores(z):
    out = {}
    for j in range(NAXES):
        m = np.where(ASSIGN == j)[0]
        raw = np.nanmean(SIGN[m] * z[m])
        out[f"AX:{AXIS_NAMES[j]}"] = 0.0 if not np.isfinite(raw) else (raw - AX_MU[j]) / AX_SD[j]
    return out

def _feature_dict(z):
    z = np.nan_to_num(np.asarray(z, float), nan=0.0)
    fd = {}
    fd.update(_axis_scores(z))
    oob = np.abs(z) >= 2
    for g in GROUPS:
        fd[f"GRP:{g}"] = float(oob[list(GIDX[g])].sum())
    fd["n_high"] = float((z >= 2).sum()); fd["n_low"] = float((z <= -2).sum())
    for i, name in enumerate(LABELS):
        fd[name] = float(z[i])                       # individual signed deviation
    return fd

def score_panel(z48):
    """z48 = 48 Brain Panel z-scores (name_strings order). -> {outcome: prob, ...}"""
    fd = _feature_dict(z48); out = {}
    for o, m in V2.items():
        if m["basis"] == "published_fallback":
            out[o] = None; continue
        s = m["intercept"]
        for name, w, mu, sd in zip(m["feature_names"], m["weights"],
                                   m["scaler_mean"], m["scaler_scale"]):
            s += w * ((fd.get(name, 0.0) - mu) / (sd if sd else 1.0))
        out[o] = 1.0 / (1.0 + math.exp(-max(-30, min(30, s))))
    return out

if __name__ == "__main__":
    # self-test: score the cached cohort, confirm full-sample AUC matches the fit
    from sklearn.metrics import roc_auc_score
    d = np.load(os.path.join(OUTS, "cohort_cache.npz"))
    Z = d["Z"]
    print("outcome           basis      full-sample AUC   cv-AUC   paper")
    for o, m in V2.items():
        probs = np.array([score_panel(Z[i]).get(o) for i in range(len(Z))], float)
        y = d[f"Y_{o}"]
        if m["basis"] == "published_fallback" or y.sum() in (0, len(y)):
            print(f"  {o:<16}{m['basis']:<10} (n/a)"); continue
        auc = roc_auc_score(y, probs)
        print(f"  {o:<16}{m['basis']:<10} {auc:6.2f}          "
              f"{m.get('cv_auc')}    {m.get('published_auc')}")
