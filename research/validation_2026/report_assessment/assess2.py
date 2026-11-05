"""Follow-ups: doctor's report fields, age recovery, test-retest, findings against all labelled
studies, cover problems. Aggregates and study ids only: text is masked to clinical vocabulary."""
import collections, glob, json, os, re, sqlite3, sys
import numpy as np
ROOT = r"C:\BrainPanel\clean_eeg_project 2025"
sys.path[:0] = [ROOT, os.path.join(ROOT, "research", "validation_2026"), os.path.join(ROOT, "tools")]
import dr_report_parser as P
from cascade_label_join_2026 import find_report
from label_join import auc
import edf_report as ER
STORE = r"C:\BrainPanel\source_db"
C = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
OUT = os.path.join(STORE, "pdf", "recent100")
order = json.load(open(os.path.join(OUT, "order.json")))["order"]
con = sqlite3.connect(os.path.join(STORE, "sources.db"))
meta = {r[0]: r[1:] for r in con.execute("SELECT id, rel_path, cond, age, client, rec_start FROM studies")}
R = {s: json.load(open(os.path.join(OUT, "refit", s + ".json"))) for s in order}
by_name = {}
for p in glob.glob(os.path.join(C, "**", "*.edf"), recursive=True):
    by_name.setdefault(os.path.basename(p).lower(), []).append(p)


def where(s):
    p = os.path.join(C, meta[s][0])
    if os.path.exists(p):
        return p
    h = by_name.get(os.path.basename(meta[s][0]).lower(), [])
    return h[0] if len(h) == 1 else None


print("== doctor's report fields, newest 100")
vocab = set("""good fair poor excellent adequate inadequate mild mildly moderate moderately severe marked minimal minor significant
muscle emg myogenic eye blink movement electrode line artifact artifacts no none some few frequent occasional present
free most majority all portions of the recording eeg quality overall""".split())
tally = {f: collections.Counter() for f in ("quality", "artifact", "artifact_free")}
gr = []
abn = collections.Counter()
pdf_ct = collections.Counter()
age_found = collections.Counter()
for s in order:
    p = where(s)
    if not p:
        continue
    try:
        rp, _ = find_report(os.path.dirname(p), os.path.basename(p)[:-4])
    except Exception:
        rp = None
    pdf_ct["report found" if rp else "no report"] += 1
    # EDF header birthdate / age recovery for no-age studies
    if R[s].get("age") is None:
        with open(p, "rb") as fh:
            h = fh.read(168).decode("latin1")
        age_found["edf patient field has a birth date"] += bool(re.search(r"\b\d{2}-[A-Za-z]{3}-\d{4}\b", h[8:88]))
        age_found["no-age studies"] += 1
        if rp:
            try:
                par = " ".join(P._gather_paragraphs(rp)).lower()
                age_found["report states an age"] += bool(re.search(r"\b\d{1,2}[- ]?(year|yr|y/?o)|\bage:?\s*\d{1,2}\b", par))
                age_found["report found"] += 1
            except Exception:
                pass
    if not rp:
        continue
    try:
        par = P._gather_paragraphs(rp)
    except Exception:
        continue
    vals = {f: (P._value_after_header(par, P._FIELD_HEADERS[f]) or "") for f in tally}
    for f in tally:
        t = re.sub(r"[^a-z ]", " ", vals[f].lower())
        t = re.sub(r"(_ )+_?", "_ ", " ".join(w if w in vocab else "_" for w in t.split())).strip()
        tally[f][t[:50]] += 1
    gr.append((s, R[s]["grade"], vals["quality"].lower(), vals["artifact"].lower()))
for f in tally:
    print(f, tally[f].most_common(8))
ql = lambda t: "good" if ("good" in t or "excellent" in t) else "fair" if "fair" in t else "poor" if ("poor" in t or "inadequate" in t) else "?"
print("grade x doctor quality", sorted(collections.Counter((g, ql(q)) for _s, g, q, _a in gr).items()))
mus = lambda a: "muscle" in a or "emg" in a or "myogenic" in a
ar = [(R[s]["tiles"]["rel_hibeta_mean"]["z"], mus(a)) for s, _g, _q, a in gr if R[s].get("tiles", {}).get("rel_hibeta_mean")]
if ar:
    a = np.array(ar, float)
    print("fast z vs muscle in the artifact field: positives", int(a[:, 1].sum()), "of", len(a), "AUC", round(auc(a[:, 0], a[:, 1]), 2) if 0 < a[:, 1].sum() < len(a) else None)
print("age recovery", dict(age_found))

print("\n== alpha peak: reports vs reader")
pdr = {r[0]: r[1] for r in con.execute("SELECT study_id, hz FROM report_pdr")}
rows = [(meta[s][2], R[s]["tiles"]["paf_post"]["value"], pdr[s]) for s in order if s in pdr and pdr[s] and R[s].get("tiles", {}).get("paf_post")]
print("EC pairs (report Hz, reader Hz) off by > 1 Hz", [(round(a, 1), b) for c, a, b in rows if c == "EC" and abs(a - b) > 1])
print("'Not found' by condition", collections.Counter(R[s]["cond"] for s in order if R[s].get("age") and "paf_post" not in R[s].get("tiles", {})))

