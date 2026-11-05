"""Assess the 100 reports against the doctor's reports. Prints aggregates and study ids only:
report text, names and paths are read but never printed. Accuracy uses the client-left-out runs."""
import collections, glob, json, os, re, sqlite3, sys
import numpy as np
ROOT = r"C:\BrainPanel\clean_eeg_project 2025"
sys.path[:0] = [os.path.join(ROOT, "research", "validation_2026"), os.path.join(ROOT, "tools")]
import dr_report_parser as P
from cascade_label_join_2026 import find_report
from label_join import auc
STORE = r"C:\BrainPanel\source_db"
C = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
OUT = os.path.join(STORE, "pdf", "recent100")
order = json.load(open(os.path.join(OUT, "order.json")))
ids = order["order"]
log = json.load(open(os.path.join(OUT, "run_log.json")))
con = sqlite3.connect(os.path.join(STORE, "sources.db"))
meta = {r[0]: r[1:] for r in con.execute("SELECT id, rel_path, cond, age, client, rec_start, size_mb, status FROM studies")}
lab = collections.defaultdict(dict)
for s, o, v, cf in con.execute("SELECT study_id, outcome, value, conf FROM labels WHERE conf='high'"):
    lab[s][o] = v
pdr = {r[0]: r[1] for r in con.execute("SELECT study_id, hz FROM report_pdr")}
def J(mode, s):
    p = os.path.join(OUT, mode, s + ".json")
    return json.load(open(p)) if os.path.exists(p) else None
R = {s: J("refit", s) for s in ids}
F = {s: J("frozen", s) for s in ids}
all_ok = [s for s in ids if R[s]]
for s in all_ok:
    R[s].setdefault("tiles", {}); F[s].setdefault("tiles", {})
ok = [s for s in all_ok if R[s]["age"] is not None]     # with no age nothing is scored
print("no age:", len(all_ok) - len(ok), "of", len(all_ok), "| corpus ok studies with no age:",
      con.execute("SELECT SUM(age IS NULL), COUNT(*) FROM studies WHERE status='ok'").fetchone(),
      "| no condition:", con.execute("SELECT SUM(cond NOT IN ('EC','EO') OR cond IS NULL), COUNT(*) FROM studies WHERE status='ok'").fetchone())
print(f"== RUN: {len(ids)} picked, moved {order['moved']}, unfindable {order['lost']}")
print("date range", meta[ids[-1]][4][:10], "to", meta[ids[0]][4][:10])
for m in ("refit", "frozen"):
    L = [x for x in log if x[1] == m]
    t = np.array([x[3] for x in L if x[2] == 0])
    print(m, "ok", sum(x[2] == 0 for x in L), "failed", sum(x[2] not in (0, "skip") for x in L),
          "time median/max s", np.median(t).round(1), t.max().round(1), "errors", collections.Counter(x[4] for x in L if x[2] not in (0,)))
    print("   messages", collections.Counter(x[4] for x in L if x[2] == 0 and x[4]).most_common(6))
print("conds", collections.Counter(R[s]["cond"] for s in ok), "| cond not in file name", sum(1 for s in ok if any("Condition" in n for n in R[s]["notes"])),
      "| age None", sum(R[s]["age"] is None for s in ok), "| clients", len({meta[s][3] for s in ok}))
print("age bands", collections.Counter("<18" if R[s]["age"] and R[s]["age"] < 18 else "65+" if R[s]["age"] and R[s]["age"] >= 65 else "18-64" if R[s]["age"] else "none" for s in ok))
print("sections", collections.Counter(tuple(R[s]["contents"]) for s in ok).most_common())

# ---- frozen vs refit
print("\n== FROZEN vs CLIENT-LEFT-OUT")
both = [s for s in ok if F[s]]
dz, dp = [], []
for s in both:
    for f, v in R[s].get("tiles", {}).items():
        w = F[s].get("tiles", {}).get(f)
        if w:
            dz.append(abs(v["z"] - w["z"])); dp.append(abs(v["pct"] - w["pct"]))
print("n", len(both), "tile z max diff", np.max(dz).round(3), "pct mean/max diff", np.mean(dp).round(2), np.max(dp).round(1))
print("same headline count", sum(R[s]["n_stand"] == F[s]["n_stand"] for s in both), "same assoc", sum(R[s]["assoc"] == F[s]["assoc"] for s in both))
print("same every row status", sum(R[s]["rows"] == F[s]["rows"] for s in both))
dd = [(R[s]["drowsy"], F[s]["drowsy"]) for s in both if R[s]["drowsy"] and F[s]["drowsy"]]
print("drowsy same call", sum(a["possible"] == b["possible"] for a, b in dd), "of", len(dd), "| score diff mean", np.mean([abs(a["score"] - b["score"]) for a, b in dd]).round(3))
at = [(R[s]["atyp_pctile"], F[s]["atyp_pctile"]) for s in both if R[s]["atyp_pctile"] is not None and F[s]["atyp_pctile"] is not None]
print("atyp pct mean diff", np.mean([abs(a - b) for a, b in at]).round(2), "| coupling pct mean diff", end=" ")
cd = [abs(R[s]["coupling"][b]["pct"] - F[s]["coupling"][b]["pct"]) for s in both if R[s]["coupling"] and F[s]["coupling"] for b in R[s]["coupling"] if R[s]["coupling"][b]["pct"] is not None]
print(np.mean(cd).round(2), "max", np.max(cd).round(1))
print("frozen scored more extreme (overfit check): mean |z| refit", np.mean([abs(v["z"]) for s in both for v in R[s]["tiles"].values()]).round(3), "frozen", np.mean([abs(v["z"]) for s in both for v in F[s]["tiles"].values()]).round(3))

