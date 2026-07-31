"""
Internal covariance / dimensionality analysis of the Brain Panel.

Answers: how many INDEPENDENT things is the 48-metric Brain Panel really
measuring, and which metrics move together?  Uses only the reference
database (EC_191.out_file.icale.xlsx, 192 files) -- no external labels.

The 56 DB rows map to mymetricsa indices 0..55 (see
files/edftotextbynameplotproc.py:836).  The 48 displayed Brain Panel rows
are indices 8..55 (the first 8 are housekeeping/reconstruction rows).

Outputs:
  out_structure/scree.png
  out_structure/clustered_corr.png
  out_structure/dendrogram.png
  prints a text report of effective dimensionality + clusters.
"""
import os
import numpy as np
import openpyxl
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram, leaves_list
from scipy.spatial.distance import squareform
from scipy.stats import spearmanr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "..", "..", "EC_191.out_file.icale.xlsx")
OUT = os.path.join(HERE, "out_structure")
os.makedirs(OUT, exist_ok=True)

# ---- 48 Brain Panel metric labels (mymetricsa idx 8..55) -------------------
LABELS = [
    "STD Raw", "Global STD",                                              # std_global (0-1)
    "PDR Symm", "PDR Synch", "PDR Reg", "PDR Mag", "PDR Sinus",
    "PDR MaxPost", "PDR FFTWidth", "PDR Amp", "PDR BurstWidth",           # pdr (2-10)
    "Beta MaxFront", "Front AlphaAsym", "XS TempAlpha", "FastAlpha",
    "AlphaPeak", "MidlineBeta",                                           # phenotypes (11-16)
    "FocalDelta", "FocalDeltaAmp", "FocalTheta", "FocalThetaAmp",
    "FocalHiBeta", "FocalHiBetaAmp", "FocalBeta", "FocalBetaAmp",
    "FrontalDelta", "FrontalTheta", "FrontalGamma", "FrontGammaAsym",     # focal (17-28)
    "DiffuseDelta", "DiffuseTheta", "DiffuseHiBeta", "DiffuseBeta",
    "DiffuseGamma", "Diffuse60Hz", "FractalDim",                         # diffuse (29-35)
    "PDRMoment1", "PDRMoment2", "PDRMoment3", "BetaMoment1", "BetaMoment2",
    "BetaMoment3", "ThetaMoment1", "ThetaMoment2", "ThetaMoment3",
    "DeltaMoment1", "DeltaMoment2", "DeltaMoment3",                       # state_shift (36-47)
]
GROUP_OF = (["Std/Global"]*2 + ["PDR"]*9 + ["Phenotype"]*6 +
            ["Focal"]*12 + ["Diffuse"]*7 + ["StateShift"]*12)
assert len(LABELS) == 48 and len(GROUP_OF) == 48

# ---- load matrix: 48 metrics x 192 files -----------------------------------
wb = openpyxl.load_workbook(DB, read_only=True, data_only=True)
ws = wb["Sheet1"]
rows = list(ws.iter_rows(values_only=True))
# sheet row (1+k) = mymetricsa idx k ; panel rows = idx 8..55 => sheet rows 9..56
# file columns = 2..193 (C1..C192)
data = []
for k in range(8, 56):
    sheet_row = rows[1 + k]
    vals = sheet_row[2:194]
    data.append([float(v) if isinstance(v, (int, float)) else np.nan for v in vals])
X = np.array(data)                      # 48 x 192  (metrics x files)
print(f"Loaded matrix: {X.shape[0]} metrics x {X.shape[1]} files")

# ---- clean: drop near-constant metrics (zero variance -> undefined corr) ----
finite = np.isfinite(X)
X = np.where(finite, X, np.nan)
col_ok = np.isfinite(X).all(axis=0)
X = X[:, col_ok]
print(f"Files with complete data: {X.shape[1]}")

std = np.nanstd(X, axis=1)
near_const = std < 1e-9 * (np.abs(np.nanmean(X, axis=1)) + 1e-9)
dropped = [LABELS[i] for i in range(48) if near_const[i]]
keep = ~near_const
print(f"Dropped near-constant metrics ({near_const.sum()}): {dropped}")

Xk = X[keep]
labels = [LABELS[i] for i in range(48) if keep[i]]
groups = [GROUP_OF[i] for i in range(48) if keep[i]]
p = Xk.shape[0]

# ---- Spearman correlation (robust to heavy-tailed moment/overflow metrics) --
C, _ = spearmanr(Xk, axis=1)            # p x p
C = np.nan_to_num(C, nan=0.0)
np.fill_diagonal(C, 1.0)

