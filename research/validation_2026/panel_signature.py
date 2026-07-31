"""
Task 1 -- the 6-axis Brain Panel "signature".

Collapse the 48 correlated metrics into 6 interpretable, empirically-derived
axes and score any recording as 6 population z-scores instead of 48 rows.

Method:
  1. Standardize the 48 metrics on the EC_191 reference DB (per-metric z).
  2. PCA -> top-6 loadings -> VARIMAX rotation (interpretable factors).
  3. Assign each metric to its dominant rotated factor (sign-aligned).
  4. Axis score = sign-aligned mean of member z-scores, standardized to
     mean 0 / std 1 on the reference population -> a per-axis z-score.
  5. Freeze the model (mu, sd, membership, signs, axis mean/std) to JSON so
     the report can score a new recording with no refit.

Run:  py panel_signature.py
Outputs: out_structure/axis_model.json, out_structure/fingerprint_*.png
"""
import os, json, numpy as np, openpyxl
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
DB   = os.path.join(HERE, "..", "..", "EC_191.out_file.icale.xlsx")
OUT  = os.path.join(HERE, "out_structure"); os.makedirs(OUT, exist_ok=True)
NAMESDB = os.path.join(HERE, "..", "..", "EC_191.names_file.icale.xlsx")

AXIS_NAMES = ["Overall Amplitude/Power", "PDR / Rhythm Organization",
              "Fast Activity (Beta/Gamma)", "Transients / Line-noise",
              "Focal Slowing", "Topographic Gradient"]

LABELS = ["STD Raw","Global STD","PDR Symm","PDR Synch","PDR Reg","PDR Mag",
 "PDR Sinus","PDR MaxPost","PDR FFTWidth","PDR Amp","PDR BurstWidth","Beta MaxFront",
 "Front AlphaAsym","XS TempAlpha","FastAlpha","AlphaPeak","MidlineBeta","FocalDelta",
 "FocalDeltaAmp","FocalTheta","FocalThetaAmp","FocalHiBeta","FocalHiBetaAmp","FocalBeta",
 "FocalBetaAmp","FrontalDelta","FrontalTheta","FrontalGamma","FrontGammaAsym","DiffuseDelta",
 "DiffuseTheta","DiffuseHiBeta","DiffuseBeta","DiffuseGamma","Diffuse60Hz","FractalDim",
 "PDRMoment1","PDRMoment2","PDRMoment3","BetaMoment1","BetaMoment2","BetaMoment3",
 "ThetaMoment1","ThetaMoment2","ThetaMoment3","DeltaMoment1","DeltaMoment2","DeltaMoment3"]
NAXES = 6

def load_matrix():
    wb = openpyxl.load_workbook(DB, read_only=True, data_only=True); ws = wb["Sheet1"]
    rows = list(ws.iter_rows(values_only=True))
    X = np.array([[float(v) if isinstance(v,(int,float)) else np.nan
                   for v in rows[1+k][2:194]] for k in range(8,56)])   # 48 x 192
    ok = np.isfinite(X).all(0)
    return X[:, ok]

def varimax(Phi, gamma=1.0, q=200, tol=1e-7):
    p, k = Phi.shape; R = np.eye(k); d = 0.0
    for _ in range(q):
        d_old = d
        L = Phi @ R
        M = L**3 - (gamma/p) * L @ np.diag(np.diag(L.T @ L))
        u, s, vh = np.linalg.svd(Phi.T @ M)
        R = u @ vh; d = s.sum()
        if d_old and d/d_old < 1 + tol: break
    return Phi @ R

def build_model():
    X = load_matrix()                          # 48 x nfiles
    mu = X.mean(1); sd = X.std(1); sd[sd == 0] = 1.0
    Z = ((X - mu[:,None]) / sd[:,None])         # 48 x nfiles  (per-metric z)
    C = np.corrcoef(Z)                          # 48 x 48
    w, V = np.linalg.eigh(C)
    idx = np.argsort(w)[::-1][:NAXES]
    Phi = V[:, idx] * np.sqrt(np.clip(w[idx], 0, None))    # PCA loadings 48 x 6
    L = varimax(Phi)                            # rotated loadings 48 x 6

    # orient each factor so its dominant loader is positive
    for j in range(NAXES):
        if L[np.argmax(np.abs(L[:, j])), j] < 0: L[:, j] *= -1

    assign = np.argmax(np.abs(L), axis=1)       # metric -> dominant axis
    sign   = np.sign([L[i, assign[i]] for i in range(48)])

    # axis raw score per file = sign-aligned mean of member z-scores
    axis_raw = np.zeros((NAXES, Z.shape[1]))
    members = {j: [i for i in range(48) if assign[i] == j] for j in range(NAXES)}
    for j in range(NAXES):
        m = members[j]
        axis_raw[j] = (sign[m][:,None] * Z[m]).mean(0)
    ax_mu = axis_raw.mean(1); ax_sd = axis_raw.std(1); ax_sd[ax_sd==0] = 1.0
    axis_z = (axis_raw - ax_mu[:,None]) / ax_sd[:,None]

    model = dict(labels=LABELS, mu=mu.tolist(), sd=sd.tolist(),
                 loadings=L.tolist(), assign=assign.tolist(), sign=sign.tolist(),
                 ax_mu=ax_mu.tolist(), ax_sd=ax_sd.tolist(),
                 members={str(j): members[j] for j in range(NAXES)})
    return model, Z, axis_z