# ---- what the reports say
print("\n== WHAT THE REPORTS SAY")
n = np.array([R[s]["n_stand"] for s in ok])
print("headline count dist", sorted(collections.Counter(n.tolist()).items()), "| nothing stands out", int((n == 0).sum()))
print("grade", collections.Counter(R[s]["grade"] for s in ok))
print("assoc", collections.Counter(a for s in ok for a in R[s]["assoc"]).most_common())
print("tile flag rates", {f: round(np.mean([abs(R[s]["tiles"][f]["z"]) >= 2 for s in ok if f in R[s]["tiles"]]) * 100) for f in R[ok[0]]["tiles"] if any(f in R[s]["tiles"] for s in ok)})
print("rows", collections.Counter((a, b) for s in ok for a, b in R[s]["rows"] if a in ("Signs of drowsiness", "Where the activity comes from", "How brain areas work together", "Speed of the main resting rhythm")).most_common(14))
oob = [R[s]["n_oob"] for s in ok if R[s]["n_oob"] is not None]
print("panel present", len(oob), "n_oob median", np.median(oob))
for c in ("EC", "EO"):
    v = [R[s]["n_oob"] for s in ok if R[s]["n_oob"] is not None and R[s]["cond"] == c]
    print("  ", c, "n_oob median", np.median(v) if v else None, "IQR", np.percentile(v, [25, 75]) if v else None, "| n_stand median", np.median([R[s]["n_stand"] for s in ok if R[s]["cond"] == c]))

# ---- doctor's report
print("\n== AGAINST THE DOCTOR'S REPORT")
by_name = {}
for p in glob.glob(os.path.join(C, "**", "*.edf"), recursive=True):
    by_name.setdefault(os.path.basename(p).lower(), []).append(p)
doc = {}
for s in ok:
    rel = meta[s][0]; p = os.path.join(C, rel)
    if not os.path.exists(p):
        h = by_name.get(os.path.basename(rel).lower(), [])
        if len(h) != 1:
            continue
        p = h[0]
    try:
        rp, _ = find_report(os.path.dirname(p), os.path.basename(p)[:-4])
        par = P._gather_paragraphs(rp)
    except Exception:
        continue
    d = {}
    for f in P._FIELD_HEADERS:
        try:
            d[f] = (P._value_after_header(par, P._FIELD_HEADERS[f]) or "").lower()
        except Exception:
            d[f] = ""
    doc[s] = d
print("reports found", len(doc), "of", len(ok))
noage = [s for s in all_ok if R[s]["age"] is None]
print("no-age studies with a doctor's label", sum(1 for s in noage if lab[s]), "of", len(noage))
yes = {"Good": 0, "Fair": 1, "Poor": 2}
qq = [(R[s]["grade"], P._label_quality(doc[s]["quality"])) for s in doc]
print("quality report x doctor", sorted(collections.Counter(qq).items(), key=str))
sev = lambda t: "muscle" in t or "emg" in t or "myogenic" in t
hib = [(R[s]["tiles"]["rel_hibeta_mean"]["z"], sev(doc[s]["artifact"] + doc[s]["comments"])) for s in doc if "rel_hibeta_mean" in R[s]["tiles"]]
if hib:
    a = np.array(hib, float); print("fast z vs doctor mentions muscle: positives", int(a[:, 1].sum()), "of", len(a), "AUC", round(auc(a[:, 0], a[:, 1]), 2) if 0 < a[:, 1].sum() < len(a) else None)
print("artifact-severity x report grade", sorted(collections.Counter((R[s]["grade"], P._label_artifact_severity(doc[s]["artifact"])) for s in doc).items(), key=str))
def ab(name, score, y):
    x = np.array(score, float); y = np.array(y, float)
    k = np.isfinite(x)
    x, y = x[k], y[k]
    pos = int(y.sum())
    print(f"  {name}: n {len(y)} positives {pos} AUC", round(auc(x, y), 2) if 0 < pos < len(y) else None)
