"""Can drowsiness be detected from the recording? Compares the doctor's comment
with feature blocks under one honest test: repeated 5-fold cross-validation grouped
by client, so no client is on both sides, with age always available to the model.

The comment is written per REPORT and is the same for the eyes-closed and eyes-open
files of a session (346 of 346 pairs), so a session is the unit:
  EC / EO   that file's features only, against the session's comment
  session   both files' features together, one row per session

Blocks: age alone; panel z (all 48); panel moments (rows 36-47); whole-recording
EDF power; vigilance (tools/vigilance_features.py: time-resolved); and combinations.
Models: ridge logistic on rank-normal features; gradient boosting.

Writes research/validation_2026/out/DROWSINESS_MODEL.md.  py tools/drowsiness_model.py
"""
import json
import os
import sqlite3
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from label_join import auc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_MD = os.path.join(ROOT, "research", "validation_2026", "out", "DROWSINESS_MODEL.md")
STORE = r"C:\BrainPanel\source_db"
REPEATS = 5
MOMENT_ROWS = list(range(36, 48))


def load(con):
    S = {r[0]: dict(client=r[1] or r[0], cond=r[2], age=r[3], when=r[4]) for r in con.execute(
        "SELECT id, client, cond, age, rec_start FROM studies WHERE status='ok' AND cond IN ('EC','EO') "
        "AND age BETWEEN 3 AND 90")}
    y, rep = {}, {}
    for s, v, r in con.execute("SELECT study_id, value, report FROM labels WHERE outcome='drowsiness' AND conf='high'"):
        if s in S:
            y[s], rep[s] = v, r
    blocks = {"panel": {}, "moments": {}, "edf": {}, "vigil": {}}
    for s, row, z in con.execute("SELECT study_id, row, z FROM panel"):
        if s in S and z is not None:
            blocks["panel"].setdefault(s, {})[f"p{row}"] = z
            if row in MOMENT_ROWS:
                blocks["moments"].setdefault(s, {})[f"p{row}"] = z
    cols = [r[1] for r in con.execute("PRAGMA table_info(edf_features)")][1:]
    for r in con.execute("SELECT * FROM edf_features"):
        if r[0] in S:
            blocks["edf"][r[0]] = {c: v for c, v in zip(cols, r[1:]) if v is not None}
    for s, f in con.execute("SELECT study_id, feat FROM vigil_features WHERE feat IS NOT NULL"):
        if s in S:
            blocks["vigil"][s] = {k: v for k, v in json.loads(f).items()
                                  if v is not None and k not in ("dur_s", "n_epochs")}
    return S, y, rep, blocks


def matrix(units, get, names):
    X = np.full((len(units), len(names)), np.nan)
    ix = {n: i for i, n in enumerate(names)}
    for r, u in enumerate(units):
        for k, v in get(u).items():
            if k in ix and np.isfinite(v):
                X[r, ix[k]] = v
    return X


def cv_auc(X, y, groups, kind):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import QuantileTransformer
    out = []
    oof_all = np.zeros(len(y))
    for rep in range(REPEATS):
        oof = np.zeros(len(y))
        for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=rep).split(X, y, groups):
            if kind == "ridge":
                m = make_pipeline(SimpleImputer(strategy="median"),
                                  QuantileTransformer(n_quantiles=min(100, len(tr)), output_distribution="normal"),
                                  LogisticRegression(C=0.05, max_iter=3000))
            else:
                m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.03, max_iter=200,
                                                   min_samples_leaf=15, random_state=rep)
            m.fit(X[tr], y[tr])
            oof[te] = m.predict_proba(X[te])[:, 1]
        out.append(auc(oof, y))
        oof_all += oof / REPEATS
    return float(np.mean(out)), float(np.std(out)), oof_all


def ci(oof, y, groups, rng, n=500):
    """Bootstrap by client on the averaged out-of-fold predictions."""
    ug = np.unique(groups)
    idx = {g: np.where(groups == g)[0] for g in ug}
    a = []
    for _ in range(n):
        k = np.concatenate([idx[g] for g in rng.choice(ug, len(ug))])
        if 0 < y[k].sum() < len(k):
            a.append(auc(oof[k], y[k]))
    return np.percentile(a, [2.5, 97.5])


