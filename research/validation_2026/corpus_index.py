"""Walk the QA corpus, classify Brain Panels and Doctor's Reports, parse
metadata + ID tokens from filenames, and pair EC panels to reports within
each weekly session folder.

Pairing is token-based and varies by year, so we report confidence rather
than assume one scheme:

  strong    - panels & report share a mixed alphanumeric code (e.g. RS101411,
              Jo0454, TBNY00041, GW053116) -> high confidence.
  weak      - share only a short pure-numeric clip id (e.g. 1225).
  ambiguous - more than one report in the session matches.
  none      - no report shares a token.
"""
import hashlib
import os
import re

import config

# ---- filename parsing ------------------------------------------------------

_AGE_RE = re.compile(r"\bAGE\s*(\d{1,3})", re.I)
_COND_RE = re.compile(r"(?<![A-Za-z])(EC|EO)(?![A-Za-z])", re.I)
# substrings to strip before tokenizing so ages/dates/session-codes don't
# masquerade as patient ids.
_STRIP_RES = [
    re.compile(r"\bAGE\s*\d{1,3}", re.I),       # AGE 57
    re.compile(r"\d\d\.\d\d\d\.\d\d"),           # 01.000.02 session code
    re.compile(r"\d{1,2}-\d{1,2}-\d{2,4}"),      # 04-23-2024 date
    re.compile(r"\b20\d\d\b"),                   # bare year
    re.compile(r"\.icale\.rep\.pdf$", re.I),
    re.compile(r"\.clean", re.I),
    re.compile(r"STS EEG Quality Assurance Review.*", re.I),
]
_MIXED_RE = re.compile(r"\b(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{5,}\b")
_NUMERIC_RE = re.compile(r"\b\d{3,6}\b")


_SEP_RE = re.compile(r"[_\-./\\]+")


def _clean_for_tokens(stem):
    s = stem
    for rx in _STRIP_RES:  # must run first: date/session regexes need - and .
        s = rx.sub(" ", s)
    return _SEP_RE.sub(" ", s)  # now split underscores etc. so \b sees tokens


def id_tokens(stem):
    """Return (strong_tokens, weak_tokens) as lowercased sets."""
    s = _clean_for_tokens(stem)
    strong = {m.group(0).lower() for m in _MIXED_RE.finditer(s)}
    # numeric tokens that are not part of a strong (alnum) token
    weak = {m.group(0).lower() for m in _NUMERIC_RE.finditer(s)} - strong
    return strong, weak


def parse_condition(stem):
    m = list(_COND_RE.finditer(stem))
    return m[-1].group(1).upper() if m else ""  # last EC/EO wins (suffix)


def parse_age(stem):
    m = _AGE_RE.search(stem)
    return int(m.group(1)) if m else None


def patient_key(strong, weak):
    """Stable anonymized key from the most specific available token."""
    basis = sorted(strong) if strong else sorted(weak)
    if not basis:
        return ""
    return "pk_" + hashlib.sha1("|".join(basis).encode()).hexdigest()[:12]


# ---- session scoping -------------------------------------------------------

def session_of(rel_parts):
    """Weekly session-folder name for a path given as parts relative to root."""
    if rel_parts and rel_parts[0].endswith(config.YEAR_FOLDER_SUFFIX):
        return rel_parts[1] if len(rel_parts) > 1 else rel_parts[0]
    return rel_parts[0] if rel_parts else ""


def year_of(rel_parts, session):
    for cand in (rel_parts[0] if rel_parts else "", session):
        m = re.search(r"20\d\d", cand)
        if m:
            return int(m.group(0))
    return None


# ---- corpus walk -----------------------------------------------------------

def _classify(fn):
    low = fn.lower()
    if low.endswith(config.PANEL_SUFFIX):
        return "panel"
    if low.endswith(".docx") and config.REPORT_GLOB_TOKEN.lower() in low \
            and "~$" not in low:
        return "report"
    return None


def walk_corpus():
    """Return (panels, reports) lists of dict records."""
    panels, reports = [], []
    root = config.CORPUS_ROOT
    for dirpath, _dirs, files in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        rel_parts = [] if rel == "." else rel.split(os.sep)
        session = session_of(rel_parts)
        year = year_of(rel_parts, session)
        for fn in files:
            kind = _classify(fn)
            if not kind:
                continue
            stem = fn
            strong, weak = id_tokens(stem)
            rec = {
                "path": os.path.join(dirpath, fn),
                "filename": fn,
                "session": session,
                "year": year,
                "strong_tokens": strong,
                "weak_tokens": weak,
                "patient_key": patient_key(strong, weak),
            }
            if kind == "panel":
                rec["condition"] = parse_condition(stem)
                rec["age"] = parse_age(stem)
                rec["is_clean"] = "clean" in stem.lower()
                panels.append(rec)
            else:
                rec["is_rt"] = bool(re.search(r"-\s*rt\b", stem, re.I))
                reports.append(rec)
    return panels, reports


# ---- pairing ---------------------------------------------------------------

def pair_ec_panels(panels, reports):
    """Attach a matched Doctor's Report to each EC panel. Returns list of
    manifest rows (one per EC panel, de-duplicated preferring non-clean)."""
    # index reports by session
    by_session = {}
    for r in reports:
        by_session.setdefault(r["session"], []).append(r)

    ec = [p for p in panels if p["condition"] == "EC"]

    # de-duplicate EC panels by (session, patient_key): prefer the non-clean
    # variant, otherwise the first seen.
    dedup = {}
    for p in ec:
        key = (p["session"], p["patient_key"], p["filename"].lower().replace(".clean", ""))
        cur = dedup.get(key)
        if cur is None or (cur["is_clean"] and not p["is_clean"]):
            dedup[key] = p
    ec = list(dedup.values())

    rows = []
    for p in ec:
        cands = by_session.get(p["session"], [])
        strong_hits = [r for r in cands if p["strong_tokens"] & r["strong_tokens"]]
        weak_hits = [r for r in cands
                     if (p["strong_tokens"] | p["weak_tokens"]) & (r["strong_tokens"] | r["weak_tokens"])]
        if strong_hits:
            hits, conf = strong_hits, ("strong" if len(set(h["patient_key"] for h in strong_hits)) == 1 else "ambiguous")
        elif weak_hits:
            hits, conf = weak_hits, ("weak" if len(set(h["patient_key"] for h in weak_hits)) == 1 else "ambiguous")
        else:
            hits, conf = [], "none"
        # prefer the revised "- rt" report if present
        match = None
        if hits:
            rt = [h for h in hits if h.get("is_rt")]
            match = (rt or hits)[0]
        rows.append({
            "patient_key": p["patient_key"],
            "session": p["session"],
            "year": p["year"],
            "age": p["age"],
            "ec_panel_path": p["path"],
            "ec_panel_file": p["filename"],
            "is_clean": p["is_clean"],
            "report_path": match["path"] if match else "",
            "report_file": match["filename"] if match else "",
            "match_conf": conf,
            "n_report_candidates": len(set(h["patient_key"] for h in hits)),
        })
    return rows
