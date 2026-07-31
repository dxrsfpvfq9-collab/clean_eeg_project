"""Build the Word document: Brain Panel internal structure + 6-axis model + discriminants."""
import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "out_structure")
OUT = os.path.join(HERE, "out", "BrainPanel_6Axis_Model.docx")

NAVY = RGBColor(0x1F, 0x3A, 0x5F)
ACCENT = RGBColor(0xC4, 0x4E, 0x52)
GREY = RGBColor(0x55, 0x55, 0x55)

doc = Document()

# ---- base styles ----
normal = doc.styles["Normal"]
normal.font.name = "Calibri"; normal.font.size = Pt(10.5)
for i, sz in [(1, 20), (2, 14), (3, 12)]:
    h = doc.styles[f"Heading {i}"]
    h.font.name = "Calibri"; h.font.size = Pt(sz); h.font.bold = True
    h.font.color.rgb = NAVY

# ---- letter page + 1" margins ----
sec = doc.sections[0]
sec.page_width = Inches(8.5); sec.page_height = Inches(11)
for m in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
    setattr(sec, m, Inches(1))

def shade(cell, hexfill):
    tcpr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hexfill)
    tcpr.append(sh)

def para(text, size=10.5, bold=False, italic=False, color=None, after=6, before=0, align=None):
    p = doc.add_paragraph(); r = p.add_run(text)
    r.font.size = Pt(size); r.bold = bold; r.italic = italic
    if color: r.font.color.rgb = color
    p.paragraph_format.space_after = Pt(after); p.paragraph_format.space_before = Pt(before)
    if align: p.alignment = align
    return p