_LOADED = {}


def _ridge(n_train):
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import QuantileTransformer
    return make_pipeline(SimpleImputer(strategy="median"),
                         QuantileTransformer(n_quantiles=min(100, n_train), output_distribution="normal"),
                         LogisticRegression(C=0.05, max_iter=3000))


def drowsy_note(edf_path, age, cond, cp, store=STORE, client=None):
    """Soft cover-page note, eyes-closed only (eyes-open reached only 0.64 and fails in
    children and older adults). Ridge on EDF power + time-resolved features, fitted without
    this client. Returns dict(possible, rate) or None. possible = the score falls in the top
    third of out-of-client reference scores; rate = how often the reader noted drowsiness there."""
    if cond != "EC" or age is None or not 3 <= age <= 90:
        return None
    import edf_power
    from sklearn.model_selection import StratifiedGroupKFold
    from vigilance_features import features
    if store not in _LOADED:
        con = sqlite3.connect(os.path.join(store, "sources.db"))
        _LOADED[store] = load(con)
        con.close()
    S, y, _rep, B = _LOADED[store]
    units = [s for s in y if S[s]["cond"] == "EC" and S[s]["client"] != client]
    if len(units) < 100:
        return None
    names = ["age"] + sorted({k for s in S for b in ("edf", "vigil") for k in B[b].get(s, {})})
    X = matrix(units, lambda s: {"age": S[s]["age"], **B["edf"].get(s, {}), **B["vigil"].get(s, {})}, names)
    yy = np.array([y[s] for s in units])
    g = np.array([S[s]["client"] for s in units])
    oof = np.zeros(len(yy))
    for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=0).split(X, yy, g):
        oof[te] = _ridge(len(tr)).fit(X[tr], yy[tr]).predict_proba(X[te])[:, 1]
    cut = np.percentile(oof, 200 / 3)
    vig = features(edf_path)
    if vig is None:
        return None
    me = {"age": age, **edf_power.summary(cp), **vig}
    x = matrix([0], lambda _u: {k: v for k, v in me.items() if v is not None and np.isscalar(v)}, names)
    score = float(_ridge(len(yy)).fit(X, yy).predict_proba(x)[0, 1])
    return dict(possible=score > cut, rate=float(yy[oof > cut].mean()), score=score, cut=float(cut))


def grade_of(text):
    """Reader's wording -> none / brief / plain / described. Text from drowsy_text.json in
    the store (outside the repo)."""
    t = (text or "").lower()
    if "not demonstrated" in t or "not clearly" in t or "no drowsiness" in t:
        return "none"
    if "brief" in t or "possibl" in t or "may " in t:
        return "brief"
    if any(w in t for w in ("diminution", "throughout", "stage", "frequent", "spindle", "slowing")):
        return "described"
    return "plain"


