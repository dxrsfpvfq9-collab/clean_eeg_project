"""After the display fixes: did they land, and does the brain-share mark-down track the doctor's artifact
wording? Study ids and numbers only."""
import collections, glob, json, os, re, sqlite3, sys
import fitz
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path[:0] = [os.path.join(ROOT, "research", "validation_2026"), os.path.join(ROOT, "tools")]
import dr_report_parser as P
from cascade_label_join_2026 import find_report
from label_join import auc
ST = r"C:\BrainPanel\source_db"
C = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"
OUT = os.path.join(ST, "pdf", "recent100")
B = os.path.join(OUT, "frozen")
order = json.load(open(os.path.join(OUT, "order.json")))["order"]
J = {s: json.load(open(os.path.join(B, s + ".json"))) for s in order}
scored = [s for s in order if J[s].get("age") is not None]
c = collections.Counter()
overlap = []
for s in order:
    d = fitz.open(os.path.join(B, s + ".edfreport.pdf"))
    c["reports"] += 1
    c[f"{len(d)} pages"] += 1
    for g in d:
        t = g.get_text()
        c["likelihood block"] += "discriminant likelihoods" in t
        c["internal words"] += bool(re.search(r"QA corpus|QA-corpus|tools/|EC_191|\.icale", t))
        c["past the edge"] += sum(b[2] > g.rect.width + 1 or b[3] > g.rect.height + 1 for b in g.get_text("blocks"))
    L = [l for b in d[0].get_text("dict")["blocks"] for l in b.get("lines", [])]
    for i, a in enumerate(L):
        for e in L[i + 1:]:
            r = fitz.Rect(a["bbox"]) & fitz.Rect(e["bbox"])
            if not r.is_empty and r.height > 2.5 and r.width > 5:
                overlap.append(s)
print(dict(c), "| covers with overlapping text", len(set(overlap)))
print("headline now", sorted(collections.Counter(J[s]["n_stand"] for s in scored).items()), "| was (ungrouped)", sorted(collections.Counter(J[s]["n_raw"] for s in scored).items()))
print("grouped reports", sum(J[s]["n_slow_grouped"] > 0 for s in scored), "| grade", collections.Counter(J[s]["grade"] for s in order))
print("too little signal", sum(("Where the activity comes from", "Too little signal") in map(tuple, J[s]["rows"]) for s in order if J[s].get("rows")))
print("nothing stands out and quality good", sum(J[s]["n_stand"] == 0 and J[s]["grade"] == "Good" for s in scored), "of", len(scored))

con = sqlite3.connect(os.path.join(ST, "sources.db"))
rel = dict(con.execute("SELECT id, rel_path FROM studies"))
by_name = {}
for p in glob.glob(os.path.join(C, "**", "*.edf"), recursive=True):
    by_name.setdefault(os.path.basename(p).lower(), []).append(p)
rows = []
for s in order:
    p = os.path.join(C, rel[s])
    if not os.path.exists(p):
        h = by_name.get(os.path.basename(rel[s]).lower(), [])
        if len(h) != 1:
            continue
        p = h[0]
    try:
        rp, _ = find_report(os.path.dirname(p), os.path.basename(p)[:-4])
        par = P._gather_paragraphs(rp)
    except Exception:
        continue
    t = " ".join((P._value_after_header(par, P._FIELD_HEADERS[f]) or "") for f in ("artifact", "artifact_free")).lower()
    if J[s].get("brain_pct") is not None:
        rows.append((J[s]["brain_pct"], bool(re.search(r"inadequate|significant|severe|marked|excessive|limited|moderate", t)), J[s]["grade"]))
a = np.array([(r[0], r[1]) for r in rows], float)
print("doctor uses heavy-artifact words", int(a[:, 1].sum()), "of", len(a), "| AUC of low brain share", round(auc(-a[:, 0], a[:, 1]), 2))
for lo, hi in ((0, 25), (25, 50), (50, 75), (75, 101)):
    k = (a[:, 0] >= lo) & (a[:, 0] < hi)
    print(f"  brain {lo}-{hi}%: n {int(k.sum())}, doctor heavy words {int(a[k, 1].sum())}")
print("grade x doctor heavy words", sorted(collections.Counter((r[2], r[1]) for r in rows).items()))