# ---- eigen-spectrum / effective dimensionality ------------------------------
eig = np.sort(np.linalg.eigvalsh(C))[::-1]
eig = np.clip(eig, 0, None)
cum = np.cumsum(eig) / eig.sum()
kaiser = int((eig > 1).sum())
pr = (eig.sum() ** 2) / (eig ** 2).sum()          # participation ratio
n80 = int(np.searchsorted(cum, 0.80) + 1)
n90 = int(np.searchsorted(cum, 0.90) + 1)
n95 = int(np.searchsorted(cum, 0.95) + 1)

print("\n=== EFFECTIVE DIMENSIONALITY (of %d usable metrics) ===" % p)
print(f"  Kaiser (eigenvalue>1)      : {kaiser}")
print(f"  Participation ratio        : {pr:.1f}")
print(f"  PCs for 80% variance       : {n80}")
print(f"  PCs for 90% variance       : {n90}")
print(f"  PCs for 95% variance       : {n95}")
print(f"  PC1 alone explains         : {cum[0]*100:.1f}%")
print(f"  Top-5 PCs explain          : {cum[4]*100:.1f}%")

# ---- hierarchical clustering on correlation distance ------------------------
D = 1.0 - np.abs(C)
np.fill_diagonal(D, 0.0)
D = (D + D.T) / 2
Z = linkage(squareform(D, checks=False), method="average")

for k in (6, 8, 10, 12):
    cl = fcluster(Z, t=k, criterion="maxclust")
    sizes = np.bincount(cl)[1:]
    print(f"\n--- {k} clusters (sizes {sorted(sizes, reverse=True)}) ---")
    for c in range(1, k + 1):
        members = [(labels[i], groups[i]) for i in range(p) if cl[i] == c]
        if not members:
            continue
        gtags = sorted(set(g for _, g in members))
        names = ", ".join(m for m, _ in members)
        print(f"  C{c:2d} [{'/'.join(gtags)}]: {names}")

# ---- PCA loadings: what each of the top components means --------------------
Zs = (Xk - np.nanmean(Xk, axis=1, keepdims=True)) / np.nanstd(Xk, axis=1, keepdims=True)
U, S, Vt = np.linalg.svd(np.nan_to_num(Zs), full_matrices=False)
print("\n=== TOP PRINCIPAL COMPONENTS (metric loadings) ===")
var = (S ** 2) / (S ** 2).sum()
for pc in range(5):
    load = U[:, pc]
    order = np.argsort(-np.abs(load))[:6]
    terms = ", ".join(f"{labels[i]}({load[i]:+.2f})" for i in order)
    print(f"  PC{pc+1} ({var[pc]*100:4.1f}% var): {terms}")

# ---- figures ----------------------------------------------------------------
# scree
plt.figure(figsize=(7, 4))
plt.bar(range(1, len(eig)+1), eig, color="#4C72B0")
plt.axhline(1.0, color="crimson", ls="--", lw=1, label="Kaiser (=1)")
plt.plot(range(1, len(eig)+1), cum*eig.sum(), color="#55A868", marker=".", label="cumulative")
plt.xlabel("Component"); plt.ylabel("Eigenvalue")
plt.title(f"Scree - Brain Panel internal structure (eff. dim ~{pr:.0f} of {p})")
plt.legend(); plt.tight_layout()
plt.savefig(os.path.join(OUT, "scree.png"), dpi=130); plt.close()

# clustered correlation heatmap
order = leaves_list(Z)
Cc = C[np.ix_(order, order)]
lab_o = [labels[i] for i in order]
plt.figure(figsize=(12, 10))
im = plt.imshow(Cc, cmap="RdBu_r", vmin=-1, vmax=1)
plt.colorbar(im, fraction=0.046, pad=0.04, label="Spearman r")
plt.xticks(range(p), lab_o, rotation=90, fontsize=6)
plt.yticks(range(p), lab_o, fontsize=6)
plt.title("Brain Panel metric correlation (hierarchically ordered)")
plt.tight_layout()
plt.savefig(os.path.join(OUT, "clustered_corr.png"), dpi=130); plt.close()

# dendrogram
plt.figure(figsize=(13, 5))
dendrogram(Z, labels=labels, leaf_font_size=6, color_threshold=0.7*max(Z[:,2]))
plt.ylabel("1 - |r|")
plt.title("Metric clustering dendrogram")
plt.tight_layout()
plt.savefig(os.path.join(OUT, "dendrogram.png"), dpi=130); plt.close()

print(f"\nFigures written to {OUT}")