def detail(S, y, rep, B):
    """Eyes-closed, EDF + vigilance: does the score follow how the reader worded it, how well
    does a small panel of features do, and which recordings disagree most with the comment?"""
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import QuantileTransformer
    text = json.load(open(os.path.join(STORE, "drowsy_text.json")))
    L = []
    for cond in ("EC", "EO"):
        units = [s for s in y if S[s]["cond"] == cond]
        yy = np.array([y[s] for s in units])
        g = np.array([S[s]["client"] for s in units])
        age = np.array([S[s]["age"] for s in units], float)
        names = ["age"] + sorted({k for s in S for b in ("edf", "vigil") for k in B[b].get(s, {})})
        X = matrix(units, lambda s: {"age": S[s]["age"], **B["edf"].get(s, {}), **B["vigil"].get(s, {})}, names)
        _, _, oof = cv_auc(X, yy, g, "ridge")
        gr = np.array([grade_of(text.get(rep[s])) for s in units])
        L.append(f"## Eyes {'closed' if cond == 'EC' else 'open'}: score against the reader's wording\n")
        L.append("| reader's wording | studies | median score | in top third of scores |")
        L.append("|---|---:|---:|---:|")
        cut = np.percentile(oof, [100 / 3, 200 / 3])
        for k in ("none", "brief", "plain", "described"):
            m = gr == k
            if m.sum():
                L.append(f"| {k} | {m.sum()} | {np.median(oof[m]):.2f} | {100 * (oof[m] > cut[1]).mean():.0f}% |")
        L.append("")
        L.append("| score third | studies | reader said drowsy |")
        L.append("|---|---:|---:|")
        for nm, m in (("lowest", oof <= cut[0]), ("middle", (oof > cut[0]) & (oof <= cut[1])), ("highest", oof > cut[1])):
            L.append(f"| {nm} | {m.sum()} | {100 * yy[m].mean():.0f}% |")
        L.append("")
        pos = gr != "none"
        for nm, m in (("brief only vs none", (gr == "brief") | (gr == "none")),
                      ("described vs none", (gr == "described") | (gr == "none"))):
            if yy[m].sum() >= 5:
                L.append(f"- {nm}: AUC {auc(oof[m], yy[m]):.2f} ({int(pos[m].sum())} positive)")
        for lo, hi in ((3, 12), (13, 39), (40, 90)):
            m = (age >= lo) & (age <= hi)
            L.append(f"- age {lo}-{hi}: AUC {auc(oof[m], yy[m]):.2f} (n={m.sum()}, {int(yy[m].sum())} positive)")
        # small panel: chosen inside each training fold, so the choice cannot see its test set
        small = {k: [] for k in (4, 6, 10)}
        picked = {}
        for k_ in small:
            for r_ in range(REPEATS):
                o = np.zeros(len(yy))
                for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=r_).split(X, yy, g):
                    sc = []
                    for j in range(1, X.shape[1]):
                        ok = np.isfinite(X[tr, j])
                        sc.append(abs(auc(X[tr, j][ok], yy[tr][ok]) - 0.5) if ok.sum() > 50 else 0)
                    top = [0] + list(np.argsort(sc)[::-1][:k_] + 1)
                    if k_ == 6:
                        for j in top[1:]:
                            picked[names[j]] = picked.get(names[j], 0) + 1
                    m = make_pipeline(SimpleImputer(strategy="median"),
                                      QuantileTransformer(n_quantiles=min(100, len(tr)), output_distribution="normal"),
                                      LogisticRegression(C=0.2, max_iter=2000))
                    m.fit(X[tr][:, top], yy[tr])
                    o[te] = m.predict_proba(X[te][:, top])[:, 1]
                small[k_].append(auc(o, yy))
        L.append("- small panels, chosen inside each fold: " +
                 ", ".join(f"{k} features {np.mean(v):.3f}" for k, v in small.items()))
        L.append("- most often chosen (of 25 folds): " + ", ".join(
            f"{k} {v}" for k, v in sorted(picked.items(), key=lambda t: -t[1])[:10]))
        L.append("")
    return L


