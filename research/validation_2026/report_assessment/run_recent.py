"""The newest 100 stored studies, most recent first: one report scored with the client
left out (--refit, the honest one) and one from the frozen bundle with no store available.
Everything is written under the store. Log lines carry study ids only.
Files moved in Dropbox since the batch are found again by file name + size."""
import glob, json, os, sqlite3, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
ROOT = r"C:\BrainPanel\clean_eeg_project 2025"
STORE = r"C:\BrainPanel\source_db"
C = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
OUT = os.path.join(STORE, "pdf", "recent100")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
for m in ("refit", "frozen"):
    os.makedirs(os.path.join(OUT, m), exist_ok=True)
con = sqlite3.connect(os.path.join(STORE, "sources.db"))
rows = con.execute("SELECT id, rel_path, status, size_mb FROM studies WHERE rec_start IS NOT NULL "
                   "ORDER BY rec_start DESC").fetchall()
con.close()
by_name = {}
for p in glob.glob(os.path.join(C, "**", "*.edf"), recursive=True):
    by_name.setdefault(os.path.basename(p).lower(), []).append(p)

picked, moved, lost = [], 0, 0
for sid, rel, status, size in rows:
    p = os.path.join(C, rel)
    if not os.path.exists(p):
        hits = by_name.get(os.path.basename(rel).lower(), [])
        hits = [h for h in hits if size is None or abs(os.path.getsize(h) / 1e6 - size) < 0.01 * max(size, 1)]
        if len(hits) != 1:
            lost += 1
            continue
        p = hits[0]
        moved += 1
    picked.append((sid, p, status))
    if len(picked) == N:
        break
print("picked", len(picked), "| found after a move", moved, "| could not be found", lost, flush=True)
json.dump(dict(order=[x[0] for x in picked], status={x[0]: x[2] for x in picked}, moved=moved, lost=lost),
          open(os.path.join(OUT, "order.json"), "w"))


def one(job):
    sid, path, status, mode = job
    d = os.path.join(OUT, mode)
    pdf, js = os.path.join(d, sid + ".edfreport.pdf"), os.path.join(d, sid + ".json")
    if os.path.exists(js):
        return sid, mode, "skip", 0, ""
    cmd = ["py", os.path.join(ROOT, "tools", "edf_report.py"), path, "--out", pdf, "--summary", js]
    npz = os.path.join(STORE, "npz", sid + ".sources.npz")
    if os.path.exists(npz):
        cmd += ["--sidecar", npz]
    cmd += ["--refit"] if mode == "refit" else ["--store", os.path.join(OUT, "no_store_here")]
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    dt = time.time() - t
    # no paths or names in the record: only "unavailable" lines and the exception type
    keep = [l for l in r.stdout.splitlines() if "unavailable" in l or "no Brain Panel" in l]
    err = r.stderr.strip().splitlines()[-1].split(":")[0] if r.returncode else ""
    return sid, mode, r.returncode, round(dt, 1), "; ".join(keep + [err]).strip("; ")


jobs = [(s, p, st, m) for m in ("refit", "frozen") for s, p, st in picked]
log = []
with ThreadPoolExecutor(8) as ex:
    for k, res in enumerate(ex.map(one, jobs)):
        log.append(res)
        if k % 10 == 0:
            print(k, "of", len(jobs), res[:4], flush=True)
        json.dump(log, open(os.path.join(OUT, "run_log.json"), "w"))
print("done", sum(1 for r in log if r[2] == 0), "ok", sum(1 for r in log if r[2] not in (0, "skip")), "failed", flush=True)
