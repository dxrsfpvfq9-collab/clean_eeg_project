"""Stage 2: is PC1 a nuisance amplitude/gain factor? Partial it out and
re-cluster the residuals to reveal the clinically-independent axes."""
import os, numpy as np, openpyxl
from scipy.stats import spearmanr, rankdata
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "..", "..", "EC_191.out_file.icale.xlsx")
LABELS = ["STD Raw","Global STD","PDR Symm","PDR Synch","PDR Reg","PDR Mag",
 "PDR Sinus","PDR MaxPost","PDR FFTWidth","PDR Amp","PDR BurstWidth","Beta MaxFront",
 "Front AlphaAsym","XS TempAlpha","FastAlpha","AlphaPeak","MidlineBeta","FocalDelta",
 "FocalDeltaAmp","FocalTheta","FocalThetaAmp","FocalHiBeta","FocalHiBetaAmp","FocalBeta",
 "FocalBetaAmp","FrontalDelta","FrontalTheta","FrontalGamma","FrontGammaAsym","DiffuseDelta",
 "DiffuseTheta","DiffuseHiBeta","DiffuseBeta","DiffuseGamma","Diffuse60Hz","FractalDim",
 "PDRMoment1","PDRMoment2","PDRMoment3","BetaMoment1","BetaMoment2","BetaMoment3",
 "ThetaMoment1","ThetaMoment2","ThetaMoment3","DeltaMoment1","DeltaMoment2","DeltaMoment3"]
GROUP_OF=(["Std"]*2+["PDR"]*9+["Phen"]*6+["Focal"]*12+["Diff"]*7+["State"]*12)

wb=openpyxl.load_workbook(DB,read_only=True,data_only=True); ws=wb["Sheet1"]
rows=list(ws.iter_rows(values_only=True))
X=np.array([[float(v) if isinstance(v,(int,float)) else np.nan
             for v in rows[1+k][2:194]] for k in range(8,56)])
X=X[:,np.isfinite(X).all(0)]
labels,groups=LABELS,GROUP_OF; p=X.shape[0]

R=np.vstack([rankdata(X[i]) for i in range(p)])
Zs=(R-R.mean(1,keepdims=True))/R.std(1,keepdims=True)
U,S,Vt=np.linalg.svd(Zs,full_matrices=False)
pc1=Vt[0]; var1=S[0]**2/(S**2).sum()
comm=np.array([np.corrcoef(Zs[i],pc1)[0,1]**2 for i in range(p)])
print(f"General factor (PC1) = {var1*100:.1f}% of total variance")
print(f"Metrics >50% explained by that ONE factor: {(comm>0.5).sum()}/{p}")
o=np.argsort(-comm)
print("\nMOST amplitude-dominated (r^2 with general factor):")
for i in o[:14]: print(f"  {comm[i]*100:5.1f}%  {labels[i]:16s} [{groups[i]}]")
print("\nMOST INDEPENDENT (carry unique, normalized info):")
for i in o[::-1][:14]: print(f"  {comm[i]*100:5.1f}%  {labels[i]:16s} [{groups[i]}]")

Res=Zs-U[:,:1]@np.diag(S[:1])@Vt[:1]
Cr,_=spearmanr(Res,axis=1); Cr=np.nan_to_num(Cr); np.fill_diagonal(Cr,1)
D=1-np.abs(Cr); np.fill_diagonal(D,0); D=(D+D.T)/2
Zl=linkage(squareform(D,checks=False),method="average")
print("\n=== Residual clusters after removing the general amplitude factor ===")
cl=fcluster(Zl,t=9,criterion="maxclust")
for c in range(1,10):
    m=[f"{labels[i]}" for i in range(p) if cl[i]==c]
    if m: print(f"  R{c}: "+", ".join(m))
