"""Build the source database over the QA corpus, newest recording first.

For every EDF under the root this
  1. copies it to <store>/work/<id>.edf -- nothing is written next to the
     Dropbox originals, and the production panels there are never touched;
  2. runs `run_cascade.py` with CLEANEEG_SIDECAR_ONLY=1: one ICA pass (the
     cascade pass, so the pre-ICA line filter is on, as on the servers) and
     only <id>.sources.npz -- no windows, no render (~20-60 s per study);
  3. keeps the sidecar as <store>/npz/<id>.sources.npz (10-20 MB) and loads
     the analysis of tools/source_summary.py into <store>/sources.db:
     components + nodes + network templates, envelope coupling + groups per
     band, a one-row-per-study feature summary, and the 48 panel values /
     z-scores parsed from the study's existing production .icale.rep.pdf.

Resumable: a study already marked ok is skipped (unless --redo). One bad file
is killed at --timeout and recorded, never fatal to the batch.

The store holds file paths (they carry patient names), so it lives OUTSIDE the
repo and outside Dropbox (default C:\\BrainPanel\\source_db). Studies are keyed
by `id` (hash of the relative path); `client` is a hash of the EDF patient
field, so one client's sessions can be grouped without storing the name.
Console and log lines print the id and the masked label only.

Usage:
    py tools/source_batch.py [root] [--store DIR] [--limit N] [--redo] [--list]
                             [--pdf] [--timeout SEC] [--features-only]
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "research", "validation_2026"))

import source_summary as ss                       # noqa: E402
from files.deidentify import deidentify_label     # noqa: E402

DEFAULT_ROOT = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
DEFAULT_STORE = r"C:\BrainPanel\source_db"
POSTERIOR = {"O1", "O2", "OZ", "P3", "P4", "PZ", "T5", "T6"}
MIN_FREE_GB = 20.0

SCHEMA = """
CREATE TABLE IF NOT EXISTS studies (
  id TEXT PRIMARY KEY, rel_path TEXT, folder TEXT, label TEXT, client TEXT,
  cond TEXT, age INTEGER, rec_start TEXT, size_mb REAL,
  status TEXT, error TEXT, runtime_s REAL, code_version TEXT, processed_at TEXT);
CREATE TABLE IF NOT EXISTS components (
  study_id TEXT, rank INTEGER, pct REAL, hz REAL, band TEXT, accept INTEGER, line INTEGER,
  max_site TEXT, x REAL, y REAL, z REAL, side TEXT, lobe TEXT, region TEXT, ba INTEGER,
  n_nodes INTEGER, dmn REAL, sn REAL, ecn REAL, network TEXT,
  PRIMARY KEY (study_id, rank));
CREATE TABLE IF NOT EXISTS nodes (
  study_id TEXT, rank INTEGER, k INTEGER, x REAL, y REAL, z REAL, rel REAL,
  side TEXT, region TEXT, ba INTEGER, PRIMARY KEY (study_id, rank, k));
CREATE TABLE IF NOT EXISTS edges (
  study_id TEXT, band TEXT, rank_a INTEGER, rank_b INTEGER, r REAL, thr REAL, sig INTEGER,
  PRIMARY KEY (study_id, band, rank_a, rank_b));
CREATE TABLE IF NOT EXISTS groups (
  study_id TEXT, band TEXT, k INTEGER, members TEXT, pct REAL, mean_r REAL,
  network TEXT, enrich REAL, PRIMARY KEY (study_id, band, k));
CREATE TABLE IF NOT EXISTS study_features (
  study_id TEXT PRIMARY KEY, n_comp INTEGER, n_accept INTEGER, artifact_pct REAL,
  delta_pct REAL, theta_pct REAL, alpha_pct REAL, beta_pct REAL, gamma_pct REAL,
  post_alpha_pct REAL, dom_post_hz REAL, dom_post_pct REAL,
  dmn_pct REAL, sn_pct REAL, ecn_pct REAL,
  n_edges_theta INTEGER, n_edges_alpha INTEGER, n_edges_beta INTEGER,
  dmn_groups INTEGER, sn_groups INTEGER, ecn_groups INTEGER, feat_json TEXT);
