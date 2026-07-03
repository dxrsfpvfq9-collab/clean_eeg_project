"""Parse a Brain Panel `.icale.rep.pdf` into its 48 metric z-scores.

The report's page-1/2 metrics table lists each metric as five consecutive
text lines: Parameter, Value, Typ, Z-Score, Range. We anchor on the 48 known
metric names (unique strings, in the exact order produced by
edftotextbynameplotproc.py line ~935) and take the THIRD numeric token after
each name as its z-score (Value, Typ, Z-Score are the first three numerics;
Range contains a dash and is skipped). This is robust to page breaks and to
the group-header words ("PDR", "Diffuse", ...) repeated at the top of pages.
"""
import re

try:
    from pypdf import PdfReader
except ImportError:  # older installs
    from PyPDF2 import PdfReader

# Canonical 48-metric order. MUST match edftotextbynameplotproc.py:935 and the
# row ordering assumed by process/discriminant.py GROUP_INDEXES.
NAME_STRINGS = [
    'STD Raw', 'Global STD', 'PDR Symmetry', 'PDR Synchrony', 'PDR Regulation',
    'PDR Magnitude', 'PDR Sinusoidal', 'PDR Max Post.', 'PDR FFT Width',
    'PDR Max Amplitude', 'PDR Burst Width', 'Beta Max Front', 'Front Alpha Asym',
    'XS Temp. Alpha', 'Alpha Speed', 'Alpha Peak', 'Midline Beta',
    'Focal Delta Index', 'Focal Delta Amp.', 'Focal Theta Index',
    'Focal Theta Amp.', 'Focal HiBeta Index', 'Focal HiBeta Amp.',
    'Focal Beta Index', 'Focal Beta Amp.', 'Frontal Delta', 'Frontal Theta',
    'Frontal Gamma', 'Front Gamma Asym', 'Diffuse Delta', 'Diffuse Theta',
    'Diffuse Hibeta', 'Diffuse Beta', 'Diffuse Gamma', 'Diffuse 60Hz',
    'Fractal Dimension', 'PDR Moment 1', 'PDR Moment 2', 'PDR Moment 3',
    'Beta Moment 1', 'Beta Moment 2', 'Beta Moment 3', 'Theta Moment 1',
    'Theta Moment 2', 'Theta Moment 3', 'Delta Moment 1', 'Delta Moment 2',
    'Delta Moment 3',
]
assert len(NAME_STRINGS) == 48

_NUM_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_WS_RE = re.compile(r"\s+")


def _norm(s):
    return _WS_RE.sub(" ", s.strip())


def _full_text(path):
    reader = PdfReader(path)
    return "\n".join((pg.extract_text() or "") for pg in reader.pages)


_DB_RE = re.compile(r"Database Used:\s*(\S+)")
_NFILES_RE = re.compile(r"Number of files:\s*(\d+)")
_YEAR_RE = re.compile(r"(20\d\d)")


def classify_version(header, database, n_files, has_zscore):
    """Coarse version label from the report header / reference database.

    The z-scores depend only on (metric algorithms, reference database).
    'BrainML (c) 2025' and 'Auto Scan (c) 2023' share the EC_191/192 database
    and 48 metrics, so they are the SAME ML version numerically; the title is
    cosmetic. Different databases (EC/95, NFLAA) are a different version.
    """
    if not has_zscore:
        return "legacy2013_noZ"
    is_ec191 = database.startswith("EC_191") and n_files == "192"
    if not is_ec191:
        return "other_db"
    return "v2025_brainml" if "BrainML" in header else "v2023_autoscan_192"


def extract_findings(path):
    """Return the page-2 'Findings:' block (the Brain Panel's own machine-
    generated comments -> column K of the comparison chart)."""
    try:
        text = _full_text(path)
    except Exception:
        return ""
    m = re.search(r"Findings:\s*(.+)", text, re.S)
    if not m:
        return ""
    body = m.group(1)
    # cut the trailing legal/disclaimer footer
    body = re.split(r"\n\s*Stress Therapy Solutions", body)[0]
    body = re.split(r"\n\s*(?:NOTE:|The end-user|No further warranties)", body)[0]
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    return " | ".join(lines)


def parse_panel_pdf(path):
    """Return a dict with the 48 z-scores and parse diagnostics.

    keys: zscores (list[48], NaN where unparsed), n_parsed (int),
          parse_ok (bool, all 48 found), valid (has Z-Score column AND
          n_parsed>=47), name, report_date, report_year, header, database,
          n_files, version, error.
    """
    out = {"zscores": [float("nan")] * 48, "values": [float("nan")] * 48,
           "typ": [float("nan")] * 48, "n_parsed": 0, "parse_ok": False,
           "valid": False, "name": None, "report_date": None,
           "report_year": None, "header": None, "database": "?",
           "n_files": "?", "version": "unreadable", "error": None}
    try:
        text = _full_text(path)
    except Exception as exc:  # corrupt / unreadable PDF
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out

    lines = [_norm(l) for l in text.splitlines() if _norm(l)]
    name_set = set(NAME_STRINGS)
    has_zscore = "Z-Score" in text

    out["header"] = lines[0] if lines else None
    m = _DB_RE.search(text)
    if m:
        out["database"] = m.group(1)
    m = _NFILES_RE.search(text)
    if m:
        out["n_files"] = m.group(1)

    # Optional metadata.
    for i, l in enumerate(lines):
        if l.startswith("Name:"):
            out["name"] = l[len("Name:"):].strip() or (lines[i + 1] if i + 1 < len(lines) else None)
        elif l.startswith("Date:"):
            out["report_date"] = l[len("Date:"):].strip()
            ym = _YEAR_RE.search(out["report_date"])
            if ym:
                out["report_year"] = int(ym.group(1))

    # Anchor on each metric name in order; advance a cursor so a repeated
    # header word never matches the wrong row.
    cursor = 0
    for mi, name in enumerate(NAME_STRINGS):
        idx = None
        for j in range(cursor, len(lines)):
            if lines[j] == name:
                idx = j
                break
        if idx is None:
            continue  # leave NaN; keep cursor (tolerate one missing row)
        nums = []
        k = idx + 1
        while k < len(lines) and len(nums) < 3:
            cell = lines[k]
            if cell in name_set:
                break  # ran into the next metric -> row was malformed
            if _NUM_RE.match(cell):
                nums.append(float(cell))
            k += 1
        if len(nums) == 3:
            out["values"][mi] = nums[0]   # Value (the raw metric, -> DB column)
            out["typ"][mi] = nums[1]      # Typ (the DB AVG used for this report)
            out["zscores"][mi] = nums[2]  # Z-Score
            out["n_parsed"] += 1
        cursor = idx + 1

    out["parse_ok"] = out["n_parsed"] == 48
    out["valid"] = has_zscore and out["n_parsed"] >= 47
    out["version"] = classify_version(out["header"] or "", out["database"],
                                      out["n_files"], has_zscore)
    return out
