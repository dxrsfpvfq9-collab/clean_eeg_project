"""Parse the structured fields out of a P. David Ims STS EEG Quality
Assurance Review .docx file.

The report follows a consistent labeled-field template across 2022-2026:

  "Overall quality of the EEG: <good | fair | poor>"
  "Presence of artifact: <mild | moderate | severe> - <free text>"
  "Amount of artifact free portions for quantitative analysis:
        <adequate | inadequate>"
  "Background rhythm: The background rhythm in the eyes closed wakeful
        state consists of <X-Y Hz> ... <free text>"
  "Drowsiness/Sleep: <Drowsiness was demonstrated | Drowsiness was not
        demonstrated | ...>"
  "Presence of paroxysmal disturbances: <None | <free text>>"
  "Comments: <free narrative>"

The 2023+ versions sometimes leave the severity word blank, drop the
artifact-free line value, or wrap the value into the next paragraph.
This parser is forgiving: each field-extractor looks at the labelled
line plus the next 1-2 paragraphs to find a value.

Public:
  parse_report(path)  -> dict with keys
        quality, artifact_severity, artifact_text, artifact_free,
        background, pdr_freq, drowsiness, paroxysmal, comments,
        author, valid (True if at least 4 fields parsed)
"""
import os
import re

try:
    import docx
except ImportError:
    docx = None


# --- normalization helpers --------------------------------------------
_DASH_RE = re.compile(r"[–—‐‑]")  # en/em/hyphen variants
_WS_RE = re.compile(r"[ \s]+")  # NBSP and runs of whitespace


def _norm(text):
    if text is None:
        return ""
    s = _DASH_RE.sub("-", str(text))
    s = _WS_RE.sub(" ", s).strip()
    return s


# --- extractors -------------------------------------------------------
# Each field has:
#   - the section header that introduces it
#   - the keywords expected in the value
#   - the function that maps free text -> structured label

_FIELD_HEADERS = {
    "quality":      ("overall quality of the eeg",),
    "artifact":     ("presence of artifact",),
    "artifact_free": ("amount of artifact free portions",
                      "amount of artifact-free portions"),
    "background":   ("background rhythm",),
    "drowsiness":   ("drowsiness/sleep", "drowsiness / sleep",
                      "drowsiness sleep"),
    "paroxysmal":   ("presence of paroxysmal", "paroxysmal disturbances"),
    "comments":     ("comments:",),
}


def _gather_paragraphs(path):
    """Return list of normalized paragraph strings (non-empty)."""
    if docx is None:
        raise RuntimeError("python-docx not installed")
    d = docx.Document(path)
    out = []
    for p in d.paragraphs:
        s = _norm(p.text)
        if s:
            out.append(s)
    # Also include table cells — sometimes fields are in tables
    for table in d.tables:
        for row in table.rows:
            for cell in row.cells:
                s = _norm(cell.text)
                if s:
                    out.append(s)
    return out


def _value_after_header(paras, header_keywords):
    """Find the value text that follows a labeled section header.

    Returns the value substring on the header line itself (after the
    colon), plus the next 1-2 paragraphs concatenated if the header
    line ended with no value.
    """
    header_keywords = [h.lower() for h in header_keywords]
    for i, p in enumerate(paras):
        low = p.lower()
        for hk in header_keywords:
            if hk in low:
                # Find the colon position; value is everything after.
                colon = p.find(":", low.find(hk))
                if colon < 0:
                    continue
                inline_val = p[colon + 1:].strip()
                # If inline value is empty or just a dash, scan ahead.
                extra = []
                if len(inline_val) < 3 or inline_val in {"-", "—", "–"}:
                    extra = [paras[j] for j in range(i + 1, min(i + 3, len(paras)))
                              if not _is_section_header(paras[j])]
                return " | ".join(filter(None, [inline_val] + extra))
    return ""


def _is_section_header(text):
    """Heuristic: a paragraph is a new section header if it ends with ':'
    near the start AND matches one of the known section labels."""
    low = text.lower()
    for kws in _FIELD_HEADERS.values():
        for hk in kws:
            if low.startswith(hk):
                return True
    # Author signature is also a section break
    if "p. david ims" in low or "chesapeake" in low:
        return True
    return False


# --- value-to-label mappers -------------------------------------------
def _label_quality(text):
    """Return 'Good' / 'Fair' / 'Poor' / None."""
    t = text.lower()
    if "excellent" in t or "good" in t:
        return "Good"
    if "fair" in t:
        return "Fair"
    if "poor" in t or "inadequate" in t:
        return "Poor"
    return None


_SEVERITY_RE = re.compile(r"\b(severe|marked|moderate|mild|minimal|minor)\b",
                          re.IGNORECASE)


def _label_artifact_severity(text):
    """Return 'Severe' / 'Moderate' / 'Mild' / None."""
    m = _SEVERITY_RE.search(text)
    if not m:
        return None
    sev = m.group(1).lower()
    if sev in {"severe", "marked"}:
        return "Severe"
    if sev == "moderate":
        return "Moderate"
    return "Mild"


def _label_artifact_free(text):
    """Return 'Adequate' / 'Inadequate' / None."""
    t = text.lower()
    if "inadequate" in t:
        return "Inadequate"
    if "adequate" in t:
        return "Adequate"
    return None


_PDR_RANGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[-]\s*(\d+(?:\.\d+)?)\s*hz",
                            re.IGNORECASE)
_PDR_SINGLE_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*hz\b", re.IGNORECASE)


