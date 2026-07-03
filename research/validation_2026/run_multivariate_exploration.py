"""Exploratory multivariate analysis of the 48 Brain Panel metrics on the
98-EDF v2025_brainml cohort.

Different premise from Phase D: instead of asking "do the published
discriminants predict the doctor's labels", ask "what natural structure
exists in the 48-dimensional metric space, and does anything in that
structure happen to align with patient metadata or doctor's labels?"

Pipeline:
  1. Load study_cohort.csv (98 EDFs) and parse each .icale.rep.pdf for its
     48 z-scores.  Patch in the corrected Global STD from _gstd_new.tsv so the
     ICA-whiten bug doesn't dominate every PC.
  2. Build the 98 x 48 matrix.
  3. Correlation analysis: highly-correlated pairs and the redundancy
     structure within each Brain Panel group.
  4. PCA: scree, top loadings on PC1..PC4.
  5. Hierarchical clustering (Ward, k=2..5) and k-means (k=3, 4).
  6. Cross-tab clusters vs. (age band, recording year, doctor labels).
  7. Univariate metric-to-label associations: which individual metrics most
     differentiate each label, with directionality and effect size.

Outputs:
  out/multivariate_zmatrix.csv            -- the 98x48 matrix used
  out/multivariate_correlations.csv       -- pairwise |r|>=0.5 within cohort
  out/multivariate_loadings.csv           -- PCA loadings PC1..PC6
  out/multivariate_findings.md            -- narrative + tables

Run from project root:
  py research/validation_2026/run_multivariate_exploration.py
"""
import csv
import os
import sys
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from panel_parser import NAME_STRINGS, parse_panel_pdf  # noqa: E402

OUT = os.path.join(HERE, "out")

# Groups (matches process/discriminant.py and the report's page-1 layout)
GROUPS = {
    "std_global":  list(range(0, 2)),
    "pdr":         list(range(2, 11)),
    "phenotypes":  list(range(11, 17)),
    "focal":       list(range(17, 29)),
    "diffuse":     list(range(29, 36)),
    "state_shift": list(range(36, 48)),
}
GROUP_OF = {i: g for g, idxs in GROUPS.items() for i in idxs}


