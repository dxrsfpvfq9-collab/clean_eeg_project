"""Freeze the EDF Analysis Report's models out of the source database into one
de-identified file (see tools/report_models.py). Workstation only: it reads the
store. Re-run after reference_ranges, source_norms or vigilance_features change,
or after the batch adds studies; each build has its own version, printed on the
report.

    py tools/freeze_models.py [--store DIR] [--out JSON]

Refuses to write if any study id or client hash from the database appears in
the file, or if the numpy drowsiness scorer disagrees with sklearn.
"""
import argparse
import datetime as dt
import json
import os
import sqlite3
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coupling_norms                              # noqa: E402
import drowsiness_model                            # noqa: E402
import edf_report                                  # noqa: E402
import report_models                               # noqa: E402
import source_norms                                # noqa: E402

N_QUANTILES = 201


def quantiles(sorted_values):
    """A reference distribution as a fixed grid, in place of one value per client."""
    v = np.asarray(sorted_values, float)
    return np.quantile(v, np.linspace(0, 1, N_QUANTILES)).round(4).tolist()


def freeze_reference(con):
    out = {}
    for cond in ("EC", "EO"):
        out[cond] = {}
        for f, t, mc, sc, rz, n, amin, amax in con.execute(
                "SELECT feature, transform, mean_coef, sd_coef, resid_z, n, age_min, age_max "
                "FROM ref_models WHERE cond=? ORDER BY feature", (cond,)):
            out[cond][f] = dict(transform=t, mean_coef=json.loads(mc), sd_coef=json.loads(sc),
                                resid_z=quantiles(json.loads(rz)), n=n, age_min=amin, age_max=amax)
    return out


def freeze_source(con):
    out = {}
    for cond in ("EC", "EO"):
        rows = {r[0]: r[1:] for r in con.execute(
            "SELECT cell, logit_coef, mean_coef, sd_coef FROM source_models WHERE cond=?", (cond,))}
        mc, sc, rz, n = con.execute(
            "SELECT mean_coef, sd_coef, resid_z, n FROM source_calib WHERE cond=?", (cond,)).fetchone()
        out[cond] = dict(
            cells=source_norms.CELLS,
            models=[dict(logit=json.loads(rows[c][0]), mean=json.loads(rows[c][1]), sd=json.loads(rows[c][2]))
                    for c in source_norms.CELLS],
            calib=dict(mean=json.loads(mc), sd=json.loads(sc), resid=quantiles(json.loads(rz))),
            n=n)
    return out


def freeze_coupling(con):
    pairs = coupling_norms.load_pairs(con)
    st, ref = coupling_norms.reference(con, pairs)
    out = {}
    for cond in ("EC", "EO"):
        m = coupling_norms.fit(ref[cond], st, pairs)
        out[cond] = dict(
            links={t: [list(v[0]), list(v[1]), v[2]] for t, v in sorted(m["links"].items())},
            bands={b: dict(mean=v["mean"].tolist(), sd=v["sd"].tolist(), resid=quantiles(v["resid"]), n=v["n"])
                   for b, v in m["bands"].items()},
            n=m["n"])
    return out


def build(store):
    con = sqlite3.connect(f"file:{os.path.join(store, 'sources.db')}?mode=ro", uri=True)
    reference = freeze_reference(con)
    group = {c: list(edf_report.group_stats(store, c)) for c in ("EC", "EO")}
    source = freeze_source(con)
    coupling = freeze_coupling(con)
    con.close()
    drowsy = drowsiness_model.fit_note(store, check=True)
    b = dict(
        format=report_models.FORMAT,
        counts={c: dict(reference_clients=reference[c]["paf_post"]["n"], source_clients=source[c]["n"],
                        coupling_clients=coupling[c]["n"]) for c in ("EC", "EO")},
        reference=reference, group_stats=group, source=source, coupling=coupling, drowsiness=drowsy)
    b["counts"]["EC"]["drowsiness_studies"] = drowsy["n"]
    sha = report_models.body_hash(b)
    b["sha256"] = sha
    b["version"] = f"{dt.date.today():%Y-%m-%d}.{sha[:8]}"
    return b


def privacy_check(text, store):
    """Fail on any study id or client hash from the database."""
    con = sqlite3.connect(f"file:{os.path.join(store, 'sources.db')}?mode=ro", uri=True)
    keys = {k for row in con.execute("SELECT id, client FROM studies") for k in row if k}
    con.close()
    hits = [k for k in keys if k in text]
    if hits:
        raise SystemExit(f"REFUSED: {len(hits)} study or client key(s) found in the bundle")
    if ".edf" in text.lower() or "dropbox" in text.lower() or ":\\\\" in text:
        raise SystemExit("REFUSED: a file path found in the bundle")
    return len(keys)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=source_norms.DEFAULT_STORE)
    ap.add_argument("--out", default=report_models.DEFAULT_PATH)
    a = ap.parse_args()
    b = build(a.store)
    text = json.dumps(b, sort_keys=True, indent=0)
    n = privacy_check(text, a.store)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    report_models.load(a.out)
    print("version", b["version"])
    print("counts", b["counts"])
    print(f"checked against {n} study and client keys, none present")
    print(f"wrote {a.out} ({os.path.getsize(a.out) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
