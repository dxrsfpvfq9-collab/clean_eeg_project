"""Compare two Brain Panel PDFs metric-by-metric.

Deployment acceptance check: run a study that already has a known-good panel
from the CURRENT server, re-run it after the update, and confirm that Global
STD is the ONLY row that moved.

    py verify_panel.py "<before>.icale.rep.pdf" "<after>.icale.rep.pdf"

Exit code 0 = only Global STD changed (the expected result).
Exit code 1 = some other metric moved; do not promote the build.

Self-contained: needs only pypdf (or PyPDF2), both of which the server
already has for report generation.
"""
import re
import sys

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader

# Canonical 48-metric order, matching edftotextbynameplotproc.py name_strings.
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

_NUM = re.compile(r"^[+-]?\d+(?:\.\d+)?$")

# Metrics allowed to differ. Global STD is the point of the update.
EXPECTED_TO_CHANGE = {'Global STD'}

# Z-scores are printed to 2 decimals, so anything at or below this is a
# rounding artifact rather than a real move.
TOL = 0.01


def panel_values(path):
    """{metric: (value, z)} parsed from the report's metrics table.

    Each metric renders as five consecutive lines: Parameter, Value, Typ,
    Z-Score, Range. Range contains a dash, so taking the first three numeric
    tokens after the name gives Value/Typ/Z.
    """
    text = "\n".join((pg.extract_text() or "") for pg in PdfReader(path).pages)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out = {}
    for name in NAME_STRINGS:
        for i, line in enumerate(lines):
            if line == name:
                nums = [x for x in lines[i + 1:i + 6] if _NUM.match(x)][:3]
                if len(nums) == 3:
                    out[name] = (float(nums[0]), float(nums[2]))
                break
    return out


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    before_path, after_path = sys.argv[1], sys.argv[2]
    before, after = panel_values(before_path), panel_values(after_path)

    missing = [n for n in NAME_STRINGS if n not in before or n not in after]
    if missing:
        print("WARNING: could not parse %d metric(s): %s"
              % (len(missing), ", ".join(missing)))

    print("%-20s %11s %11s %10s %10s"
          % ("metric", "before", "after", "z before", "z after"))
    print("-" * 68)

    unexpected = []
    for name in NAME_STRINGS:
        if name in missing:
            continue
        bv, bz = before[name]
        av, az = after[name]
        moved = abs(az - bz) > TOL or abs(av - bv) > TOL
        if not moved:
            continue
        tag = "  <- expected" if name in EXPECTED_TO_CHANGE else "  <<< UNEXPECTED"
        if name not in EXPECTED_TO_CHANGE:
            unexpected.append(name)
        print("%-20s %11.2f %11.2f %10.2f %10.2f%s"
              % (name, bv, av, bz, az, tag))

    print("-" * 68)
    if unexpected:
        print("FAIL: %d metric(s) moved that should not have: %s"
              % (len(unexpected), ", ".join(unexpected)))
        print("Do not promote this build.")
        return 1
    print("PASS: only Global STD changed. Panel is otherwise identical.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