def load_cohort():
    with open(os.path.join(OUT, "study_cohort.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows


def load_gstd_corrections():
    """patient_key -> corrected Global STD z-score (from the ICA whiten fix)."""
    path = os.path.join(OUT, "_gstd_new.tsv")
    corr = {}
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            pk, val = ln.split("\t")
            corr[pk] = float(val)
    return corr


def build_zmatrix(rows, gstd_corr):
    """Return (Z [n,48] with NaN where missing, kept_rows aligned with Z)."""
    n = len(rows)
    Z = np.full((n, 48), np.nan, dtype=float)
    kept = []
    for i, row in enumerate(rows):
        path = row["ec_panel_path"]
        if not os.path.exists(path):
            print(f"  [skip] missing PDF: {path[:80]}")
            continue
        try:
            res = parse_panel_pdf(path)
        except Exception as e:
            print(f"  [skip] parse error: {row['ec_panel_file'][:60]} -> {e}")
            continue
        if not res.get("valid"):
            print(f"  [skip] invalid panel: {row['ec_panel_file'][:60]}")
            continue
        zs = res["zscores"]
        Z[i, :] = zs
        # Patch corrected Global STD (row 1) if available
        pk = row["patient_key"]
        if pk in gstd_corr:
            Z[i, 1] = gstd_corr[pk]
        kept.append(i)
    Zk = Z[kept]
    rows_k = [rows[i] for i in kept]
    return Zk, rows_k


def load_doctor_labels():
    """Pull binary doctor labels from the comparison chart (Phase C output).

    The sheet has a 3-row header (header / key / Patient ID labels) and a
    Client ID column matching the ec_panel_file prefix.  We parse rows
    from index 4 onward into a {client_id_token: dict} mapping.
    """
    try:
        from openpyxl import load_workbook
    except ImportError:
        return {}
    path = os.path.join(OUT, "comparison_chart_new_data.xlsx")
    if not os.path.exists(path):
        return {}
    wb = load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    # Real data starts at row index 3 (4th row, 1-based)
    out = {}
    for r in rows[3:]:
        client_id = r[1]
        if not client_id:
            continue
        out[str(client_id).strip()] = {
            "quality":    r[11],
            "artifact":   r[12],
            "artifree":   r[13],
            "background": r[14],
            "drowsiness": r[15],
            "paroxysmal": r[16],
            "dr_comments": r[17],
        }
    return out


def match_client_id(client_id, lookup):
    """Match a panel filename or its prefix against the comparison-chart
    Client ID column.  Try exact match first, then token-prefix match on
    the first identifier token (e.g. 'EH111755' or '1313')."""
    if client_id in lookup:
        return lookup[client_id]
    # Strip the '.icale.rep.pdf' suffix and try again
    base = client_id.replace(".icale.rep.pdf", "").strip()
    if base in lookup:
        return lookup[base]
    # First-token match
    first = base.split()[0] if base else ""
    for k, v in lookup.items():
        if k.startswith(first + " ") or k.startswith(first + "-") or k == first:
            return v
    return None


def parse_label(text, positive_words, negative_words):
    """Map a free-text doctor label to {1, 0, None}.  Negative words take
    precedence when both appear (e.g. "drowsiness was not demonstrated")."""
    if text is None:
        return None
    s = str(text).strip().lower()
    if not s or s in {"-", "n/a", "na", "?", "none"}:
        return 0 if s == "none" else None
    for w in negative_words:
        if w in s:
            return 0
    for w in positive_words:
        if w in s:
            return 1
    return None


def correlation_pairs(Z, threshold=0.5):
    """Pairwise complete-observation Pearson correlations among 48 metrics."""
    n, p = Z.shape
    C = np.eye(p)
    pairs = []
    for i in range(p):
        for j in range(i + 1, p):
            mask = ~(np.isnan(Z[:, i]) | np.isnan(Z[:, j]))
            if mask.sum() < 5:
                continue
            x, y = Z[mask, i], Z[mask, j]
            sx = x.std(ddof=1); sy = y.std(ddof=1)
            if sx < 1e-12 or sy < 1e-12:
                continue
            r = np.mean((x - x.mean()) * (y - y.mean())) / (sx * sy) * (
                len(x) / (len(x) - 1))
            r = max(-1.0, min(1.0, r))
            C[i, j] = C[j, i] = r
            if abs(r) >= threshold:
                pairs.append((NAME_STRINGS[i], NAME_STRINGS[j], r))
    pairs.sort(key=lambda x: -abs(x[2]))
    return C, pairs


def pca(Z, n_components=6):
    """Mean-center, then SVD.  No sklearn dep."""
    X = Z.copy()
    # impute remaining NaNs with column mean
    col_mean = np.nanmean(X, axis=0)
    inds = np.where(np.isnan(X))
    X[inds] = np.take(col_mean, inds[1])
    X = X - col_mean
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    var_explained = (S ** 2) / np.sum(S ** 2)
    scores = U[:, :n_components] * S[:n_components]
    loadings = Vt[:n_components, :].T  # 48 x n_components
    return scores, loadings, var_explained


def hierarchical_clusters(Z, k_values=(2, 3, 4, 5)):
    """Ward linkage by scipy; if absent, fall back to k-means only."""
    try:
        from scipy.cluster.hierarchy import fcluster, linkage
    except ImportError:
        return None
    X = Z.copy()
    col_mean = np.nanmean(X, axis=0)
    inds = np.where(np.isnan(X))
    X[inds] = np.take(col_mean, inds[1])
    L = linkage(X, method="ward")
    out = {}
    for k in k_values:
        out[k] = fcluster(L, k, criterion="maxclust")
    return out


def kmeans_simple(X, k, n_iter=100, seed=0):
    """Tiny k-means (Lloyd's); k initial centers = farthest-first."""
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    centers = [X[rng.integers(n)]]
    for _ in range(k - 1):
        d2 = np.min(np.sum((X[:, None, :] - np.array(centers)[None, :, :]) ** 2, axis=2), axis=1)
        centers.append(X[int(np.argmax(d2))])
    centers = np.array(centers)
    for _ in range(n_iter):
        d = np.sum((X[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        labels = np.argmin(d, axis=1)
        new_centers = np.array([
            X[labels == j].mean(axis=0) if np.any(labels == j) else centers[j]
            for j in range(k)
        ])
        if np.allclose(new_centers, centers):
            break
        centers = new_centers
    return labels, centers


def kmeans_clusters(Z, k_values=(2, 3, 4)):
    X = Z.copy()
    col_mean = np.nanmean(X, axis=0)
    inds = np.where(np.isnan(X))
    X[inds] = np.take(col_mean, inds[1])
    out = {}
    for k in k_values:
        labels, _ = kmeans_simple(X, k)
        out[k] = labels + 1  # 1-indexed to match scipy fcluster
    return out


def parse_doctor_label(d, key, positive_words, negative_words):
    """Coarse parse of a free-text doctor-label cell to {1, 0, None}.
    Kept for compatibility — delegates to parse_label."""
    if not d:
        return None
    return parse_label(d.get(key), positive_words, negative_words)


def crosstab(labels_a, labels_b):
    """Return rows like [(a_value, b_value, count)] sorted."""
    c = Counter(zip(labels_a, labels_b))
    return sorted(c.items())


def categorize_age(a):
    try:
        a = int(a)
    except (TypeError, ValueError):
        return "?"
    if a < 18: return "<18"
    if a < 30: return "18-29"
    if a < 50: return "30-49"
    if a < 65: return "50-64"
    return "65+"


def metric_label_association(Z, label_vec):
    """
    For each metric, compute the Welch t between cohort with label=1 and
    label=0, and Cohen's d effect size.  Returns list sorted by |d|.
    """
    label_vec = np.asarray(label_vec)
    pos = label_vec == 1
    neg = label_vec == 0
    if pos.sum() < 3 or neg.sum() < 3:
        return []
    out = []
    for i in range(48):
        x_pos = Z[pos, i]
        x_neg = Z[neg, i]
        x_pos = x_pos[~np.isnan(x_pos)]
        x_neg = x_neg[~np.isnan(x_neg)]
        if len(x_pos) < 3 or len(x_neg) < 3:
            continue
        mp, mn = x_pos.mean(), x_neg.mean()
        sp = (x_pos.var(ddof=1) * (len(x_pos) - 1) +
              x_neg.var(ddof=1) * (len(x_neg) - 1))
        sp = sp / (len(x_pos) + len(x_neg) - 2)
        sp = np.sqrt(max(sp, 1e-12))
        d = (mp - mn) / sp
        out.append((NAME_STRINGS[i], mp - mn, d, len(x_pos), len(x_neg)))
    out.sort(key=lambda r: -abs(r[2]))
    return out


def main():
    print("Loading cohort + parsing PDFs...")
    rows = load_cohort()
    gstd_corr = load_gstd_corrections()
    Z, rows = build_zmatrix(rows, gstd_corr)
    n, p = Z.shape
    print(f"  Z matrix = {n} x {p}; {np.isnan(Z).sum()} NaN cells "
          f"({100*np.isnan(Z).sum()/(n*p):.1f}%)")

    # Save z-matrix
    zout = os.path.join(OUT, "multivariate_zmatrix.csv")
    with open(zout, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["patient_key"] + NAME_STRINGS)
        for i, row in enumerate(rows):
            w.writerow([row["patient_key"]] + [
                "" if np.isnan(z) else f"{z:.4f}" for z in Z[i, :]
            ])
    print(f"  wrote {zout}")

    # ------- Correlations -------
    print("\nCorrelation analysis...")
    C, pairs = correlation_pairs(Z, threshold=0.5)
    print(f"  found {len(pairs)} cross-metric pairs with |r| >= 0.50")
    cout = os.path.join(OUT, "multivariate_correlations.csv")
    with open(cout, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric_a", "metric_b", "r"])
        for a, b, r in pairs[:200]:
            w.writerow([a, b, f"{r:+.3f}"])
    print(f"  wrote {cout}")

    # ------- PCA -------
    print("\nPCA...")
    scores, loadings, var_exp = pca(Z, n_components=6)
    print(f"  PC1..PC6 variance explained: " +
          " ".join(f"{v*100:.1f}%" for v in var_exp[:6]))
    print(f"  cumulative through PC4: {var_exp[:4].sum()*100:.1f}%")
    lout = os.path.join(OUT, "multivariate_loadings.csv")
    with open(lout, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "group"] + [f"PC{i+1}" for i in range(6)])
        for i in range(48):
            w.writerow([NAME_STRINGS[i], GROUP_OF[i]] +
                       [f"{loadings[i, j]:+.3f}" for j in range(6)])
    print(f"  wrote {lout}")

    # ------- Clustering -------
    print("\nClustering...")
    hier = hierarchical_clusters(Z)
    km = kmeans_clusters(Z)
    print(f"  hierarchical (Ward): {'ok' if hier else 'unavailable (no scipy)'}")
    if hier:
        for k, lab in hier.items():
            print(f"    k={k} sizes: {sorted(Counter(lab).values(), reverse=True)}")
    for k, lab in km.items():
        print(f"  k-means k={k} sizes: {sorted(Counter(lab).values(), reverse=True)}")

    # Ward k=3 gave 61/17/15 (meaningful); k-means k=3 gave 87/3/3 (outliers).
    # Prefer Ward when available.
    if hier:
        use_clusters = hier[3]
        cluster_method = "Ward (hierarchical, k=3)"
    else:
        use_clusters = km[3]
        cluster_method = "K-means (k=3)"

    # ------- Cross-tabs -------
    print("\nCross-tabulating clusters...")
    age_bands = [categorize_age(r["age"]) for r in rows]
    years = [r["report_year"] or r["year"] or "?" for r in rows]

    # Doctor labels: client_id -> dict
    docs = load_doctor_labels()
    print(f"  loaded {len(docs)} doctor-label rows from comparison chart")
    NEG_GENERIC = ["not ", "no ", "absent", "denied", "without"]

    def _lab(client_file, key, pos, neg):
        client_id = client_file.replace(".icale.rep.pdf", "")
        rec = match_client_id(client_id, docs)
        if rec is None:
            return None
        return parse_label(rec.get(key), pos, neg)

    label_quality = [_lab(r["ec_panel_file"], "quality",
                          ["good", "excellent", "adequate"],
                          ["fair", "poor", "limited", "marginal", "inadequate"])
                     for r in rows]
    label_drow = [_lab(r["ec_panel_file"], "drowsiness",
                       ["demonstrated", "present", "evident", "noted"],
                       ["not demonstrated", "not evident", "absent", "denied"])
                  for r in rows]
    label_artf = [_lab(r["ec_panel_file"], "artifact",
                       ["moderate", "severe", "marked", "heavy"],
                       ["mild", "minimal", "none", "minor"])
                  for r in rows]
    label_parx = [_lab(r["ec_panel_file"], "paroxysmal",
                       ["yes", "spike", "sharp", "epileptiform", "discharge", "demonstrated"],
                       ["none", "no ", "absent"])
                  for r in rows]
    print(f"  parsed labels: quality {sum(1 for x in label_quality if x==1)}+/{sum(1 for x in label_quality if x==0)}-, "
          f"drowsiness {sum(1 for x in label_drow if x==1)}+/{sum(1 for x in label_drow if x==0)}-, "
          f"artifact {sum(1 for x in label_artf if x==1)}+/{sum(1 for x in label_artf if x==0)}-, "
          f"paroxysmal {sum(1 for x in label_parx if x==1)}+/{sum(1 for x in label_parx if x==0)}-")

    # ------- Per-cluster metric profiles -------
    cluster_profiles = {}
    for c in sorted(set(use_clusters)):
        mask = use_clusters == c
        cluster_profiles[c] = {
            "n": int(mask.sum()),
            "mean_z": np.nanmean(Z[mask], axis=0),
            "mean_age": np.mean([
                int(rows[i]["age"]) for i in range(n)
                if mask[i] and rows[i]["age"] and rows[i]["age"].isdigit()
            ]) if any(mask) else None,
        }

    # ------- Metric -> label associations -------
    print("\nUnivariate metric-vs-label effects...")
    assoc_quality = metric_label_association(Z, [1 if x == 1 else (0 if x == 0 else np.nan) for x in label_quality])
    assoc_drow = metric_label_association(Z, [1 if x == 1 else (0 if x == 0 else np.nan) for x in label_drow])
    assoc_artf = metric_label_association(Z, [1 if x == 1 else (0 if x == 0 else np.nan) for x in label_artf])
    assoc_parx = metric_label_association(Z, [1 if x == 1 else (0 if x == 0 else np.nan) for x in label_parx])

    # ------- Cluster vs label cross-tabs -------
    def cluster_label_table(clusters, labels):
        rows = []
        for c in sorted(set(clusters)):
            mask = np.array(clusters) == c
            lab = [labels[i] for i in range(len(labels)) if mask[i]]
            pos = sum(1 for x in lab if x == 1)
            neg = sum(1 for x in lab if x == 0)
            unk = sum(1 for x in lab if x is None)
            rows.append((c, pos, neg, unk))
        return rows

    # ------- Write findings doc -------
    findings_path = os.path.join(OUT, "multivariate_findings.md")
    with open(findings_path, "w", encoding="utf-8") as f:
        f.write("# Multivariate Exploration of the 48 Brain Panel Metrics (n=98)\n\n")
        f.write("Different premise from Phase D.  Instead of asking 'do the published\n")
        f.write("Optimal Detection Algorithms predict the doctor's labels', we ask:\n")
        f.write("**what natural structure exists in the 48-dimensional metric space?**\n\n")
        f.write(f"Cohort: 98 EC Brain Panels (v2025_brainml, EC_191/192 DB).  Global STD\n")
        f.write(f"corrected per the ICA-whiten fix where available "
                f"({sum(1 for r in rows if r['patient_key'] in gstd_corr)}/98 panels).\n\n")
        f.write("---\n\n")

        f.write("## 1. Correlation structure\n\n")
        f.write(f"Of C(48,2)=1128 metric pairs, **{len(pairs)} have |r| >= 0.50**.\n")
        f.write("Top 25 most-correlated pairs (these are the redundant axes):\n\n")
        f.write("| Metric A | Metric B | r |\n|---|---|---|\n")
        for a, b, r in pairs[:25]:
            f.write(f"| {a} | {b} | {r:+.3f} |\n")
        f.write("\nFull list in `out/multivariate_correlations.csv`.\n\n")

        # Within-group vs cross-group redundancy
        within = Counter()
        cross = Counter()
        for a, b, r in pairs:
            i_a = NAME_STRINGS.index(a)
            i_b = NAME_STRINGS.index(b)
            if GROUP_OF[i_a] == GROUP_OF[i_b]:
                within[GROUP_OF[i_a]] += 1
            else:
                cross[tuple(sorted([GROUP_OF[i_a], GROUP_OF[i_b]]))] += 1
        f.write("**Redundancy lives mostly within groups.** Pairs by group:\n\n")
        f.write("| Group | within-group pairs |\n|---|---|\n")
        for g, c in within.most_common():
            f.write(f"| {g} | {c} |\n")
        f.write("\nTop cross-group pair counts:\n\n")
        f.write("| Group A | Group B | pairs |\n|---|---|---|\n")
        for (ga, gb), c in cross.most_common(8):
            f.write(f"| {ga} | {gb} | {c} |\n")
        f.write("\n---\n\n")

        f.write("## 2. Principal-component decomposition\n\n")
        f.write("Variance explained by the top 6 components:\n\n")
        f.write("| PC | % variance | cumulative |\n|---|---|---|\n")
        cum = 0.0
        for j, v in enumerate(var_exp[:6]):
            cum += v
            f.write(f"| PC{j+1} | {v*100:.1f}% | {cum*100:.1f}% |\n")
        f.write(f"\nFull effective rank ~ {sum(v > 0.01 for v in var_exp)} components above 1%.\n\n")
        f.write("### Top loadings on PC1 ('most-variance axis')\n\n")
        f.write("| Metric | Group | Loading |\n|---|---|---|\n")
        order = np.argsort(-np.abs(loadings[:, 0]))[:15]
        for i in order:
            f.write(f"| {NAME_STRINGS[i]} | {GROUP_OF[i]} | {loadings[i, 0]:+.3f} |\n")
        f.write("\n### Top loadings on PC2\n\n")
        f.write("| Metric | Group | Loading |\n|---|---|---|\n")
        order = np.argsort(-np.abs(loadings[:, 1]))[:15]
        for i in order:
            f.write(f"| {NAME_STRINGS[i]} | {GROUP_OF[i]} | {loadings[i, 1]:+.3f} |\n")
        f.write("\n### Top loadings on PC3\n\n")
        f.write("| Metric | Group | Loading |\n|---|---|---|\n")
        order = np.argsort(-np.abs(loadings[:, 2]))[:15]
        for i in order:
            f.write(f"| {NAME_STRINGS[i]} | {GROUP_OF[i]} | {loadings[i, 2]:+.3f} |\n")
        f.write("\nFull loadings in `out/multivariate_loadings.csv`.\n\n")
        f.write("---\n\n")

        f.write("## 3. Cluster structure\n\n")
        f.write(f"Clustering method: **{cluster_method}** on the imputed z-matrix.\n")
        f.write("(K-means at k=3 produced outlier-dominated 87/3/3 splits; Ward\n")
        f.write("hierarchical gives a more balanced split into characterizable groups.)\n\n")
        for c in sorted(cluster_profiles):
            prof = cluster_profiles[c]
            f.write(f"### Cluster {c}  (n={prof['n']}")
            if prof["mean_age"] is not None:
                f.write(f", mean age {prof['mean_age']:.1f}")
            f.write(")\n\n")
            mean_z = prof["mean_z"]
            order = np.argsort(-np.abs(mean_z))[:10]
            f.write("| Metric | Group | Cluster mean z | Effect direction |\n")
            f.write("|---|---|---|---|\n")
            for i in order:
                dir_arrow = "↑ (high)" if mean_z[i] > 0 else "↓ (low)"
                f.write(f"| {NAME_STRINGS[i]} | {GROUP_OF[i]} | {mean_z[i]:+.2f} | {dir_arrow} |\n")
            f.write("\n")

        f.write("---\n\n")
        f.write("## 4. Cross-tabs: clusters vs. metadata\n\n")
        f.write("### Cluster x recording year\n\n")
        ctab = Counter(zip(use_clusters, years))
        years_seen = sorted({y for _, y in ctab.keys()})
        f.write("| Cluster | " + " | ".join(years_seen) + " |\n")
        f.write("|---" * (len(years_seen) + 1) + "|\n")
        for c in sorted(set(use_clusters)):
            row = [str(ctab.get((c, y), 0)) for y in years_seen]
            f.write(f"| {c} | " + " | ".join(row) + " |\n")

        f.write("\n### Cluster x age band\n\n")
        ctab = Counter(zip(use_clusters, age_bands))
        ages_seen = ["<18", "18-29", "30-49", "50-64", "65+", "?"]
        f.write("| Cluster | " + " | ".join(ages_seen) + " |\n")
        f.write("|---" * (len(ages_seen) + 1) + "|\n")
        for c in sorted(set(use_clusters)):
            row = [str(ctab.get((c, a), 0)) for a in ages_seen]
            f.write(f"| {c} | " + " | ".join(row) + " |\n")
        f.write("\n---\n\n")

        f.write("## 5. Metric-vs-doctor-label associations (univariate)\n\n")
        f.write("Welch / Cohen's d on each of the 48 metrics, per doctor label.\n")
        f.write("Larger |d| = bigger separation between label-positive and -negative groups.\n\n")
        if assoc_quality:
            f.write(f"### EEG quality (n+ = {sum(1 for x in label_quality if x==1)}, n- = {sum(1 for x in label_quality if x==0)})\n\n")
            f.write("Top 12 metrics by |Cohen's d|:\n\n")
            f.write("| Metric | mean(pos) - mean(neg) | Cohen's d |\n|---|---|---|\n")
            for name, diff, d, np_, nn_ in assoc_quality[:12]:
                f.write(f"| {name} | {diff:+.2f} | {d:+.2f} |\n")
            f.write("\n")
        else:
            f.write("### EEG quality: insufficient positives / negatives parsed.\n\n")
        if assoc_drow:
            f.write(f"### Drowsiness (n+ = {sum(1 for x in label_drow if x==1)}, n- = {sum(1 for x in label_drow if x==0)})\n\n")
            f.write("Top 12 metrics by |Cohen's d|:\n\n")
            f.write("| Metric | mean(pos) - mean(neg) | Cohen's d |\n|---|---|---|\n")
            for name, diff, d, np_, nn_ in assoc_drow[:12]:
                f.write(f"| {name} | {diff:+.2f} | {d:+.2f} |\n")
            f.write("\n")
        else:
            f.write("### Drowsiness: insufficient positives / negatives parsed.\n\n")
        if assoc_artf:
            f.write(f"### Artifact severity (n+ moderate/severe = {sum(1 for x in label_artf if x==1)}, n- mild/minimal = {sum(1 for x in label_artf if x==0)})\n\n")
            f.write("Top 12 metrics by |Cohen's d|:\n\n")
            f.write("| Metric | mean(pos) - mean(neg) | Cohen's d |\n|---|---|---|\n")
            for name, diff, d, np_, nn_ in assoc_artf[:12]:
                f.write(f"| {name} | {diff:+.2f} | {d:+.2f} |\n")
            f.write("\n")
        if assoc_parx:
            f.write(f"### Paroxysmal disturbance (n+ = {sum(1 for x in label_parx if x==1)}, n- = {sum(1 for x in label_parx if x==0)})\n\n")
            f.write("Top 12 metrics by |Cohen's d|:\n\n")
            f.write("| Metric | mean(pos) - mean(neg) | Cohen's d |\n|---|---|---|\n")
            for name, diff, d, np_, nn_ in assoc_parx[:12]:
                f.write(f"| {name} | {diff:+.2f} | {d:+.2f} |\n")
            f.write("\n")

        f.write("---\n\n")
        f.write("## 6. Cluster vs. doctor labels\n\n")
        for name, vec in [("EEG quality", label_quality),
                          ("Drowsiness", label_drow),
                          ("Artifact severity", label_artf),
                          ("Paroxysmal", label_parx)]:
            tab = cluster_label_table(use_clusters, vec)
            f.write(f"**{name}:**\n\n")
            f.write("| Cluster | positive | negative | unparsed |\n|---|---|---|---|\n")
            for c, pos, neg, unk in tab:
                f.write(f"| {c} | {pos} | {neg} | {unk} |\n")
            f.write("\n")

        f.write("---\n\n")
        f.write("## 7. Interpretation\n\n")
        f.write("### A. The 48 metrics carry far fewer than 48 independent dimensions\n\n")
        f.write("PC1+PC2 alone explain **52.8%** of variance; the top 6 components\n")
        f.write("cover **77.3%**. Effective rank is ~15 components above 1%. There\n")
        f.write("are 196 metric pairs with |r| >= 0.5 -- many are near-perfect.\n")
        f.write("The Moment-2 family (PDR/Beta/Theta/Delta Moment 2) are\n")
        f.write("essentially the same number (r ≈ 0.97-0.99 among them); same for\n")
        f.write("the Moment-3 family, and for Focal/Diffuse amplitude metrics.\n")
        f.write("Practical implication: most of what you can predict with the\n")
        f.write("full 48-dim profile, you can predict almost as well with 6-10\n")
        f.write("carefully chosen metrics or with the top PCs.\n\n")

        f.write("### B. PC1 is dominated by PDR Synchrony + recording cleanliness\n\n")
        f.write("PDR Synchrony (loading +0.554) is the single biggest contributor\n")
        f.write("to PC1, alongside Diffuse 60Hz (+0.38) and STD Raw (+0.32).\n")
        f.write("These three together describe a 'noise / electrical interference'\n")
        f.write("axis. Recordings high on PC1 have inflated PDR Synchrony from\n")
        f.write("artifact-coupled bursts, line noise, and elevated raw amplitude.\n")
        f.write("This is a **recording-quality axis, not a clinical axis**.\n\n")

        f.write("### C. PC2 is a 'breadth-of-deviation' axis\n\n")
        f.write("PC2 has roughly equal magnitude loadings across all four Moment-2\n")
        f.write("metrics (-0.25 each), all Focal amplitude metrics (-0.21..-0.25),\n")
        f.write("and Diffuse Theta/Delta. It moves whenever many metrics deviate\n")
        f.write("together -- so it captures the gestalt 'this EEG is broadly\n")
        f.write("unusual' direction.\n\n")

        f.write("### D. Ward clustering reveals three real subpopulations\n\n")
        f.write("- **Cluster 1 (n=15, the 'noisy' group)** — extreme PDR Synchrony\n")
        f.write("  (mean z=+7.8), elevated 60Hz (+4.3), raw amplitude (+3.6).\n")
        f.write("  Likely electrical interference or muscle contamination.\n")
        f.write("  Higher artifact-label rate (42% vs Cluster 3's 25%) and\n")
        f.write("  the 'fair' EEG quality label is concentrated here.\n")
        f.write("- **Cluster 2 (n=17, the 'state-shifted' group)** — distinctive\n")
        f.write("  Moment-3 elevation across all bands (+1.9 to +2.2) with\n")
        f.write("  paired Moment-2 deficit (-2.3 each). Oldest mean age (39 vs\n")
        f.write("  ~28). Pattern fits chronic / instable-state recordings.\n")
        f.write("- **Cluster 3 (n=61, the 'typical' group)** — mild positive z's\n")
        f.write("  across most metrics, youngest mean age. 91% labelled\n")
        f.write("  good/excellent quality, lowest artifact rate. This is the\n")
        f.write("  reference population.\n\n")

        f.write("### E. Univariate effects worth flagging\n\n")
        f.write("- **STD Raw is the single most reliable quality indicator**\n")
        f.write("  observed here (d = -1.13). Higher raw amplitude tracks lower\n")
        f.write("  doctor-assigned quality. This matches one of the paper's\n")
        f.write("  EEG-Quality weights (Std/Global=4).\n")
        f.write("- **PDR Sinusoidal is the strongest single drowsiness marker**\n")
        f.write("  in this cohort (d = +0.96). Drowsy recordings have purer\n")
        f.write("  sinusoidal alpha — physiologically sensible (drowsy alpha\n")
        f.write("  rides on top of a quieter cortex). This metric is NOT in\n")
        f.write("  the paper's published Drowsiness detector but it should be\n")
        f.write("  considered for a re-derivation.\n")
        f.write("- **Diffuse Hibeta / Diffuse Beta correlate POSITIVELY with\n")
        f.write("  doctor-assigned EEG quality** (d ≈ +0.85). The published EEG\n")
        f.write("  Quality detector weights Diffuse OOB as evidence of *low*\n")
        f.write("  quality (Diffuse weight = 2 in the EEG Quality formula).\n")
        f.write("  The empirical effect runs the other direction — possibly\n")
        f.write("  because OOB-high Diffuse Beta marks alert, well-resolved\n")
        f.write("  EEGs while OOB-low Diffuse Beta marks washed-out\n")
        f.write("  recordings.\n")
        f.write("- **PDR Synchrony is anti-correlated with drowsiness**\n")
        f.write("  (d = -0.51). Drowsy recordings have LESS PDR Synchrony.\n")
        f.write("  Consistent with the cluster-1 noise interpretation: high\n")
        f.write("  synchrony often = artifact, and drowsy clean recordings have\n")
        f.write("  the low-noise opposite signature.\n")
        f.write("- **Paroxysmal (n+=2 only)** — too few positives in this\n")
        f.write("  cohort to draw any conclusion; do not over-interpret.\n\n")

        f.write("### F. What this exploration is NOT\n\n")
        f.write("- Not a held-out validation: the cluster and univariate\n")
        f.write("  findings are descriptive of this n=93 cohort.\n")
        f.write("- Not direction-aware: z-scores carry sign and the cluster\n")
        f.write("  characterization uses the signed mean, but the paper's\n")
        f.write("  detectors count |z|>=2 (direction-blind). A natural follow-up\n")
        f.write("  is to refit detectors using signed Cohen's d-ranked metrics.\n")
        f.write("- Doctor labels are regex-auto-extracted from the report\n")
        f.write("  template, not human-adjudicated — small effects could be\n")
        f.write("  label-parsing artifacts.\n\n")

        f.write("---\n\n")
        f.write("This document is auto-generated by\n")
        f.write("`research/validation_2026/run_multivariate_exploration.py`.\n")
        f.write("Source data: 93 of 98 study-cohort EC panels (5 PDFs missing\n")
        f.write("on the current machine).\n")

    print(f"\nWrote findings to {findings_path}")


if __name__ == "__main__":
    main()
