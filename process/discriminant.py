# Discriminant-function scoring for the Brain Panel.
#
# Implements the six weighted-count discriminant functions from
# Collura et al. (2026), Table 4 / Appendix B Figure B7:
# "Optimal weighted metric combinations for predicting clinical
#  abnormality, drowsiness, artifacts, paroxysmal events, PDR frequency
#  abnormalities, and overall EEG quality."
#
# Each category score is a weighted sum of out-of-bounds (|z| >= 2) row
# counts from the five Brain Panel groups (Std/Global, PDR, Focal,
# Diffuse, State Shift) plus the total OOB count across all 48 rows.
#
# Used by files/create_report_pdf_discriminant.py to render a likelihood
# block on page 2 of the report.

import numpy as np

OOB_Z = 2.0

# Row-index ranges into the 48 Brain Panel rows (name_strings ordering
# as built in edftotextbynameplotproc.py line ~934).
# Phenotypes (rows 11-16) contribute only to the "total" count; the
# Table-4 discriminants do not assign them a group weight.
GROUP_INDEXES = {
    "std_global":  list(range(0, 2)),    # STD Raw, Global STD
    "pdr":         list(range(2, 11)),   # PDR Symmetry .. PDR Burst Width
    "phenotypes":  list(range(11, 17)),  # Beta Max Front .. Midline Beta (informational)
    "focal":       list(range(17, 29)),  # Focal Delta Index .. Front Gamma Asym
    "diffuse":     list(range(29, 36)),  # Diffuse Delta .. Fractal Dimension
    "state_shift": list(range(36, 48)),  # PDR Moment 1 .. Delta Moment 3
}

# weights = {group: integer weight} -- one row per Table-4 entry, in the
# same display order as the paper.  "total" is the count of ALL OOB rows
# (across all 48 metrics, including phenotypes).
DISCRIMINANTS = [
    {"name": "Clinical Abnormality",
     "weights": {"std_global": 0, "pdr": 3, "focal": 2, "diffuse": 2, "state_shift": 1, "total": 0},
     "sens": 89, "spec": 76, "acc": 78},
    {"name": "Drowsiness",
     "weights": {"std_global": 0, "pdr": 2, "focal": 0, "diffuse": 1, "state_shift": 3, "total": 0},
     "sens": 93, "spec": 79, "acc": 87},
    {"name": "Artifact",
     "weights": {"std_global": 3, "pdr": 0, "focal": 0, "diffuse": 2, "state_shift": 0, "total": 1},
     "sens": 92, "spec": 83, "acc": 88},
    {"name": "Paroxysmal",
     "weights": {"std_global": 0, "pdr": 2, "focal": 3, "diffuse": 0, "state_shift": 1, "total": 0},
     "sens": 94, "spec": 88, "acc": 91},
    {"name": "PDR frequency",
     "weights": {"std_global": 0, "pdr": 4, "focal": 0, "diffuse": 0, "state_shift": 1, "total": 1},
     "sens": 95, "spec": 84, "acc": 91},
    {"name": "EEG Quality",
     "weights": {"std_global": 4, "pdr": 0, "focal": 0, "diffuse": 2, "state_shift": 0, "total": 1},
     "sens": 94, "spec": 88, "acc": 90},
]

# Group sizes (# Brain Panel rows in each group, used to compute the
# theoretical maximum score per category).  "total" counts all 48 rows.
GROUP_SIZES = {
    "std_global":  2,
    "pdr":         9,
    "phenotypes":  6,   # only contributes to total
    "focal":       12,
    "diffuse":     7,
    "state_shift": 12,
    "total":       48,
}

# Base risk bands from Appendix Figure B7 of the paper, derived for the
# Clinical Abnormality (Clinical-Weighted Score) detector.  The upper
# bounds of the first three bands (2, 4, 7) get scaled proportionally
# for each category by (cat_max_score / clinical_abnormality_max_score),
# so each category's bands span the same fraction-of-max range.
# (label, rgb_color_0to1)
BASE_UPPER_BOUNDS = (2, 4, 7)
BASE_BAND_LABELS = (
    ("Very Low Likelihood", (0.00, 0.50, 0.00)),
    ("Low Likelihood",      (0.40, 0.55, 0.00)),
    ("Moderate Likelihood", (0.80, 0.45, 0.00)),
    ("High Likelihood",     (0.85, 0.00, 0.00)),
)