def bullet(text, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_lead:
        r = p.add_run(bold_lead); r.bold = True
        p.add_run(text)
    else:
        p.add_run(text)
    p.paragraph_format.space_after = Pt(3)
    return p

def table(headers, rows, widths, header_fill="1F3A5F", zebra=True, font=9):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    hdr = t.rows[0].cells
    for i, htext in enumerate(headers):
        hdr[i].width = Inches(widths[i]); shade(hdr[i], header_fill)
        p = hdr[i].paragraphs[0]; p.paragraph_format.space_after = Pt(2)
        r = p.add_run(htext); r.bold = True; r.font.size = Pt(font)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for ci, val in enumerate(row):
            cells[ci].width = Inches(widths[ci])
            if zebra and ri % 2 == 1: shade(cells[ci], "F0F3F7")
            p = cells[ci].paragraphs[0]; p.paragraph_format.space_after = Pt(1)
            rr = p.add_run(str(val)); rr.font.size = Pt(font)
            if ci == 0: rr.bold = True
    return t

def figure(fname, width=6.3, caption=None):
    path = os.path.join(FIG, fname)
    doc.add_picture(path, width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if caption:
        para(caption, size=8.5, italic=True, color=GREY, after=10, align=WD_ALIGN_PARAGRAPH.CENTER)

def page_number_footer():
    footer = sec.footer
    p = footer.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Page "); run.font.size = Pt(8); run.font.color.rgb = GREY
    fld1 = OxmlElement("w:fldSimple"); fld1.set(qn("w:instr"), "PAGE")
    p._p.append(fld1)

page_number_footer()

# =====================  TITLE  =====================
tp = doc.add_paragraph(); tp.alignment = WD_ALIGN_PARAGRAPH.LEFT
tr = tp.add_run("The BrainML Brain Panel: Internal Structure\nand a Six-Axis Signature Model")
tr.bold = True; tr.font.size = Pt(22); tr.font.color.rgb = NAVY
para("A data-driven decomposition of the 48-metric panel, and direction-aware discriminant "
     "functions derived from it.", size=12, italic=True, color=GREY, after=4)
para("Stress Therapy Solutions / BrainMaster Technologies", size=10, bold=True, after=0)
para("Prepared for T. Collura  •  Reference database: EC_191 (192 eyes-closed recordings)  "
     "•  Validation cohort: 98 EC panels (v2025_brainml)", size=9, color=GREY, after=2)
para("This document is a research/analysis record. Discriminant weights are prototypes fit on "
     "auto-extracted labels from a single cohort — not shipped clinical thresholds. See "
     "Limitations.", size=9, italic=True, color=ACCENT, after=6)

# rule
def hrule():
    p = doc.add_paragraph(); pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr"); bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "1"); bottom.set(qn("w:color"), "1F3A5F")
    pbdr.append(bottom); pPr.append(pbdr)
hrule()

# =====================  1. EXEC SUMMARY  =====================
doc.add_heading("1. Executive summary", level=1)
para("The Brain Panel presents 48 quantitative EEG metrics, each as a z-score against a "
     "192-recording reference population. This report analyzes the panel's internal covariance "
     "structure and rebuilds its clinical detectors on that structure. Four findings:", after=6)
bullet(" The 48 metrics have the information content of roughly six independent axes "
       "(participation ratio 6.5). They are not 48 independent measurements.",
       bold_lead="Low effective dimensionality.")
bullet(" A single general-amplitude/power factor explains 35% of all variance; 21 of 48 metrics "
       "have over half their variance explained by it. The list-of-48 view therefore overstates "
       "severity through redundancy.", bold_lead="One dominant factor.")
bullet(" Collapsing the panel to six named, interpretable axes yields a compact per-recording "
       "“signature.” Of reference files that flag ≥5 raw rows, 73% are explained by "
       "≤1 axis.", bold_lead="A six-axis signature.")
bullet(" Re-deriving the six clinical discriminants on these axes, with direction (sign) taken "
       "into account, recovers detectors the published weights got wrong — notably drowsiness "
       "(AUC 0.44→0.72) and EEG quality (0.76→0.82).",
       bold_lead="Superior direction-aware detectors.")

# =====================  2. BACKGROUND  =====================
doc.add_heading("2. Background: what the Brain Panel measures", level=1)
para("The panel computes 48 metrics (mymetricsa indices 8–55) spanning six a-priori groups: "
     "Std/Global (2), PDR / posterior-dominant-rhythm (9), Phenotypes (6), Focal (12), Diffuse (7), "
     "and State-Shift moment metrics (12). Each metric is standardized against the EC_191 reference "
     "database and rendered as a z-score with a color-coded bar.", after=6)
para("The limitation this report addresses: the panel is presented as 48 independent verdicts. "
     "With 48 correlated metrics, (a) 2–3 will cross |z|≥2 by chance in a normal brain, and "
     "(b) many metrics move together, so a single physical fact can light up a dozen rows. The "
     "list-of-alarms format under-delivers on integration and inflates apparent abnormality.",
     after=6)

# =====================  3. INTERNAL STRUCTURE  =====================
doc.add_heading("3. Internal structure analysis", level=1)
para("Method: Spearman correlation (robust to the heavy-tailed moment metrics), eigen-decomposition, "
     "and hierarchical clustering on the 48×192 metric-by-file matrix from the reference database. "
     "No external labels — purely structural.", italic=True, after=8)

doc.add_heading("3.1  Effective dimensionality", level=2)
table(["Measure", "Value", "Interpretation"],
      [["Participation ratio", "6.5", "Effective # of independent axes"],
       ["Eigenvalues > 1 (Kaiser)", "11", "Upper bound on meaningful factors"],
       ["PCs for 80% variance", "12", "Most structure in a low-dim subspace"],
       ["PCs for 90% / 95%", "19 / 25", "Long thin tail of near-noise"],
       ["PC1 alone", "35% of variance", "One factor dominates everything"],
       ["Top 5 PCs", "63% of variance", "Six-ish axes carry the signal"]],
      [2.3, 1.6, 2.4])
para("", after=2)

doc.add_heading("3.2  The dominant factor is overall amplitude", level=2)
para("Twenty-one of 48 metrics have more than half their variance explained by a single general "
     "factor. In the clustered correlation heatmap below, the entire lower-right quadrant is one "
     "deep-red block of ~25 metrics correlating 0.5–0.9 — all absolute-amplitude / power "
     "quantities (the *Amp metrics, the Moment-2 family, Global STD, the absolute Diffuse/Frontal "
     "powers). These co-scale with the recording’s overall amplitude (gain, skull, impedance, "
     "age) and are partly a nuisance dimension.", after=6)
figure("clustered_corr.png", width=5.6,
       caption="Figure 1. Hierarchically-ordered metric correlation. Lower-right red mass = one "
               "amplitude factor measured ~25 ways; top-left pale scatter = the metrics carrying "
               "unique information.")
figure("scree.png", width=5.6,
       caption="Figure 2. Eigenvalue scree. Effective dimensionality ~6.5 of 48; the tail past "
               "component ~12 is near-noise.")

table(["Most amplitude-dominated (r² with general factor)",
       "Most independent (unique information, r²≈0)"],
      [["PDRMoment2 (77%), BetaMoment2 (75%), DeltaMoment2 (75%)",
        "PDR Symm, PDR Synch, PDR Reg, PDR Amp"],
       ["ThetaMoment2 (74%), FocalBetaAmp (71%), DiffuseTheta (71%)",
        "PDR Sinus, PDR BurstWidth, PDR FFTWidth"],
       ["FocalThetaAmp (69%), FocalDeltaAmp (68%), Global STD (65%)",
        "FocalDelta, FocalBeta, FocalHiBeta, FastAlpha"],
       ["→ the *Amp / Moment-2 / absolute-power rows are near-duplicates",
        "→ the normalized ratio / shape indices earn the panel’s keep"]],
      [3.15, 3.15], font=8.5)

# =====================  4. THE 6-AXIS MODEL  =====================
doc.add_heading("4. The six-axis signature model", level=1)
para("A varimax-rotated factor model (frozen to out_structure/axis_model.json) assigns each metric "
     "to one interpretable axis. Any recording’s 48 metrics map to six population z-scores. "
     "Each axis score is the sign-aligned mean of its member metrics’ z-scores, standardized on "
     "the reference population — so an axis value is itself a z-score, flagged at |z|≥2.",
     after=6)
table(["Axis", "n", "Meaning", "Top contributing metrics"],
      [["A0", "22", "Overall Amplitude / Power",
        "FocalThetaAmp, Moment-2 family, *Amp, Global STD(−)"],
       ["A1", "7", "PDR / Rhythm Organization",
        "PDR Synch(+), PDR Amp(−), PDR Reg(−), PDR Symm(−)"],
       ["A2", "8", "Fast Activity (Beta/Gamma)",
        "FrontalGamma, DiffuseHiBeta, FocalBeta, FastAlpha"],
       ["A3", "4", "Transients / Line-noise",
        "DeltaMoment3, Diffuse60Hz, FrontGammaAsym"],
       ["A4", "4", "Focal Slowing",
        "FocalDelta, FocalTheta, XS TempAlpha, PDR BurstWidth(−)"],
       ["A5", "3", "Topographic Gradient",
        "PDR MaxPost, Beta MaxFront, Front AlphaAsym"]],
      [0.5, 0.35, 2.05, 3.4], font=8.5)
para("", after=2)

doc.add_heading("4.1  Compression: the alarm-storm is usually one finding", level=2)
para("Across the 192 reference files, the 48-row view flags on average 1.7 rows (max 20), but the "
     "six-axis view flags 0.22 axes on average (max 2). Of the 15 files where ≥5 raw rows are "
     "flagged, 73% collapse to ≤1 axis — i.e. one physical fact shown many times.", after=6)
figure("fingerprint_demo.png", width=6.3,
       caption="Figure 3. Per-recording six-axis signatures vs the 48-row count. Top-right: 10 raw "
               "rows collapse to “amplitude high.” Bottom-right: 17 rows read as one thing, "
               "“Fast Activity +3.5.” Bottom-left: only 1 raw row crosses threshold, yet the "
               "axis aggregation surfaces a coherent “Focal Slowing +2.5” — catching "
               "distributed sub-threshold signal.")

# =====================  5. AXIS DISCRIMINANTS  =====================
doc.add_heading("5. Re-deriving the discriminants on the axes", level=1)
para("The published discriminants (Collura et al., 2026) score each clinical outcome as a weighted "
     "count of out-of-bounds rows in the a-priori groups. On the 98-case validation cohort these did "
     "not replicate (Phase D: AUC 0.36–0.73). We re-fit each detector on the six covariance axes "
     "instead, same 5-fold CV. Result: axes recover the state/organization outcomes, while the "
     "a-priori groups remain better for the amplitude/artifact outcomes.", after=6)
figure("axis_vs_group_auc.png", width=6.3,
       caption="Figure 4. Empirical AXES vs a-priori GROUPS, 5-fold CV ROC-AUC. Axes recover "
               "clinical abnormality (0.36→0.73), drowsiness (0.50→0.71) and paroxysmal "
               "(0.21→0.61); groups still win EEG quality and artifact.")
para("Why: the published “State-Shift” group lumps the amplitude-driven Moment-2 metrics "
     "together with true state metrics. Separating amplitude (A0) from organization (A1) and "
     "fast/transient activity (A2/A3) exposes the buried signal.", italic=True, after=6)

# =====================  6. COMBINED v2  =====================
doc.add_heading("6. Combined direction-aware discriminants (v2)", level=1)
para("Finally we gave a model all three information sources at once — the 48 signed z-scores, "
     "the 6 signed axes, the 6 group counts, and directional n_high / n_low counts (62 features) "
     "— under L1 sparsity, judged by repeated 5×20 cross-validation. Unlike the published "
     "|z|≥2 counting, every feature is signed: the direction of each deviation matters.", after=6)
table(["Outcome", "npos", "Paper", "GROUPS", "AXES", "COMB-L1", "v2 pick"],
      [["EEG quality", "15", "0.76", "0.80", "0.71", "0.82", "combined 0.82"],
       ["Drowsiness", "59", "0.44", "0.54", "0.72", "0.70", "axes 0.72"],
       ["Artifact", "29", "0.57", "0.68", "0.58", "0.56", "groups 0.68"],
       ["Clinical abnorm.", "7", "0.63", "0.52", "0.67", "0.46", "axes 0.67*"],
       ["Paroxysmal", "5", "0.59", "0.25", "0.61", "0.31", "axes 0.61*"],
       ["PDR frequency", "2", "0.56", "—", "—", "—", "not learnable"]],
      [1.5, 0.55, 0.7, 0.8, 0.7, 0.85, 1.3], font=8.5)
para("Repeated 5×20-fold CV ROC-AUC. * small positive class — unstable, provisional.",
     size=8, italic=True, color=GREY, after=8)
figure("combined_auc.png", width=6.3,
       caption="Figure 5. Combined direction-aware model vs prior bases (error bars = CV std). "
               "The combined model wins cleanly only for EEG quality, where positives and signal "
               "are both sufficient.")

doc.add_heading("6.1  Three conclusions", level=2)
bullet(" Feeding all 48 individual deviations + axes + direction into one model overfits wherever "
       "the positive class is small (clinical 0.46, paroxysmal 0.31 — worse than the paper). "
       "More information ≠ better detector at n≈98.", bold_lead="A kitchen-sink model is not superior.")
bullet(" The fusion wins only where signal and positives are both sufficient — EEG quality, 0.82, "
       "combining +STD Raw, +PDRMoment3, +std_global count, +n_high (high raw amplitude, spiky, many "
       "elevated rows → poor quality).", bold_lead="Fusion helps where data allows.")
bullet(" The published drowsiness count was inverted (0.44). The signed axis model reads drowsy = low "
       "amplitude + more sinusoidal rhythm and scores 0.72 — a large, correctly-oriented gain.",
       bold_lead="Direction-awareness fixes drowsiness.")
para("The superior artifact is therefore an outcome-matched, direction-aware ensemble (implemented in "
     "discriminant_v2.py: score_panel), not a single combined model.", bold=True, after=6)

# =====================  7. LIMITATIONS  =====================
doc.add_heading("7. Limitations", level=1)
bullet(" clinical (7), paroxysmal (5), PDR-frequency (2). Their AUCs are unstable; picks are "
       "provisional. Drowsiness (59) and artifact (29) are the trustworthy estimates.",
       bold_lead="Small positive classes:")
bullet(" ground-truth labels are regex-extracted from report templates, not human-adjudicated.",
       bold_lead="Auto-extracted labels:")
bullet(" weights fit on one cohort are in-sample-optimistic (full-sample AUCs run 0.05–0.12 above "
       "CV). Validate on an adjudicated hold-out before any clinical use.", bold_lead="Single cohort:")
bullet(" drowsiness↑ with low amplitude is statistically clear but physiologically debated "
       "(possible cleanliness confound). ", bold_lead="Causal reading unsettled:")
bullet(" Sections 5 and 6 use different CV protocols (single 5-fold vs repeated 5×20), so axis/group "
       "AUCs shift a few points between them; the repeated-CV figures in Section 6 are the more stable.",
       bold_lead="CV protocol:")

# =====================  8. FILES  =====================
doc.add_heading("8. Files and reproducibility", level=1)
para("All under research/validation_2026/ :", after=4)
table(["Artifact", "Purpose"],
      [["internal_structure_analysis.py", "Correlation / eigen / clustering (Figs 1–2)"],
       ["panel_signature.py", "6-axis model + fingerprint renderer (Fig 3)"],
       ["out_structure/axis_model.json", "Frozen axis definitions (drop-in for the report)"],
       ["axis_discriminants.py", "Axis vs group re-derivation (Fig 4)"],
       ["combined_discriminants.py", "Direction-aware v2 evaluation (Fig 5)"],
       ["discriminant_v2.py + .json", "Usable scorer: score_panel(z48) → probabilities"],
       ["out/DISCRIMINANT_V2_FINDINGS.md", "Detailed findings write-up"]],
      [2.9, 3.4], font=9)

doc.add_heading("9. Next step", level=1)
para("The binding limit is label quantity for the rare outcomes. Harvesting symptom-checklist and "
     "medication data from the practice’s online records (see SCRAPING_PLAN.md) to add 20–30 "
     "positive cases each for paroxysmal, clinical abnormality, and PDR-frequency would let those "
     "detectors be validated rather than remain provisional.", after=6)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
doc.save(OUT)
print("saved", OUT)