def score_recording(raw48, model):
    """raw48 = the 48 Brain Panel metric values (mymetricsa idx 8..55) for one
    recording. Returns dict axis_name -> population z-score."""
    mu = np.array(model["mu"]); sd = np.array(model["sd"])
    z = (np.asarray(raw48, float) - mu) / sd
    assign = np.array(model["assign"]); sign = np.array(model["sign"])
    ax_mu = np.array(model["ax_mu"]); ax_sd = np.array(model["ax_sd"])
    out = {}
    for j in range(NAXES):
        m = np.where(assign == j)[0]
        raw = (sign[m] * z[m]).mean()
        out[j] = (raw - ax_mu[j]) / ax_sd[j]
    return out

def load_names():
    wb = openpyxl.load_workbook(NAMESDB, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]; rows = list(ws.iter_rows(values_only=True))
    out = []
    for r in rows[1:]:
        s = str(r[0]).strip().strip("'")
        out.append(os.path.basename(s.replace("\\", "/")))
    return out

def render_fingerprint(ax, axis_z_one, n_oob, title):
    y = np.arange(NAXES)[::-1]
    vals = np.array([axis_z_one[j] for j in range(NAXES)])
    colors = ["#C44E52" if abs(v) >= 2 else "#DD8452" if abs(v) >= 1 else "#8FA5B8"
              for v in vals]
    ax.axvspan(-2, 2, color="#EAF0EA", zorder=0)
    ax.axvspan(-1, 1, color="#DCE7DC", zorder=0)
    ax.barh(y, vals, color=colors, height=0.62, zorder=3)
    ax.axvline(0, color="#444", lw=0.8, zorder=4)
    for j in range(NAXES):
        v = vals[j]
        ax.text(v + (0.12 if v >= 0 else -0.12), y[j], f"{v:+.1f}",
                va="center", ha="left" if v >= 0 else "right", fontsize=8)
    ax.set_yticks(y); ax.set_yticks(y, [AXIS_NAMES[j] for j in range(NAXES)], fontsize=8)
    ax.set_xlim(-6, 6); ax.set_xlabel("axis z-score (population)", fontsize=8)
    ax.set_title(f"{title}\n(48-row view flags {n_oob} rows |z|>=2)", fontsize=9)
    ax.tick_params(labelsize=8)

if __name__ == "__main__":
    model, Z, axis_z = build_model()          # Z:48xN  axis_z:6xN
    L = np.array(model["loadings"]); assign = np.array(model["assign"])
    print("=== 6 empirical axes: membership + top loaders ===")
    for j in range(NAXES):
        m = sorted([i for i in range(48) if assign[i]==j], key=lambda i:-abs(L[i,j]))
        top = ", ".join(f"{LABELS[i]}({L[i,j]:+.2f})" for i in m[:8])
        print(f"\nAXIS {j} = {AXIS_NAMES[j]} ({len(m)} metrics): {top}"
              + (" ..." if len(m) > 8 else ""))
    with open(os.path.join(OUT, "axis_model.json"), "w") as f:
        json.dump(model, f)
    np.save(os.path.join(OUT, "axis_z_allfiles.npy"), axis_z)
    print(f"\nModel frozen -> out_structure/axis_model.json  (axis_z {axis_z.shape})")

    # ---- demo: pick illustrative reference files & render fingerprints ------
    names = load_names()
    n_oob = (np.abs(Z) >= 2).sum(0)           # per-file count of OOB raw rows
    absz = np.abs(axis_z)
    picks = {}
    picks["Most normal (flat signature)"]   = int(np.argmin(absz.sum(0)))
    picks["Amplitude-dominant"]             = int(np.argmax(axis_z[0]))
    picks["Focal slowing (Axis 4)"]         = int(np.argmax(axis_z[4]))
    picks["Fast activity (Axis 2)"]         = int(np.argmax(axis_z[2]))
    fig, axes = plt.subplots(2, 2, figsize=(13, 7.5))
    for ax, (cap, fidx) in zip(axes.ravel(), picks.items()):
        one = {j: float(axis_z[j, fidx]) for j in range(NAXES)}
        render_fingerprint(ax, one, int(n_oob[fidx]), f"{cap}\n{names[fidx][:46]}")
    fig.suptitle("Brain Panel 6-axis SIGNATURE  vs  the 48-row view", fontsize=12)
    fig.tight_layout(rect=[0,0,1,0.96])
    fig.savefig(os.path.join(OUT, "fingerprint_demo.png"), dpi=130); plt.close()
    print("Rendered out_structure/fingerprint_demo.png")

    # how much does the 6-axis view compress the flagged-row story?
    print("\n=== compression check (across 192 reference files) ===")
    print(f"  mean raw rows flagged |z|>=2 : {n_oob.mean():.1f}  (max {n_oob.max()})")
    axis_flag = (absz >= 2).sum(0)
    print(f"  mean AXES flagged |z|>=2     : {axis_flag.mean():.2f}  (max {axis_flag.max()})")
    # of files with >=5 raw rows flagged, how often is it really 1 axis?
    busy = n_oob >= 5
    one_axis = (axis_flag[busy] <= 1).mean() if busy.any() else 0
    print(f"  of {busy.sum()} files with >=5 rows flagged, {one_axis*100:.0f}% "
          f"are explained by <=1 axis")
