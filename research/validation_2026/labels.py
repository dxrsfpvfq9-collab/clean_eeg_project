"""Phase D ground truth: normalise the Doctor's Report template fields into the
six binary clinical outcomes the published discriminants predict.

Each label returns (value in {0,1}, confidence in {"high","low"}). Thresholds
are documented inline and are the obvious levers to revisit.

Outcome           Doctor field      Positive (=1) means
----------------- ----------------- ------------------------------------------
clinical_abnorm   comments (R)      abnormality noted (not "no overt ...")
drowsiness        drowsiness (P)    drowsiness demonstrated (incl. possible)
artifact          artifact (M)      Moderate or Severe (vs Mild / none)
paroxysmal        paroxysmal (Q)    anything other than "none"
pdr_freq_abnorm   background (O)    PDR frequency below age-appropriate floor
eeg_quality       quality (L)       Fair or Poor (vs Good/Satisfactory/Adequate)
"""
import re

OUTCOMES = ["clinical_abnorm", "drowsiness", "artifact", "paroxysmal",
            "pdr_freq_abnorm", "eeg_quality"]

# outcome -> discriminant name in process/discriminant.py
DISCRIMINANT_OF = {
    "clinical_abnorm": "Clinical Abnormality",
    "drowsiness": "Drowsiness",
    "artifact": "Artifact",
    "paroxysmal": "Paroxysmal",
    "pdr_freq_abnorm": "PDR frequency",
    "eeg_quality": "EEG Quality",
}


def _lc(s):
    return (s or "").strip().lower()


def lab_clinical_abnorm(rep):
    v = _lc(rep.get("comments"))
    if not v:
        return 0, "low"
    neg = ("no overt" in v or "no abnormalit" in v or "without abnormalit" in v
           or "no significant" in v or v in ("none", "none."))
    return (0 if neg else 1), "high"


def lab_drowsiness(rep):
    v = _lc(rep.get("drowsiness"))
    if not v:
        return 0, "low"
    # Negatives FIRST so a negated clause is not swallowed by the "demonstrated"
    # positive below. "Drowsiness was not clearly demonstrated" (4 cohort reports)
    # was previously misread as positive.
    if ("not demonstrated" in v or "no drowsiness" in v or "not present" in v
            or "not clearly demonstrated" in v):
        return 0, "high"
    # Drowsiness reported only for the EO condition does not label the EC panel
    # ("Drowsiness was noted in the EO condition.").
    if "noted in the eo" in v and "ec" not in v:
        return 0, "high"
    if "demonstrated" in v or "drowsy" in v or "sleep" in v or "noted" in v:
        # "possibly / may be / intermittent / noted throughout" count positive.
        return 1, "high"
    return 0, "low"


def lab_artifact(rep):
    v = _lc(rep.get("artifact"))
    if not v:
        return 0, "low"
    if "severe" in v or "marked" in v:
        return 1, "high"
    if "moderate" in v:
        return 1, "high"
    if "mild" in v or "minimal" in v or "none" in v or "no significant" in v:
        return 0, "high"
    return 0, "low"


def lab_paroxysmal(rep):
    v = _lc(rep.get("paroxysmal")).strip(" .")
    if v == "":
        return 0, "low"
    return (0 if v.startswith("none") or v == "no" else 1), "high"


_DASH_HZ = re.compile(r"(\d{1,2}(?:\.\d)?)\s*-\s*(\d{1,2}(?:\.\d)?)\s*hz")
_ONE_HZ = re.compile(r"(\d{1,2}(?:\.\d)?)\s*hz")


def parse_pdr_hz(background):
    """Best-effort PDR frequency (Hz) from the space-corrupted background text.
    Returns (hz or None). Takes the lower bound of the first 'X-Y Hz' range
    after de-spacing numerals."""
    t = _lc(background)
    t = re.sub(r"\s*\.\s*", ".", t)        # "8 .0" -> "8.0", "10. 0" -> "10.0"
    t = re.sub(r"(\d)\s+(\d)", r"\1\2", t)  # "1 0" -> "10", "1 1" -> "11"
    t = re.sub(r"(\d)\s+(\d)", r"\1\2", t)  # second pass for "1 1 1"
    m = _DASH_HZ.search(t)
    if m:
        lo = float(m.group(1))
        return lo if 2 <= lo <= 20 else None
    m = _ONE_HZ.search(t)
    if m:
        v = float(m.group(1))
        return v if 2 <= v <= 20 else None
    return None


def _pdr_floor(age):
    if age is None:
        return 8.0
    if age >= 8:
        return 8.0
    if age >= 5:
        return 7.0
    if age >= 3:
        return 6.0
    return 5.0


def lab_pdr_freq_abnorm(rep, age):
    # Honor an explicit clinician call of PDR slowing for age in the comments.
    # This catches boundary cases where the numeric PDR sits exactly on the age
    # floor (e.g. 7.0 Hz at age 7) yet the reviewer flagged slowing.
    c = _lc(rep.get("comments"))
    if ("pdr slowing for" in c or "slowing for stated age" in c
            or "slowing for his age" in c or "slowing for her age" in c):
        if not ("no pdr slowing" in c or "without pdr slowing" in c
                or "no slowing" in c):
            return 1, "high"
    hz = parse_pdr_hz(rep.get("background"))
    if hz is None:
        return 0, "low"
    return (1 if hz < _pdr_floor(age) else 0), "high"


_QUAL_BAD = ("fair", "poor", "inadequate")
_QUAL_OK = ("good", "satisfactory", "adequate", "excellent")


def lab_eeg_quality(rep):
    v = _lc(rep.get("quality"))
    if not v:
        return 0, "low"
    first = v.split()[0]
    if first in ("fair", "poor", "inadequate"):
        return 1, "high"
    if first in _QUAL_OK:
        return 0, "high"
    if any(b in v for b in _QUAL_BAD):
        return 1, "high"
    return 0, "low"


def all_labels(rep, age):
    """Return {outcome: (value, conf)} for one report."""
    return {
        "clinical_abnorm": lab_clinical_abnorm(rep),
        "drowsiness": lab_drowsiness(rep),
        "artifact": lab_artifact(rep),
        "paroxysmal": lab_paroxysmal(rep),
        "pdr_freq_abnorm": lab_pdr_freq_abnorm(rep, age),
        "eeg_quality": lab_eeg_quality(rep),
    }
