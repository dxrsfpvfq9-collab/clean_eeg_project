"""Follow-ups from reading the PDFs: brain share against the quality line, alarming panel likelihoods
against the cover, slow alpha counted several times. Study ids and numbers only."""
import collections, json, os, re, sqlite3
import fitz
ST = r"C:\BrainPanel\source_db"
OUT = os.path.join(ST, "pdf", "recent100")
B = os.path.join(OUT, "frozen")
order = json.load(open(os.path.join(OUT, "order.json")))["order"]
con = sqlite3.connect(os.path.join(ST, "sources.db"))
pdr = {r[0]: r[1] for r in con.execute("SELECT study_id, hz FROM report_pdr WHERE hz IS NOT NULL")}
lab = collections.defaultdict(dict)
for s, o, v in con.execute("SELECT study_id, outcome, value FROM labels WHERE conf='high'"):
    lab[s][o] = v
J = {s: json.load(open(os.path.join(B, s + ".json"))) for s in order}
scored = [s for s in order if J[s].get("age") is not None]
for s in ("098e152f1778", "9b2d21066e53", "f35bd04f78f5", "94544ea748ea"):
    t = J[s]["tiles"].get("paf_post", {})
    print(s, "report Hz", round(t.get("value", 0), 1), "doctor Hz", pdr.get(s), "brain %", round(J[s]["brain_pct"] or 0), "labels", lab[s])

print("\nbrain share")
bp = [(J[s]["brain_pct"], s) for s in order if J[s].get("brain_pct") is not None]
bands = collections.Counter("<25" if b < 25 else "25-50" if b < 50 else "50-75" if b < 75 else "75+" for b, _ in bp)
print(dict(bands), "of", len(bp))
print("under 50% with a Good quality line", sum(b < 50 and J[s].get("grade") == "Good" for b, s in bp),
      "| and 'nothing stands out'", sum(b < 50 and J[s].get("grade") == "Good" and J[s].get("age") is not None and J[s]["n_stand"] == 0 for b, s in bp))
print("lowest", [(round(b), s) for b, s in sorted(bp)[:6]])

print("\npanel likelihood words")
hi = collections.Counter()
good_but = conflict_par = n = 0
for s in order:
    d = fitz.open(os.path.join(B, s + ".edfreport.pdf"))
    txt = next((g.get_text() for g in d if "Panel discriminant likelihoods" in g.get_text()), None)
    if not txt:
        continue
    n += 1
    L = [x.strip() for x in txt.splitlines()]
    cur = {}
    for i, x in enumerate(L):
        if x in ("Clinical Abnormality", "Drowsiness", "Artifact", "Paroxysmal", "PDR frequency", "EEG Quality"):
            for y in L[i + 1:i + 4]:
                if "Likelihood" in y:
                    cur[x] = y
    for k, v in cur.items():
        if v.startswith("High") or v.startswith("Very High"):
            hi[k] += 1
    if J[s].get("age") is not None and J[s]["grade"] == "Good" and str(cur.get("EEG Quality", "")).startswith(("High", "Very High")):
        good_but += 1
    if J[s].get("age") is not None and J[s]["n_stand"] == 0 and any(str(v).startswith(("High", "Very High")) for v in cur.values()):
        conflict_par += 1
print("reports with the block", n, "| high or very high:", dict(hi))
print("cover says quality good, panel block says EEG quality concern high", good_but)
print("cover says nothing stands out, panel block has a high likelihood", conflict_par)
print("high paroxysmal with a doctor's paroxysmal label", collections.Counter())

print("\none finding counted several ways")
multi = [s for s in scored if J[s]["n_stand"] >= 2]
slowish = [s for s in multi if any(a in J[s]["assoc"] for a in ("rel_theta:1", "rel_theta_front:1", "tbr_cz:1"))]
low_peak = [s for s in slowish if J[s]["tiles"].get("paf_post", {}).get("value", 99) < 8.5]
print("2+ results", len(multi), "| include slow-activity findings", len(slowish), "| of those with an alpha peak under 8.5 Hz", len(low_peak), low_peak[:5])
th = [len([a for a in J[s]["assoc"] if a in ("rel_theta:1", "rel_theta_front:1", "tbr_cz:1", "paf_post:-1", "rel_alpha:-1", "rel_alpha_post:-1")]) for s in multi]
print("slow-type findings per report with 2+", collections.Counter(th))