for c in ("EC", "EO", None):
    S = [s for s in ok if lab[s] and (c is None or R[s]["cond"] == c)]
    print(f" labelled {c or 'all'}: {len(S)}")
    if not S:
        continue
    for o in ("clinical_abnorm", "drowsiness", "paroxysmal", "pdr_slow"):
        T = [s for s in S if o in lab[s]]
        y = [lab[s][o] for s in T]
        ab(f"{o} ~ headline count", [R[s]["n_stand"] for s in T], y)
        ab(f"{o} ~ panel n_oob", [R[s]["n_oob"] if R[s]["n_oob"] is not None else np.nan for s in T], y)
        if o == "drowsiness":
            T2 = [s for s in T if R[s]["drowsy"]]
            ab("   drowsy score", [R[s]["drowsy"]["score"] for s in T2], [lab[s][o] for s in T2])
            for call in (True, False):
                V = [lab[s][o] for s in T2 if R[s]["drowsy"]["possible"] == call]
                print(f"     possible={call}: n {len(V)} reader noted {sum(V)}")
        if o == "pdr_slow":
            T2 = [s for s in T if "paf_post" in R[s]["tiles"]]
            ab("   PAF z (inverted)", [-R[s]["tiles"]["paf_post"]["z"] for s in T2], [lab[s][o] for s in T2])
hz = [(R[s]["tiles"]["paf_post"]["value"], pdr[s]) for s in ok if s in pdr and pdr[s] and "paf_post" in R[s]["tiles"] and R[s]["cond"] == "EC"]
if hz:
    a = np.array(hz); from scipy.stats import spearmanr
    print(f"reader PDR Hz vs report alpha peak, EC: n {len(a)} rho {spearmanr(a[:, 0], a[:, 1])[0]:.2f}, median |diff| {np.median(np.abs(a[:, 0] - a[:, 1])):.2f} Hz, within 1 Hz {np.mean(np.abs(a[:, 0] - a[:, 1]) <= 1) * 100:.0f}%")
# keyword concordance: band finding in report vs band word in the doctor's text
kw = dict(rel_theta=("theta", 1), rel_delta=("delta", 1), rel_beta=("beta", 1), rel_alpha=("alpha", -1))
for k, (w, d) in kw.items():
    t = []
    for s in doc:
        text = doc[s]["background"] + " " + doc[s]["comments"]
        t.append((f"{k}:{d}" in R[s]["assoc"], w in text))
    print(f"band {k} flagged x doctor's word '{w}':", sorted(collections.Counter(t).items()))
# ---- clean-reader vs not
clean = [s for s in ok if lab[s].get("clinical_abnorm") == 0 and lab[s].get("drowsiness") == 0 and lab[s].get("paroxysmal") == 0]
print("reader: no clinical, drowsy or paroxysmal comment", len(clean), "| headline zero among them", sum(R[s]["n_stand"] == 0 for s in clean), "| median count", np.median([R[s]["n_stand"] for s in clean]) if clean else None)
not_clean = [s for s in ok if lab[s] and s not in clean]
print("reader: any such comment", len(not_clean), "| headline zero among them", sum(R[s]["n_stand"] == 0 for s in not_clean), "| median count", np.median([R[s]["n_stand"] for s in not_clean]) if not_clean else None)

# ---- stability
print("\n== STABILITY: same client, close in time")
by = collections.defaultdict(list)
for s in ok:
    by[(meta[s][3], meta[s][4][:10])].append(s)
pairs = [(v[0], v[1]) for v in by.values() if len(v) == 2 and {R[v[0]]["cond"], R[v[1]]["cond"]} == {"EC", "EO"}]
print("EC/EO same-day pairs", len(pairs))
for f in ("paf_post", "tbr_cz", "rel_alpha_post", "theta_front", "alpha_asym_f4f3", "rel_hibeta_mean"):
    xy = [(R[a]["tiles"][f]["z"], R[b]["tiles"][f]["z"]) for a, b in pairs if f in R[a]["tiles"] and f in R[b]["tiles"]]
    if len(xy) > 5:
        a = np.array(xy); print(f"  {f}: n {len(a)} r {np.corrcoef(a.T)[0, 1]:.2f}  same flag {np.mean((abs(a[:, 0]) >= 2) == (abs(a[:, 1]) >= 2)) * 100:.0f}%")
print("grade agree", sum(R[a]["grade"] == R[b]["grade"] for a, b in pairs), "of", len(pairs))
print("tile names", list(R[ok[0]]["tiles"]))
print("\nsample ids: EC possible", [s for s in ok if R[s]["drowsy"] and R[s]["drowsy"]["possible"]][:3], "| many flags", sorted(ok, key=lambda s: -R[s]["n_stand"])[:3], "| poor", [s for s in ok if R[s]["grade"] == "Poor"][:3], "| no cond", [s for s in ok if any("Condition" in n for n in R[s]["notes"])][:3], "| zero", [s for s in ok if R[s]["n_stand"] == 0][:3])