print("\n== cover gaps")
keys = collections.Counter(a for s in order for a in R[s].get("assoc", []) if R[s].get("age"))
miss = {k: v for k, v in keys.items() if tuple([k.split(":")[0], int(k.split(":")[1])]) not in ER.ASSOCIATIONS}
print("findings", sum(keys.values()), "with no association text", sum(miss.values()), miss)
print("reports with a finding but no association text at all", sum(1 for s in order if R[s].get("assoc") and R[s].get("age") and not any(tuple([k.split(':')[0], int(k.split(':')[1])]) in ER.ASSOCIATIONS for k in R[s]["assoc"])))
qd = collections.Counter(re.sub(r"\d+%?", "#", q) for s in order for q in [R[s].get("quality", "")] if R[s].get("grade") == "Fair")
print("why fair", qd.most_common(6))
stand_src = collections.Counter()
for s in order:
    if R[s].get("age") and R[s]["n_stand"]:
        rw = dict(map(tuple, R[s]["rows"]))
        only_desc = not R[s]["assoc"]
        stand_src["source/coupling only"] += only_desc
        stand_src["has rhythm finding"] += not only_desc
print("what stands out", stand_src)

print("\n== all labelled corpus: findings vs doctor (stored scores, one study per client per condition)")
tiles = [t[0] for t in ER.TILES]
z = collections.defaultdict(dict)
for sid, f, v in con.execute(f"SELECT study_id, feature, z FROM ref_z WHERE feature IN ({','.join('?' * len(tiles))})", tiles):
    z[sid][f] = v
lab = collections.defaultdict(dict)
for s, o, v in con.execute("SELECT study_id, outcome, value FROM labels WHERE conf='high'"):
    lab[s][o] = v
atyp = dict(con.execute("SELECT study_id, atyp_pctile FROM source_atyp"))
seen, keep = set(), []
for s in sorted(z, key=lambda s: meta[s][4] or ""):
    k = (meta[s][3] or s, meta[s][1])
    if k not in seen and lab[s] and meta[s][1] in ("EC", "EO"):
        seen.add(k)
        keep.append(s)
for cond in ("EC", "EO"):
    S = [s for s in keep if meta[s][1] == cond]
    n_flag = {s: sum(abs(v) >= 2 for v in z[s].values() if v is not None) for s in S}
    print(cond, "studies", len(S))
    for o in ("clinical_abnorm", "drowsiness", "paroxysmal", "pdr_slow"):
        T = [s for s in S if o in lab[s]]
        y = np.array([lab[s][o] for s in T], float)
        x = np.array([n_flag[s] for s in T], float)
        any_rate = [100 * np.mean(x[y == v] >= 1) for v in (1, 0)]
        print(f"  {o}: positives {int(y.sum())}, count-of-six AUC {auc(x, y):.2f}, any flag {any_rate[0]:.0f}% of positives vs {any_rate[1]:.0f}% of negatives", end="")
        T2 = [s for s in T if atyp.get(s) is not None]
        if T2:
            print(f" | source verdict AUC {auc(np.array([atyp[s] for s in T2]), np.array([lab[s][o] for s in T2], float)):.2f}", end="")
        print()
    T = [s for s in S if "pdr_slow" in lab[s] and z[s].get("paf_post") is not None]
    y = np.array([lab[s]["pdr_slow"] for s in T], float)
    x = np.array([z[s]["paf_post"] for s in T])
    low = x <= -2
    print(f"  slow alpha flag: AUC {auc(-x, y):.2f}; flagged {int(low.sum())}, reader agreed {int(y[low].sum())}; reader-slow {int(y.sum())}, caught {int(y[low].sum())}")

print("\n== test-retest: same client, same condition, different recording, stored z")
by = collections.defaultdict(list)
for s in z:
    if meta[s][3] and meta[s][5] and meta[s][1] in ("EC", "EO") and meta[s][2] is not None:
        by[(meta[s][3], meta[s][1])].append(s)
from datetime import datetime as D
pairs = {"<= 1 day": [], "2-90 days": [], "> 90 days": []}
for k, v in by.items():
    v = sorted(v, key=lambda s: meta[s][4])
    for a, b in zip(v, v[1:]):
        try:
            d = (D.fromisoformat(meta[b][4]) - D.fromisoformat(meta[a][4])).total_seconds() / 86400
        except Exception:
            continue
        if d < 60 / 86400 or all(z[a].get(f) == z[b].get(f) for f in tiles):
            continue      # the same recording filed twice
        pairs["<= 1 day" if d <= 1 else "2-90 days" if d <= 90 else "> 90 days"].append((a, b))
for name, P2 in pairs.items():
    print(name, "pairs", len(P2))
    if len(P2) < 10:
        continue
    for f in tiles:
        xy = np.array([(z[a][f], z[b][f]) for a, b in P2 if z[a].get(f) is not None and z[b].get(f) is not None])
        if len(xy) < 10:
            continue
        fl = np.abs(xy) >= 2
        either = fl.any(axis=1).sum()
        print(f"  {f}: n {len(xy)} r {np.corrcoef(xy.T)[0, 1]:.2f}; flagged in either {int(either)}, in both {int(fl.all(axis=1).sum())}")
