"""Phase C: parse a Doctor's Report .docx into the structured template fields
used by the study comparison chart (columns L-S of the original spreadsheet).

The reports use a fixed clinician template; we slice the text between the seven
known field labels. A cp1252 bullet/non-breaking artifact (shown as a stray
character after each colon) is normalised away.
"""
import re
import zipfile

# Ordered (column, label-regex) for the Doctor's Report template.
FIELDS = [
    ("quality",      r"Overall quality of the EEG"),
    ("artifact",     r"Presence of artifact"),
    ("artifact_free", r"Amount of artifact free portions(?: for quantitative analysis)?"),
    ("background",   r"Background rhythm"),
    ("drowsiness",   r"Drowsiness\s*/\s*Sleep"),
    ("paroxysmal",   r"Presence of paroxysmal disturbances"),
    ("comments",     r"Comments"),
]
FIELD_KEYS = [k for k, _ in FIELDS]

_TAG_P = re.compile(r"</w:p>")
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]+")
# stray cp1252 / control junk that appears right after the field colon
_JUNK = re.compile(r"[-¿•�]")


def docx_text(path):
    """Whitespace-normalised plain text of a .docx."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    t = _TAG_P.sub("\n", xml)
    t = _TAG.sub(" ", t)
    t = _JUNK.sub(" ", t)
    t = _WS.sub(" ", t)
    t = re.sub(r" *\n *", "\n", t)
    return re.sub(r"\n{2,}", "\n", t).strip()


def parse_report(path):
    """Return dict of the 7 template fields + 'full_text' + 'template_ok'.

    Missing fields are "" and lower template_ok. Field value = text between its
    label's colon and the next field label (or a sensible stop).
    """
    out = {k: "" for k in FIELD_KEYS}
    out["full_text"] = ""
    out["template_ok"] = False
    try:
        text = docx_text(path)
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    out["error"] = ""
    out["full_text"] = text

    # locate each field label's colon position
    positions = []
    for key, lbl in FIELDS:
        m = re.search(lbl + r"\s*:", text, re.I)
        positions.append((m.start() if m else None, m.end() if m else None, key))

    found = [(s, e, k) for (s, e, k) in positions if s is not None]
    found.sort()
    n_found = len(found)
    for i, (s, e, key) in enumerate(found):
        # value runs from end of this label to the start of the next found label
        nxt = found[i + 1][0] if i + 1 < len(found) else None
        # also stop at a clinician signature / spectral section if it precedes nxt
        val = text[e:nxt] if nxt is not None else text[e:]
        val = val.strip(" :–-")
        # for the final 'comments', trim trailing signature / boilerplate lines
        if key == "comments":
            val = re.split(r"\n(?:Spectral Analysis|Eyes Closed|Eyes Open)\b", val)[0]
            val = re.split(r"\n[A-Z][A-Za-z.,'\- ]+,\s*(?:LCPC|BCN|QEEG|MD|DO|PhD)\b", val)[0]
        out[key] = _WS.sub(" ", val.replace("\n", " ")).strip()

    out["template_ok"] = n_found >= 6  # tolerate one missing label
    out["n_fields_found"] = n_found
    return out