GROUP_LABEL = {
    "std_global":  "Std/Global",
    "pdr":         "PDR",
    "focal":       "Focal",
    "diffuse":     "Diffuse",
    "state_shift": "State Shift",
    "total":       "Total",
}


def _max_score(weights):
    """Theoretical maximum score: every weighted group fully OOB."""
    return sum(weights.get(g, 0) * GROUP_SIZES[g] for g in weights)


def _category_bands(weights):
    """
    Build per-category risk bands by scaling the Clinical Abnormality
    bands proportionally to this category's max-score relative to
    Clinical Abnormality's max (= 77).  Returns a list of
    (lo, hi, label, color) tuples covering all integer scores.
    """
    clinical_max = _max_score(DISCRIMINANTS[0]["weights"])
    scale = _max_score(weights) / clinical_max
    scaled = [int(b * scale) for b in BASE_UPPER_BOUNDS]

    bands = []
    lo = 0
    upper_points = list(scaled) + [10**9]
    for upper, (label, color) in zip(upper_points, BASE_BAND_LABELS):
        hi = max(upper, lo)  # collapse to a single point if scale is tiny
        bands.append((lo, hi, label, color))
        lo = hi + 1
    return bands


def _bands_label(bands):
    """Compact one-line summary, e.g. '0-1 | 2-3 | 4-6 | 7+'."""
    parts = []
    for i, (lo, hi, _label, _color) in enumerate(bands):
        if i == len(bands) - 1:
            parts.append(f"{lo}+")
        elif lo == hi:
            parts.append(str(lo))
        else:
            parts.append(f"{lo}-{hi}")
    return " | ".join(parts)


def compute_oob_counts(z_scores):
    """
    z_scores : iterable of 48 z-scores in name_strings ordering.
    Returns a dict of {group_name: # rows OOB} plus 'total'.
    OOB is |z| >= OOB_Z (matches the >2 / <-2 thresholds used elsewhere).
    """
    z = np.asarray(list(z_scores), dtype=float)
    if z.shape[0] != 48:
        raise ValueError(f"expected 48 z-scores, got {z.shape[0]}")
    oob = np.abs(z) >= OOB_Z
    counts = {g: int(oob[idxs].sum()) for g, idxs in GROUP_INDEXES.items()}
    counts["total"] = int(oob.sum())
    return counts


def compute_scores(counts):
    """
    counts : dict from compute_oob_counts.
    Returns list of dicts (one per category) with score / per-category
    risk band / metadata.  Each category carries its own bands list,
    proportionally scaled to its theoretical maximum score.
    """
    out = []
    for d in DISCRIMINANTS:
        w = d["weights"]
        score = sum(w[g] * counts.get(g, 0) for g in w)
        bands = _category_bands(w)
        label, color = _band(score, bands)
        out.append({
            "name":      d["name"],
            "score":     score,
            "label":     label,
            "color":     color,
            "sens":      d["sens"],
            "spec":      d["spec"],
            "acc":       d["acc"],
            "formula":   _formula(w),
            "weights":   dict(w),
            "max_score": _max_score(w),
            "bands":     bands,
            "bands_label": _bands_label(bands),
        })
    return out


def _band(score, bands):
    for lo, hi, label, color in bands:
        if lo <= score <= hi:
            return label, color
    return "Unknown", (0.0, 0.0, 0.0)


def _formula(w):
    parts = []
    for g in ("std_global", "pdr", "focal", "diffuse", "state_shift", "total"):
        if w.get(g, 0):
            parts.append(f"{w[g]}·{GROUP_LABEL[g]}")
    return "  +  ".join(parts) if parts else "(none)"