CREATE TABLE IF NOT EXISTS panel (
  study_id TEXT, row INTEGER, name TEXT, value REAL, z REAL, version TEXT, report_date TEXT,
  PRIMARY KEY (study_id, row));
"""


# ------------------------------------------------------------------ corpus
def edf_header(path):
    """(start datetime or None, patient-field hash). The patient field is
    hashed here and never stored or printed."""
    try:
        with open(path, "rb") as fh:
            h = fh.read(256)
        pid = hashlib.sha1(h[8:88].strip()).hexdigest()[:12]
        d, t = h[168:176].decode("ascii", "replace"), h[176:184].decode("ascii", "replace")
        dd, mm, yy = (int(v) for v in d.split("."))
        hh, mi, se = (int(v) for v in t.split("."))
        yy += 2000 if yy < 85 else 1900
        return dt.datetime(yy, mm, dd, hh, mi, se), pid
    except Exception:
        return None, None


def discover(root):
    out = []
    for p in glob.glob(os.path.join(root, "**", "*.edf"), recursive=True):
        low = os.path.basename(p).lower()
        if low.endswith((".clean.edf", ".unclean.edf")) or ".reviewed" in low:
            continue
        rel = os.path.relpath(p, root)
        start, client = edf_header(p)
        mtime = dt.datetime.fromtimestamp(os.path.getmtime(p))
        when = start if (start and start.year >= 2000) else mtime
        base = os.path.basename(p)[:-4]
        m = re.search(r"AGE\s*(\d+)", base, re.IGNORECASE)
        toks = re.findall(r"(?<![a-z])(ec|eo)(?![a-z])", base.lower())   # "_EC" counts too
        out.append(dict(
            id=hashlib.sha1(rel.lower().encode("utf-8")).hexdigest()[:12], path=p, rel=rel,
            folder=rel.split(os.sep)[0], label=deidentify_label(base), client=client,
            cond=toks[-1].upper() if toks else "", age=int(m.group(1)) if m else None,
            when=when, rec_start=start.isoformat() if start else None,
            size_mb=os.path.getsize(p) / 1e6))
    out.sort(key=lambda s: s["when"], reverse=True)
    return out


def code_version():
    try:
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                           text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "files", "process", "tools"],
                               cwd=ROOT, capture_output=True, text=True).stdout.strip()
        return h + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


# ------------------------------------------------------------------ run one
def run_sidecar(st, store, timeout):
    work = os.path.join(store, "work", st["id"])
    os.makedirs(work, exist_ok=True)
    edf = os.path.join(work, st["id"] + ".edf")
    shutil.copy2(st["path"], edf)
    env = dict(os.environ, CLEANEEG_SIDECAR_ONLY="1", PYTHONIOENCODING="utf-8")
    log = os.path.join(store, "logs", st["id"] + ".log")
    with open(log, "w", encoding="utf-8") as fh:
        proc = subprocess.Popen(["py", "run_cascade.py", edf], cwd=ROOT, env=env,
                                stdout=fh, stderr=subprocess.STDOUT)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            shutil.rmtree(work, ignore_errors=True)
            raise RuntimeError(f"timeout after {timeout} s")
    npz = os.path.join(work, st["id"] + ".sources.npz")
    if not os.path.exists(npz):
        tail = open(log, encoding="utf-8", errors="replace").read()[-400:].replace("\n", " | ")
        shutil.rmtree(work, ignore_errors=True)
        raise RuntimeError("no sidecar written; log tail: " + tail)
    dest = os.path.join(store, "npz", st["id"] + ".sources.npz")
    shutil.move(npz, dest)
    shutil.rmtree(work, ignore_errors=True)
    return dest


# ------------------------------------------------------------------ features
def extract(con, sid, npz, pdf_out=None):
    data = ss.load(npz)
    use, res = ss.analyze_networks(data) if data["sources"] is not None else ([], [])
    comps = data["comps"]
    tot = sum(c["pct"] for c in comps) or 1.0
    pc = lambda c: 100 * c["pct"] / tot                                    # noqa: E731
    for t in ("components", "nodes", "edges", "groups", "study_features"):
        con.execute(f"DELETE FROM {t} WHERE study_id=?", (sid,))

    scores = {}
    for c in comps:
        csd = data["csd"][c["idx"]]
        sc = ss.template_scores(data["vox"], csd / (csd.max() or 1.0))
        net = ss.best_template(sc)[0] if c["accept"] else None
        scores[c["rank"]] = (sc, net)
        con.execute("INSERT INTO components VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            sid, c["rank"], pc(c), c["hz"], ss.band_of(c["hz"])[0], int(c["accept"]),
            int(c["line"]), c["site"], *[float(v) for v in c["xyz"]], c["side"], c["lobe"],
            c["region"], c["ba"], len(c["nodes"]), sc["Default mode"], sc["Salience"],
            sc["Executive control"], net))
        for k, nd in enumerate(c["nodes"]):
            con.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?,?,?)", (
                sid, c["rank"], k, *[float(v) for v in nd["xyz"]], nd["rel"], nd["side"],
                nd["region"], nd["ba"]))

    nedge, ngrp = {}, {"Default mode": 0, "Salience": 0, "Executive control": 0}
    for rb in res:
        r, thr = rb["r"], rb["thr"]
        n = 0
        for i in range(len(use)):
            for j in range(i + 1, len(use)):
                sig = int(abs(r[i, j]) >= thr)
                n += sig
                con.execute("INSERT INTO edges VALUES (?,?,?,?,?,?,?)", (
                    sid, rb["band"], use[i]["rank"], use[j]["rank"], float(r[i, j]), thr, sig))
        nedge[rb["band"]] = n
        for k, g in enumerate(rb["groups"]):
            tname, tval = g["tmpl"]
            if tname:
                ngrp[tname] += 1
            con.execute("INSERT INTO groups VALUES (?,?,?,?,?,?,?,?)", (
                sid, rb["band"], k, ",".join(str(use[i]["rank"]) for i in g["members"]),
                g["pct"], g["mean_r"], tname, float(tval)))

    acc = [c for c in comps if c["accept"]]
    share = {b[0]: sum(pc(c) for c in acc if ss.band_of(c["hz"])[0] == b[0]) for b in ss.BANDS}
    post = [c for c in acc if c["site"].upper() in POSTERIOR and 8 <= c["hz"] < 13]
    dom = max(post, key=lambda c: c["pct"]) if post else None
    netpct = {t: sum(pc(c) for c in acc if scores[c["rank"]][1] == t) for t in ngrp}
    feats = dict(
        n_comp=len(comps), n_accept=len(acc), artifact_pct=100 - sum(pc(c) for c in acc),
        delta_pct=share["Delta"], theta_pct=share["Theta"], alpha_pct=share["Alpha"],
        beta_pct=share["Beta"], gamma_pct=share["Gamma"],
        post_alpha_pct=sum(pc(c) for c in post),
        dom_post_hz=dom["hz"] if dom else None, dom_post_pct=pc(dom) if dom else None,
        dmn_pct=netpct["Default mode"], sn_pct=netpct["Salience"], ecn_pct=netpct["Executive control"],
        n_edges_theta=nedge.get("Theta"), n_edges_alpha=nedge.get("Alpha"),
        n_edges_beta=nedge.get("Beta"), dmn_groups=ngrp["Default mode"],
        sn_groups=ngrp["Salience"], ecn_groups=ngrp["Executive control"])
    con.execute("INSERT INTO study_features VALUES (" + ",".join("?" * 22) + ")",
                (sid, *feats.values(), json.dumps(feats)))
    if pdf_out:
        from matplotlib.backends.backend_pdf import PdfPages
        with PdfPages(pdf_out) as pdf:
            ss.page_sources(data, pdf)
            if res:
                ss.page_networks(data, pdf, (use, res))
    return feats


def load_panel(con, sid, edf_path):
    pdfp = edf_path[:-4] + ".icale.rep.pdf"
    if not os.path.exists(pdfp):
        return False
    from panel_parser import parse_panel_pdf, NAME_STRINGS
    p = parse_panel_pdf(pdfp)
    if not p.get("valid"):
        return False
    con.execute("DELETE FROM panel WHERE study_id=?", (sid,))
    for k in range(48):
        con.execute("INSERT INTO panel VALUES (?,?,?,?,?,?,?)", (
            sid, k, NAME_STRINGS[k], p["values"][k], p["zscores"][k], p.get("version"),
            p.get("report_date")))
    return True


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=DEFAULT_ROOT)
    ap.add_argument("--store", default=DEFAULT_STORE)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--pdf", action="store_true", help="also write <store>/pdf/<id>.sources.pdf")
    ap.add_argument("--features-only", action="store_true",
                    help="re-extract features from existing sidecars (after an analysis change)")
    a = ap.parse_args()

    for d in ("npz", "logs", "work", "pdf"):
        os.makedirs(os.path.join(a.store, d), exist_ok=True)
    con = sqlite3.connect(os.path.join(a.store, "sources.db"))
    con.executescript(SCHEMA)
    studies = discover(a.root)
    done = {r[0] for r in con.execute("SELECT id FROM studies WHERE status='ok'")}
    todo = [s for s in studies if a.redo or a.features_only or s["id"] not in done]
    if a.features_only:
        todo = [s for s in todo if os.path.exists(os.path.join(a.store, "npz", s["id"] + ".sources.npz"))]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(studies)} EDFs found, {len(done)} already ok, {len(todo)} to process")
    if a.list:
        for s in todo[:50]:
            print(f"  {s['id']}  {s['when']:%Y-%m-%d}  {s['cond'] or '--'}  {s['label'][-40:]}")
        return
    ver = code_version()
    for k, s in enumerate(todo, 1):
        free = shutil.disk_usage(a.store).free / 1e9
        if free < MIN_FREE_GB:
            print(f"stopping: {free:.0f} GB free")
            break
        t0 = time.time()
        status, err = "ok", None
        try:
            npz = os.path.join(a.store, "npz", s["id"] + ".sources.npz")
            if not a.features_only:
                npz = run_sidecar(s, a.store, a.timeout)
            pdf_out = os.path.join(a.store, "pdf", s["id"] + ".sources.pdf") if a.pdf else None
            feats = extract(con, s["id"], npz, pdf_out)
            has_panel = load_panel(con, s["id"], s["path"])
            msg = (f"alpha {feats['alpha_pct']:.0f}%  artifact {feats['artifact_pct']:.0f}%  "
                   f"panel {'yes' if has_panel else 'no'}")
        except Exception as exc:
            status, err = "error", f"{type(exc).__name__}: {exc}"[:2000]
            msg = err[:120]
            if not isinstance(exc, RuntimeError):
                traceback.print_exc()
        rt = time.time() - t0
        con.execute("INSERT OR REPLACE INTO studies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            s["id"], s["rel"], s["folder"], s["label"], s["client"], s["cond"], s["age"],
            s["rec_start"], s["size_mb"], status, err, rt, ver, dt.datetime.now().isoformat()))
        con.commit()
        print(f"[{k}/{len(todo)}] {s['id']} {s['when']:%Y-%m-%d} {s['cond'] or '--'} "
              f"{status} {rt:5.0f}s  {msg}", flush=True)
    con.close()


if __name__ == "__main__":
    main()
