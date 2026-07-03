"""Configuration for the Brain Panel validation study."""
import os

# Root of the saved Quality-Assurance corpus (Dropbox).
CORPUS_ROOT = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"

# Repo root (two levels up from this file) so we can import process.discriminant.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Where all CSV / summary outputs land (git-ignored).
OUT_DIR = os.path.join(os.path.dirname(__file__), "out")

# Brain Panel report PDFs and Doctor's Report docx.
PANEL_SUFFIX = ".icale.rep.pdf"          # case-insensitive match
REPORT_GLOB_TOKEN = "STS EEG Quality Assurance Review"  # substring, .docx

# Year-folder marker.
YEAR_FOLDER_SUFFIX = "COMPLETED Q.A. REVIEWS"

# ---- study cohort definition ----------------------------------------------
# Keep only recent panels that all use the SAME ML version. The z-scores depend
# only on (metric algorithms, reference database); the EC_191/192-file database
# is identical across the "BrainML (c)2025" and "Auto Scan (c)2023" titles, so
# both are the same instrument numerically.
#
# COHORT_VERSIONS: which version labels (from panel_parser.classify_version)
# count as in-cohort.
# Strict (default): "BrainML (c)2025" only. This is the only internally
# consistent version -- the v2023_autoscan_192 reports predate the x1000
# Global-STD reconstruction scaling (Global STD z = 2642.7 in v2025 vs a normal
# ~N(0,1) in v2023), so std_global OOB counts are NOT comparable across the two.
# Since std_global is weighted 3x (Artifact) and 4x (EEG Quality) in the
# discriminants, mixing versions would corrupt those detectors.
#   - Strict (default) : ["v2025_brainml"]                       -> 2025-2026.
#   - Pooled (broader) : [...,"v2023_autoscan_192"] (NOT advised for std_global)
COHORT_VERSIONS = ["v2025_brainml"]
MIN_REPORT_YEAR = 2024  # discard older studies

os.makedirs(OUT_DIR, exist_ok=True)


def in_cohort(parsed):
    """True if a parsed panel belongs to the study cohort."""
    return (parsed.get("version") in COHORT_VERSIONS
            and (parsed.get("report_year") or 0) >= MIN_REPORT_YEAR)
