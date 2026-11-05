"""The EDF Analysis Report's frozen reference: one JSON file holding every fitted
number the report scores against, so a report needs no source database (that
store's paths carry patient names and cannot leave this workstation) and no refit.
The same EDF and the same bundle give the same report.

Built by tools/freeze_models.py. Reading it needs only numpy and the standard
library: no sqlite, no sklearn, no pickles, so it does not depend on the versions
installed on a server.

What is in it: coefficients, aggregate counts, and quantile tables. Nothing per
study: no ids, client hashes, paths or names. Reference distributions are kept
as 201 quantiles rather than one value per client.

Limit: a frozen model cannot leave a client out. A returning client whose earlier
study is in the reference is scored by a model that contains it. One study in
about 440 per condition moves these fits very little, but it means the bundle is
not an honest test of accuracy: validate with `edf_report.py --refit`, which
leaves the client out, on this workstation.
"""
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(ROOT, "models", "edf_report_models.json")
FORMAT = 1
BODY_KEYS = ("format", "counts", "reference", "group_stats", "source", "coupling", "drowsiness")


def body_hash(bundle):
    """Hash of the fitted numbers only, so rebuilding the same fits on another
    day gives the same hash."""
    body = {k: bundle[k] for k in BODY_KEYS}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load(path=DEFAULT_PATH):
    """The bundle, or an exception. A damaged or foreign file must stop the report:
    wrong numbers would print as confident percentiles."""
    with open(path, encoding="utf-8") as fh:
        b = json.load(fh)
    if b.get("format") != FORMAT:
        raise ValueError(f"{path}: format {b.get('format')!r}, this code reads {FORMAT}")
    if body_hash(b) != b.get("sha256"):
        raise ValueError(f"{path}: contents do not match the stored hash")
    return b