def _label_pdr_freq(text):
    """Return midpoint Hz of stated PDR range, or single-freq, or None."""
    s = _norm(text)
    # First check for "not clearly demonstrated" etc.
    low = s.lower()
    if ("not clearly demonstrated" in low
            or "no clearly defined" in low
            or "not demonstrated" in low):
        return ("not_demonstrated", None)
    # Look for X-Y Hz in the first 200 chars (close to "Background rhythm")
    head = s[:300]
    m = _PDR_RANGE_RE.search(head)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return ((lo + hi) / 2, lo)
    m = _PDR_SINGLE_RE.search(head)
    if m:
        v = float(m.group(1))
        return (v, v)
    return None


_NOT_DEMONSTRATED_RE = re.compile(
    r"\bnot\b[^.]*?\bdemonstrated\b", re.IGNORECASE)


def _label_drowsiness(text):
    """Return 'Demonstrated' / 'Not demonstrated' / None."""
    t = text.lower()
    if not t:
        return None
    if _NOT_DEMONSTRATED_RE.search(t):
        return "Not demonstrated"
    if any(w in t for w in ["demonstrated", "noted", "diminution",
                            "present"]):
        return "Demonstrated"
    if "none" in t or "no drowsiness" in t:
        return "Not demonstrated"
    return None


def _label_paroxysmal(text):
    """Return 'None' / 'Present' / None."""
    t = text.lower()
    if not t:
        return None
    if t.startswith("none") or t == "none." or "no paroxysmal" in t:
        return "None"
    # Affirmative cue words
    for w in ["spike", "sharp wave", "sharp-wave", "epileptiform",
              "discharge", "paroxysm", "burst of slowing", "slowing"]:
        if w in t:
            return "Present"
    if "none" in t:
        return "None"
    return None


def _label_clinical_abnormality(text):
    """Return 'No' / 'Yes' / None from comments narrative."""
    if not text:
        return None
    t = text.lower()
    # Strong negatives first
    for neg in ["no overt abnormal", "no abnormalities noted",
                "no abnormalities", "no abnormal", "no other overt",
                "no other abnormal", "no overt"]:
        if neg in t:
            return "No"
    # Strong positives
    for pos in ["epileptiform", "spike wave", "spike-wave",
                "sharp wave", "sharp/slowing", "interictal",
                "ictal", "encephalopathy",
                "this is an abnormal eeg", "abnormal eeg",
                "slowing of background", "intermittent slowing",
                "isolated spike", "intermittent left",
                "intermittent right"]:
        if pos in t:
            return "Yes"
    return None


def _author(paras):
    """Return author name (most reports: 'P. David Ims, LCPC, BCN, QEEG-D')."""
    for p in paras:
        low = p.lower()
        if "kerasidis" in low:
            return "Kerasidis"
        if "robert turner" in low or " turner," in low or " turner " in low:
            return "Turner"
        if "ims" in low:
            return "Ims"
    return "Unknown"


# --- public --------------------------------------------------------
def parse_report(path):
    """Return structured fields from a doctor's QA review .docx file.

    Returns dict with the parsed values; sets 'valid' True if at least
    4 of the 7 structured fields parsed to non-None.
    """
    result = {
        "path": path,
        "author": "Unknown",
        "quality": None,
        "artifact_severity": None,
        "artifact_text": "",
        "artifact_free": None,
        "background": "",
        "pdr_freq": None,
        "pdr_freq_lo": None,
        "drowsiness": None,
        "paroxysmal": None,
        "comments": "",
        "clinical_abnormality": None,
        "valid": False,
        "error": "",
    }
    try:
        paras = _gather_paragraphs(path)
    except Exception as e:
        result["error"] = str(e)
        return result

    if not paras:
        result["error"] = "no paragraphs found"
        return result

    result["author"] = _author(paras)

    # Field-by-field extraction
    quality_v = _value_after_header(paras, _FIELD_HEADERS["quality"])
    result["quality"] = _label_quality(quality_v)

    artifact_v = _value_after_header(paras, _FIELD_HEADERS["artifact"])
    result["artifact_text"] = artifact_v
    result["artifact_severity"] = _label_artifact_severity(artifact_v)

    af_v = _value_after_header(paras, _FIELD_HEADERS["artifact_free"])
    result["artifact_free"] = _label_artifact_free(af_v)

    bg_v = _value_after_header(paras, _FIELD_HEADERS["background"])
    result["background"] = bg_v[:600]
    pdr = _label_pdr_freq(bg_v)
    if pdr is not None:
        if pdr[0] == "not_demonstrated":
            result["pdr_freq"] = None
            result["pdr_freq_lo"] = None
        else:
            result["pdr_freq"] = pdr[0]
            result["pdr_freq_lo"] = pdr[1]

    drow_v = _value_after_header(paras, _FIELD_HEADERS["drowsiness"])
    result["drowsiness"] = _label_drowsiness(drow_v)

    par_v = _value_after_header(paras, _FIELD_HEADERS["paroxysmal"])
    result["paroxysmal"] = _label_paroxysmal(par_v)

    com_v = _value_after_header(paras, _FIELD_HEADERS["comments"])
    result["comments"] = com_v[:1000]
    result["clinical_abnormality"] = _label_clinical_abnormality(com_v)

    # Validity: at least 4 of 7 structured fields parsed
    structured = [result["quality"], result["artifact_severity"],
                  result["artifact_free"], result["drowsiness"],
                  result["paroxysmal"], result["clinical_abnormality"],
                  result["pdr_freq"]]
    result["valid"] = sum(1 for v in structured if v is not None) >= 4

    return result


# --- self-test ---------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        for path in sys.argv[1:]:
            print(f"\n=== {os.path.basename(path)} ===")
            r = parse_report(path)
            for k, v in r.items():
                if isinstance(v, str) and len(v) > 120:
                    v = v[:120] + "..."
                print(f"  {k}: {v!r}")
