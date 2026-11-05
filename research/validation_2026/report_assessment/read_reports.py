"""What the 100 finished PDFs actually say: an index, repetition across covers, the cross-check page's
readings, same-session consistency. Masked labels and study ids only. Writes INDEX.md beside the PDFs and
page images of a chosen spread to the folder given as argv[1]."""
import collections, json, os, re, sqlite3, statistics, sys
import fitz
ST = r"C:\BrainPanel\source_db"
OUT = os.path.join(ST, "pdf", "recent100")
B = os.path.join(OUT, "frozen")
IMG = sys.argv[1]
order = json.load(open(os.path.join(OUT, "order.json")))["order"]
con = sqlite3.connect(os.path.join(ST, "sources.db"))
meta = {r[0]: r[1:] for r in con.execute("SELECT id, client, rec_start FROM studies")}
stale, rows, cov, cross = 0, [], {}, collections.Counter()
J = {}
for s in order:
    j = json.load(open(os.path.join(B, s + ".json")))
    J[s] = j
    d = fitz.open(os.path.join(B, s + ".edfreport.pdf"))
    cov[s] = d[0].get_text()
    stale += "Reference models 2026-11-05.20d70a13" not in cov[s] or "BrainMaster BrainPanel / ICA Analysis Report" not in cov[s]
    for g in d:
        t = g.get_text()
        if "Brain Panel cross-check" in t:
            for w in ("CONFLICT", "both high", "both low", "borderline", "panel only", "EDF only"):
                cross[w] += len(re.findall(w, t, re.I))
            cross["reports with the page"] += 1
            cross["reports with a conflict"] += "CONFLICT" in t
    dr = (j.get("drowsy") or {}).get("possible")
    rows.append((s, j.get("age"), j.get("cond"), meta[s][1][:10], len(d), j.get("n_stand") if j.get("age") is not None else None, j.get("grade"),
                 "" if dr is None else "Possible" if dr else "No clear signs", j.get("n_oob")))
print("reports", len(rows), "| not on current models or title", stale)
with open(os.path.join(B, "INDEX.md"), "w", encoding="utf-8") as fh:
    fh.write("# 100 newest studies, newest first\n\n| file | age | cond | recorded | pages | stand out | quality | drowsiness | panel out of range |\n|---|---:|---|---|---:|---:|---|---|---:|\n")
    for r in rows:
        fh.write(f"| {r[0]}.edfreport.pdf | {r[1] if r[1] is not None else 'none'} | {r[2]} | {r[3]} | {r[4]} | {r[5] if r[5] is not None else 'no age'} | {r[6]} | {r[7]} | {r[8] if r[8] is not None else 'no panel'} |\n")

scored = [s for s in order if J[s].get("age") is not None]
print("\nrepetition: cover lines shared across scored reports")
lines = collections.Counter()
for s in scored:
    for l in set(x.strip() for x in cov[s].splitlines() if len(x.strip()) > 30):
        lines[l] += 1
tot = [sum(1 for x in set(y.strip() for y in cov[s].splitlines() if len(y.strip()) > 30)) for s in scored]
same = [sum(lines[x.strip()] >= 0.5 * len(scored) for x in set(y.strip() for y in cov[s].splitlines() if len(y.strip()) > 30)) for s in scored]
print(" median long lines per cover", statistics.median(tot), "| of which on at least half of all covers", statistics.median(same))
print(" distinct covers by (headline count, flagged rows)", len({(J[s]["n_stand"], tuple(map(tuple, J[s]["rows"]))) for s in scored}), "of", len(scored))
inf = collections.Counter()
for s in scored:
    R = dict(map(tuple, J[s]["rows"]))
    non = [k for k, v in R.items() if k != "Brain Panel" and v not in ("Typical", "Mix: typical", "No clear signs")]
    inf["all rows typical"] += not non
    inf["1-2 rows not typical"] += 1 <= len(non) <= 2
    inf["3+ rows not typical"] += len(non) >= 3
print(" how much is on a cover", dict(inf))
print(" a Fair-quality report with results standing out", sum(J[s]["grade"] != "Good" and J[s]["n_stand"] > 0 for s in scored), "of", sum(J[s]["n_stand"] > 0 for s in scored))
print("\ncross-check page", dict(cross))

print("\nsame client, same day, EC and EO")
by = collections.defaultdict(dict)
for s in scored:
    by[(meta[s][0], meta[s][1][:10])][J[s]["cond"]] = s
pairs = [(v["EC"], v["EO"]) for v in by.values() if "EC" in v and "EO" in v]
print(" pairs", len(pairs), "| same zero / nonzero headline", sum((J[a]["n_stand"] > 0) == (J[b]["n_stand"] > 0) for a, b in pairs),
      "| share a rhythm finding", sum(bool(set(J[a]["assoc"]) & set(J[b]["assoc"])) for a, b in pairs), "| both have findings", sum(bool(J[a]["assoc"]) and bool(J[b]["assoc"]) for a, b in pairs))

print("\npanel against this report")
x = [(J[s]["n_oob"], J[s]["n_stand"], J[s]["age"], J[s]["cond"]) for s in scored if J[s].get("n_oob") is not None]
print(" panel >= 8 out of range and nothing stands out here", sum(a >= 8 and b == 0 for a, b, *_ in x), "| panel <= 2 and 2+ stand out here", sum(a <= 2 and b >= 2 for a, b, *_ in x), "| n", len(x))
try:
    from scipy.stats import spearmanr
    print(" rho", round(spearmanr([v[0] for v in x], [v[1] for v in x])[0], 2))
except Exception:
    pass

# a spread to read in full
pick = {}
def first(fn, used):
    for s in scored:
        if s not in used and fn(s):
            return s
used = set()
for name, fn in (("adult_EC_clean", lambda s: J[s]["cond"] == "EC" and 18 <= J[s]["age"] < 65 and J[s]["n_stand"] == 0 and J[s]["grade"] == "Good"),
                 ("child_EC_flags", lambda s: J[s]["cond"] == "EC" and J[s]["age"] < 18 and J[s]["n_stand"] >= 2),
                 ("adult_EO_flags", lambda s: J[s]["cond"] == "EO" and J[s]["age"] >= 18 and J[s]["n_stand"] >= 2),
                 ("older_EC_drowsy", lambda s: J[s]["cond"] == "EC" and J[s]["age"] >= 50 and (J[s].get("drowsy") or {}).get("possible"))):
    s = first(fn, used)
    if s:
        used.add(s); pick[name] = s
        d = fitz.open(os.path.join(B, s + ".edfreport.pdf"))
        for k, g in enumerate(d):
            g.get_pixmap(dpi=80).save(os.path.join(IMG, f"read_{name}_{k + 1}.png"))
        print(name, s, "age", J[s]["age"], J[s]["cond"], "stand", J[s]["n_stand"], J[s]["grade"], "pages", len(d))