def main():
    con = sqlite3.connect(os.path.join(STORE, "sources.db"))
    S, y, rep, B = load(con)
    con.close()
    rng = np.random.default_rng(0)
    if "--detail" in sys.argv:
        L = detail(S, y, rep, B)
        s = open(OUT_MD, encoding="utf-8").read().split("## Eyes closed: score")[0]
        open(OUT_MD, "w", encoding="utf-8").write(s + "\n".join(L) + "\n")
        print("\n".join(L))
        return
    L = ["# Detecting drowsiness\n",
         "Generated by `tools/drowsiness_model.py`. Target: the doctor's drowsiness comment (high-confidence "
         "labels). Repeated 5-fold CV grouped by client; every model also sees age. 95% CI: bootstrap by client. "
         "AUC 0.5 = chance.\n"]
    sets = {}
    for c in ("EC", "EO"):
        sets[c] = [s for s in y if S[s]["cond"] == c]
    # sessions: one report, both files
    sess = {}
    for s in y:
        sess.setdefault(rep[s], {})[S[s]["cond"]] = s
    pairs = [d for d in sess.values() if "EC" in d and "EO" in d]

    combos = [("age only", []), ("panel moments (12)", ["moments"]), ("panel, all 48", ["panel"]),
              ("EDF whole-recording power", ["edf"]), ("vigilance (time-resolved)", ["vigil"]),
              ("panel + EDF", ["panel", "edf"]), ("panel + vigilance", ["panel", "vigil"]),
              ("EDF + vigilance", ["edf", "vigil"]), ("all", ["panel", "edf", "vigil"])]
    L.append("| unit | features | ridge | boosted | best 95% CI |")
    L.append("|---|---|---:|---:|---:|")
    keep = {}
    for unit in ("EC", "EO", "session"):
        if unit == "session":
            units = pairs
            y_ = np.array([y[d["EC"]] for d in units])
            g = np.array([S[d["EC"]]["client"] for d in units])

            def getter(bl):
                def f(d):
                    o = {"age": S[d["EC"]]["age"]}
                    for b in bl:
                        for c in ("EC", "EO"):
                            o.update({f"{c}.{k}": v for k, v in B[b].get(d[c], {}).items()})
                    return o
                return f
            def names(bl):
                out = ["age"]
                for b in bl:
                    ks = sorted({k for s in S for k in B[b].get(s, {})})
                    out += [f"{c}.{k}" for c in ("EC", "EO") for k in ks]
                return out
        else:
            units = sets[unit]
            y_ = np.array([y[s] for s in units])
            g = np.array([S[s]["client"] for s in units])

            def getter(bl):
                def f(s):
                    o = {"age": S[s]["age"]}
                    for b in bl:
                        o.update(B[b].get(s, {}))
                    return o
                return f
            def names(bl):
                out = ["age"]
                for b in bl:
                    out += sorted({k for s in S for k in B[b].get(s, {})})
                return out
        print(unit, len(units), "units", int(y_.sum()), "positive", flush=True)
        for title, bl in combos:
            X = matrix(units, getter(bl), names(bl))
            r, rs, ro = cv_auc(X, y_, g, "ridge")
            h, hs, ho = cv_auc(X, y_, g, "boost")
            lo, hi = ci(ro if r >= h else ho, y_, g, rng)
            L.append(f"| {unit} (n={len(units)}, {int(y_.sum())} pos) | {title} | {r:.3f} | {h:.3f} | {lo:.2f}-{hi:.2f} |")
            keep[(unit, title)] = max(r, h)
            print(" ", title, round(r, 3), round(h, 3), flush=True)
    L.append("")

    # single features, age-adjusted, session mean of EC and EO where both exist
    L.append("## Best single vigilance and moment features (AUC; EC, EO)\n")
    L.append("Residual of each feature after a cubic in log(age); > 0.5 = higher in drowsy.\n")
    L.append("| feature | EC | EO |")
    L.append("|---|---:|---:|")
    feats = sorted({k for s in S for k in B["vigil"].get(s, {})} | {f"p{r}" for r in MOMENT_ROWS})
    res = []
    for k in feats:
        row = []
        for c in ("EC", "EO"):
            ss = [s for s in sets[c] if k in {**B["vigil"].get(s, {}), **B["moments"].get(s, {})}]
            v = np.array([{**B["vigil"].get(s, {}), **B["moments"].get(s, {})}[k] for s in ss], float)
            la = np.log(np.array([S[s]["age"] for s in ss], float) / 20)
            D = np.vstack([la ** i for i in range(4)]).T
            yy = np.array([y[s] for s in ss])
            row.append(auc(v - D @ np.linalg.lstsq(D, v, rcond=None)[0], yy))
        res.append((k, row))
    for k, row in sorted(res, key=lambda t: -abs(t[1][0] + t[1][1] - 1))[:20]:
        L.append(f"| {k} | {row[0]:.2f} | {row[1]:.2f} |")
    L.append("")
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("wrote", OUT_MD)


if __name__ == "__main__":
    main()
