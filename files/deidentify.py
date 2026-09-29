"""Mask likely personal names in a study label before it is drawn on a page.

Study files are named like  "9999 Jordan D 01.000.03 AGE 15 EC.edf"  -- case
number, first name, last initial, session code, age, condition. The cascade
prints that name on every component page, so it is masked first:

    deidentify_label(".../9999 Jordan D 01.000.03 AGE 15 EC.edf")
      -> "9999 ###### # 01.000.03 AGE 15 EC"

Rules (HIPAA Safe Harbor, applied to what a file name can carry):
  * Only the file's base name is shown -- directory components are dropped,
    since folder names (practitioner, patient) can carry names too.
  * Any purely alphabetic word not in KNOWN_TERMS is treated as a name and
    each of its letters replaced by '#'. Unknown words are masked by default:
    a missed technical term costs readability, a missed name costs privacy.
  * Words containing digits (case numbers, session codes, "raw_130399") are
    kept -- they are codes, not names.
  * An age over 89 ("AGE 92") becomes "90+", as Safe Harbor requires.

Display only: nothing here feeds a metric, a file name, or a path.
"""
import os
import re

# Technical vocabulary that appears in study file names. Compared upper-case.
KNOWN_TERMS = {
    # recording / montage / file handling
    "AGE", "EC", "EO", "EEG", "QEEG", "QEEGS", "QEGG", "STLE", "RAW", "ECRAW",
    "EORAW", "ICA", "ICAL", "ICALE", "LE", "AVG", "LAP", "EDF", "RECON",
    "TEST", "CLEAN", "UNCLEAN", "PRE", "POST", "BASELINE", "REST", "RESTING",
    "TASK", "EYES", "EYE", "OPEN", "CLOSED", "SESSION", "STS", "QAR", "NF",
    "NFB", "HEG", "ERP", "CPT", "MIN", "MINS", "SEC", "DATA", "FILE", "COPY",
    "EXCEL", "EDITED", "EDITS", "IMPORT", "EXPORT", "UPLOAD", "UPLOADED",
    "VERSION", "MISC", "NEW", "ORIGINAL", "INITIAL", "REDO", "REPEAT",
    "RECORDING", "RECORDED", "READING", "ACQUISITION", "ACQUISTION",
    "IMPEDANCE", "QEGIMPEDENCE", "FILTER", "CHANNEL", "DYN", "RES", "MAP",
    "OUTPUTS", "ANALYSIS", "SLORETA", "LORETA", "BRAINAVATAR", "HSBM", "NFLA",
    "IMS", "CADWELL", "INTAKE", "SCREENING", "ASSESSMENT", "ASSESSMENTS",
    "REVIEW", "REVIEWS", "REVIEWED", "TRAINING", "FOLLOW", "UP", "FULL",
    "HZ", "YR", "YO", "FEMALE", "MALE",
    # small words
    "AND", "FOR", "WITH", "FROM", "NOT", "NO", "AS", "VERY", "GOOD",
    # clinical findings that turn up in file names
    "PDR", "IRDA", "IRDAS", "FIRDA", "TIRDA", "PIRDA", "IEDS", "SPIKE",
    "SPIKES", "SHARPS", "SLOW", "SLOWS", "PAUSES", "DROWSY", "SLEEP", "STAGE",
    "RAPID", "FOCAL", "PAROXYSM", "ABSENCE", "ROLANDIC", "EPILEPSY", "JME",
    "SZ", "ADD", "ADHD", "HX", "TRAUMA", "DYSREGULATION", "ISOELECTRIC",
    "ARTIFACT", "ARTIFACTS", "ACTIVITY", "CONTINUOUS", "EXTREME",
    "EXTREMELY", "ATYPICAL", "MULTIPLE", "FRONTAL", "LOBE", "DELTA", "THETA",
    "ALPHA", "BETA", "GAMMA", "THC", "IED", "EPILEPTIFORM", "EPILEPTOGENIC",
    "SUBCORTICAL", "POSTERIOR", "DROWSINESS", "PANDAS", "ROUND", "ROUNDUP",
    "CONVERTED", "DISREGARD", "EACH",
}

_SPLIT = re.compile(r"([\s_\-]+)")
_ALPHA = re.compile(r"^[A-Za-z][A-Za-z.'’]*$")


def deidentify_label(name):
    base = re.split(r"[\\/]", str(name))[-1]
    if base.lower().endswith(".edf"):
        base = base[:-4]
    parts = _SPLIT.split(base)
    out = []
    prev_word = ""
    for part in parts:
        if not part or _SPLIT.fullmatch(part):
            out.append(part)
            continue
        word = part.rstrip(".,")
        tail = part[len(word):]
        if _ALPHA.match(word):
            # dot-joined words ("EC.RECON", "Y.") are judged piece by piece
            part = ".".join(p if (not p or p.upper() in KNOWN_TERMS)
                            else "#" * len(p) for p in word.split(".")) + tail
        elif prev_word == "AGE" and word.isdigit() and int(word) > 89:
            part = "90+" + tail
        out.append(part)
        prev_word = word.upper()
    return "".join(out)
