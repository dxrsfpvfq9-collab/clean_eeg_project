"""Build the clinician quick-reference Word doc from the source markdown.

Layout:
  Cover page         — Title, subtitle, intro
  Section A          — Rule-OUT rules (high NPV / confident absent)
  Section B          — Rule-IN rules  (high PPV / confident present)
  Section C          — Per-recording decision flow (procedure)
  Section D          — Compact summary table
  Section E          — Caveats
  Section F          — One-line-per-outcome summary
  Per-recording checklist (printable page)

Run:  py research/validation_2026/_build_clinician_docx.py
Output: research/validation_2026/out/Brain_Panel_Quick_Reference.docx
"""
import os

from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "Brain_Panel_Quick_Reference.docx")

# Brand palette
NAVY      = RGBColor(0x1F, 0x3A, 0x5F)
TEAL      = RGBColor(0x2C, 0x73, 0x8A)
GREEN     = RGBColor(0x2E, 0x7D, 0x32)
ORANGE    = RGBColor(0xC8, 0x65, 0x00)
RED       = RGBColor(0xB7, 0x1C, 0x1C)
GREY      = RGBColor(0x55, 0x55, 0x55)
LIGHT_GREY = "EEEEEE"
ACCENT_FILL = "E1EBF2"
NPV_FILL = "E8F5E9"   # green-tinted for rule-OUT
PPV_FILL = "FFF3E0"   # orange-tinted for rule-IN


def set_cell_shading(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    tcPr.append(shd)


def add_horizontal_rule(doc, color="888888"):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)
    pBdr.append(bottom)
    pPr.append(pBdr)


def style_paragraph(para, *, size=11, bold=False, color=None, align=None,
                    space_before=0, space_after=4):
    if align is not None:
        para.alignment = align
    para.paragraph_format.space_before = Pt(space_before)
    para.paragraph_format.space_after = Pt(space_after)
    for run in para.runs:
        run.font.size = Pt(size)
        run.bold = bold
        if color is not None:
            run.font.color.rgb = color
        run.font.name = "Calibri"


def add_heading(doc, text, level=1, color=NAVY, size=None, space_before=12,
                space_after=4):
    sizes = {1: 22, 2: 16, 3: 13}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.font.size = Pt(size if size else sizes[level])
    run.font.color.rgb = color
    run.bold = True
    run.font.name = "Calibri"
    p.paragraph_format.keep_with_next = True
    return p


def add_para(doc, text, *, size=11, bold=False, italic=False, color=None,
             align=None, space_before=0, space_after=6):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.name = "Calibri"
    if color is not None:
        run.font.color.rgb = color
    return p


def add_rich_para(doc, parts, *, size=11, align=None, space_before=0,
                  space_after=6):
    """parts: list of (text, opts) where opts is dict with bold/italic/color."""
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    for text, opts in parts:
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(opts.get("size", size))
        run.bold = opts.get("bold", False)
        run.italic = opts.get("italic", False)
        if "color" in opts:
            run.font.color.rgb = opts["color"]
    return p


def add_bullet(doc, text, *, bullet_char="•", indent=0.25, size=11,
                bold=False, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(indent)
    p.paragraph_format.space_after = Pt(2)
    bullet_run = p.add_run(f"{bullet_char}  ")
    bullet_run.font.size = Pt(size)
    bullet_run.font.name = "Calibri"
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.name = "Calibri"
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color
    return p


def add_checkbox_line(doc, text, *, indent=0.0, size=12, bold=False):
    """Empty checkbox + text — for printable checklists."""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(indent)
    p.paragraph_format.space_after = Pt(4)
    box_run = p.add_run("☐  ")
    box_run.font.size = Pt(size + 2)
    box_run.font.name = "Segoe UI Symbol"
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.bold = bold
    run.font.name = "Calibri"
    return p


def add_simple_table(doc, header, rows, *, col_widths_in=None,
                      header_fill="1F3A5F", header_color=RGBColor(0xFF, 0xFF, 0xFF),
                      body_fill=None, alt_fill=None):
    """Make a styled table.  col_widths_in: list of inches."""
    table = doc.add_table(rows=1 + len(rows), cols=len(header))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    if col_widths_in:
        for col_idx, w in enumerate(col_widths_in):
            for cell in table.columns[col_idx].cells:
                cell.width = Inches(w)
    # Header row
    for i, txt in enumerate(header):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(txt)
        run.bold = True
        run.font.color.rgb = header_color
        run.font.size = Pt(10)
        run.font.name = "Calibri"
        p.paragraph_format.space_after = Pt(0)
        set_cell_shading(cell, header_fill)
    # Body rows
    for r_idx, row in enumerate(rows):
        for c_idx, txt in enumerate(row):
            cell = table.rows[1 + r_idx].cells[c_idx]
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(str(txt))
            run.font.size = Pt(10)
            run.font.name = "Calibri"
            p.paragraph_format.space_after = Pt(0)
            if body_fill:
                set_cell_shading(cell, body_fill)
            elif alt_fill and (r_idx % 2 == 1):
                set_cell_shading(cell, alt_fill)
    return table


def add_callout_box(doc, text, *, fill="E1EBF2", border="2C738A", bold=True,
                    color=NAVY):
    """A one-paragraph callout box (used for the Total-OOB-<-4 highlight)."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.rows[0].cells[0]
    cell.width = Inches(6.5)
    set_cell_shading(cell, fill)
    # cell border
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "10")
        b.set(qn("w:color"), border)
        tcBorders.append(b)
    tcPr.append(tcBorders)

    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(11)
    run.font.color.rgb = color
    run.font.name = "Calibri"
    return table


def add_page_break(doc):
    p = doc.add_paragraph()
    p.add_run().add_break()
    last_run = p.runs[-1]
    last_run._r.append(OxmlElement("w:br"))
    last_run._r[-1].set(qn("w:type"), "page")


# ---------- DOCUMENT BUILD ----------
def build():
    doc = Document()

    # Page setup — US Letter, 1" margins
    for section in doc.sections:
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Default body style
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # ===== COVER =====
    add_para(doc, "BrainML Brain Panel",
             size=12, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER,
             space_before=0, space_after=4)
    title = add_para(doc, "Quick-Reference Card", size=28, bold=True,
                     color=NAVY, align=WD_ALIGN_PARAGRAPH.CENTER,
                     space_before=0, space_after=4)
    add_para(doc, "A clinician's guide to high-confidence calls",
             size=14, italic=True, color=TEAL,
             align=WD_ALIGN_PARAGRAPH.CENTER,
             space_before=0, space_after=18)
    add_horizontal_rule(doc, "2C738A")

    add_heading(doc, "How to use this card", level=2, space_before=8)
    add_para(doc,
             "The Brain Panel reports 48 z-scored metrics grouped into seven "
             "categories (Std/Global, PDR, Phenotype, Focal/Frontal, Diffuse, "
             "State Shift, Total). This card translates those numbers into "
             "two kinds of high-confidence calls you can make at a glance:")
    add_bullet(doc,
        "RULE-OUT calls (Section A) — when a specific condition is met, the "
        "outcome is almost certainly absent. Negative call = confident clear.",
        bullet_char="◆", indent=0.3)
    add_bullet(doc,
        "RULE-IN calls (Section B) — when a specific condition is met, the "
        "outcome is almost certainly present. Positive call = confident finding.",
        bullet_char="◆", indent=0.3)
    add_para(doc,
             "Each call comes with a confidence number: NPV (negative "
             "predictive value) for rule-out, PPV (positive predictive value) "
             "for rule-in. If neither a rule-out nor a rule-in fires for a "
             "given outcome, the Brain Panel cannot make a confident call — "
             "the recording should get a full neurologist review.",
             space_before=4)
    add_para(doc,
             "These rules complement, rather than replace, neurologist "
             "judgment.  Section A rules were derived on a 91-EDF validation "
             "cohort and CROSS-VALIDATED on the combined independent cohort "
             "of 341 EDFs (100 original study + 242 newly-processed Q.A. "
             "review recordings, all labelled by Dr. P. David Ims).  "
             "Section B rules show the COMBINED-COHORT PPV — the most honest "
             "generalization estimate available.  Rules whose PPV falls "
             "below or near the outcome's prevalence in the cohort have "
             "been DROPPED, since at-or-below-prevalence PPV means a flag "
             "adds no information beyond the base rate.",
             italic=True, color=GREY, size=10, space_before=2)
    add_para(doc,
             "Pipeline-version note: z-scores are computed by the current "
             "(post-2026-06-12 bug-fix) Brain Panel pipeline.  Reports "
             "generated by older code versions (pre-fix) may have shifted "
             "z-score distributions for STD Raw, Global STD, and the four "
             "Moment-3 metrics; cross-validation here is performed only on "
             "PDFs produced by the same code version that will read this "
             "card.",
             italic=True, color=ORANGE, size=9, space_before=4)

    # ===== SECTION A — RULE-OUT =====
    add_page_break(doc)
    add_heading(doc, "Section A.  Rule-OUT rules",
                level=1, color=GREEN, size=22, space_before=0)
    add_para(doc,
             "When the condition listed below is met on the Brain Panel "
             "report, the outcome is almost certainly absent.",
             italic=True, color=GREY, size=11, space_after=10)

    # A1
    add_heading(doc, "A1.  No Clinical Abnormality", level=2, color=GREEN, size=14)
    add_rich_para(doc, [
        ("Condition:  ", {"bold": True}),
        ("Total OOB count < 4 (i.e., fewer than 4 metrics are out-of-bounds "
         "across the whole panel).", {}),
    ])
    add_rich_para(doc, [
        ("Confidence:  ", {"bold": True}),
        ("96% NPV derived (n=98); 92% NPV cross-cohort (n=100).  "
         "Of every 100 recordings cleared by this rule, ~92–96 will be "
         "clinically normal.", {}),
    ])
    add_rich_para(doc, [
        ("Action:  ", {"bold": True}),
        ("Routine review.  The recording is unlikely to contain significant "
         "clinical abnormalities.", {}),
    ])

    # A2
    add_heading(doc, "A2.  No Paroxysmal Events", level=2, color=GREEN, size=14)
    add_rich_para(doc, [
        ("Condition:  ", {"bold": True}),
        ("Total OOB count < 2.", {}),
    ])
    add_rich_para(doc, [
        ("Confidence:  ", {"bold": True}),
        ("100% NPV in both cohorts (no paroxysmal events were observed "
         "at this threshold in either the n=98 derivation or the n=100 "
         "cross-cohort).", {}),
    ])
    add_rich_para(doc, [
        ("Action:  ", {"bold": True}),
        ("Cleared for paroxysmal screening.  Note this is a rare finding in "
         "screening cohorts (~3% prevalence).", {}),
    ])

    # A3
    add_heading(doc, "A3.  No EEG Quality Concern  (strict version)",
                level=2, color=GREEN, size=14)
    add_rich_para(doc, [
        ("Condition:  ", {"bold": True}),
        ("State Shift OOB count = 0 — no Moment metrics out-of-bounds "
         "(PDR/Beta/Theta/Delta Moments 1, 2, 3 all within ±2 z).", {}),
    ])
    add_rich_para(doc, [
        ("Confidence:  ", {"bold": True}),
        ("93% NPV derived; 87% NPV cross-cohort.", {}),
    ])
    add_rich_para(doc, [
        ("Action:  ", {"bold": True}),
        ("Quality is good.  Move to standard review.", {}),
    ])

    # A4
    add_heading(doc, "A4.  No EEG Quality Concern  (sensitive version)",
                level=2, color=GREEN, size=14)
    add_rich_para(doc, [
        ("Condition:  ", {"bold": True}),
        ("Total OOB count < 4.", {}),
    ])
    add_rich_para(doc, [
        ("Confidence:  ", {"bold": True}),
        ("96% NPV derived; 95% NPV cross-cohort.  Catches ~93% of "
         "quality issues.", {}),
    ])

    add_para(doc, " ", space_after=4)
    add_callout_box(doc,
        "Practical tip:  A single Total OOB < 4 reading simultaneously "
        "clears A1 + A2 + A4 — clinical abnormality, paroxysmal events, "
        "and EEG quality concern, all at NPV 96–100%.  The simplest "
        "screening question to ask of a Brain Panel is:  Is Total OOB < 4?")

    # ===== SECTION B — RULE-IN =====
    add_page_break(doc)
    add_heading(doc, "Section B.  Rule-IN rules",
                level=1, color=ORANGE, size=22, space_before=0)
    add_para(doc,
             "When ANY of the conditions listed below is met on the Brain "
             "Panel report, the outcome is almost certainly present.",
             italic=True, color=GREY, size=11, space_after=10)

    # B1 — drowsiness  (combined-cohort honest values)
    add_heading(doc, "B1.  Drowsiness rule-in  (LIMITED — see note)",
                level=2, color=ORANGE, size=14)
    add_para(doc,
             "Combined-cohort baseline:  drowsiness prevalence is 55% (182 "
             "of 329 labelled EDFs).  Any flag with PPV ≤ 55% adds no "
             "information beyond the base rate.",
             italic=True, color=GREY, size=10, space_after=6)
    add_para(doc,
             "Only one flag clearly beats the prevalence baseline on the "
             "combined cohort:",
             bold=False, size=11)

    drow_rows = [
        ("XS Temp. Alpha",   "z ≤ −2", "65%",  "+10 pp"),
    ]
    add_simple_table(doc,
        header=["Metric", "Direction", "PPV (n=329)", "Lift over base rate"],
        rows=drow_rows,
        col_widths_in=[2.2, 1.4, 1.4, 1.6],
        header_fill="C86500",
        alt_fill="FFF3E0",
    )
    add_rich_para(doc, [
        ("Confidence:  ", {"bold": True}),
        ("When this flag fires, drowsiness is present 65% of the time — "
         "modestly above the 55% baseline.  This is the only direction-"
         "aware single-metric flag that survives the larger cross-cohort "
         "test.", {}),
    ], space_before=6)
    add_rich_para(doc, [
        ("Action:  ", {"bold": True}),
        ("Document as a drowsiness signal but acknowledge the modest lift "
         "over base rate.  Do NOT treat as a high-confidence call.", {}),
    ])
    add_para(doc,
             "DROPPED from this section after the 341-EDF combined-cohort "
             "test:  Diffuse Hibeta high (47% PPV), Diffuse Gamma high (47%), "
             "Diffuse Beta high (50%), Focal Delta Amp. low (55%), Delta "
             "Moment 1 high (47%), Focal Beta Index high (45%).  Each of "
             "these had PPV at or below the drowsiness prevalence rate, "
             "meaning the flag added no information.  Earlier cards "
             "overstated their PPV based on small derivation/validation "
             "cohorts.",
             italic=True, color=GREY, size=9, space_before=4)

    # B2 — artifact  (combined-cohort)
    add_heading(doc, "B2.  Moderate-or-Severe Artifact rule-in",
                level=2, color=ORANGE, size=14)
    add_para(doc,
             "Combined-cohort baseline:  moderate/severe artifact "
             "prevalence is 44% (48 of 108 labelled EDFs).  "
             "Note: artifact severity labels parse on only a subset of the "
             "cohort because the 2023+ doctor's template often leaves the "
             "field blank.",
             italic=True, color=GREY, size=10, space_after=6)
    add_para(doc,
             "Three flags clearly beat baseline:",
             bold=False, size=11)
    artf_rows = [
        ("PDR Moment 3",      "z ≤ −2", "100%", "+56 pp  (small-n: 3 hits)"),
        ("Focal Theta Index", "z ≤ −2",  "67%", "+23 pp"),
        ("Focal Beta Amp.",   "z ≥ +2",  "62%", "+18 pp"),
    ]
    add_simple_table(doc,
        header=["Metric", "Direction", "PPV (n=108)", "Lift over base rate"],
        rows=artf_rows,
        col_widths_in=[2.2, 1.4, 1.4, 1.6],
        header_fill="C86500",
        alt_fill="FFF3E0",
    )
    add_rich_para(doc, [
        ("Confidence:  ", {"bold": True}),
        ("PDR Moment 3 low has fired only 3 times in 108 labelled EDFs but "
         "all 3 were artifact-positive (100% PPV, very low sensitivity).  "
         "Focal Theta Index low and Focal Beta Amp. high are more often "
         "triggered (5-8 hits) with PPVs 62-67% — solid 'rule in' signals.", {}),
    ], space_before=6)
    add_rich_para(doc, [
        ("Action:  ", {"bold": True}),
        ("Document moderate/severe artifact when any of these flags fires.  "
         "May warrant re-acquisition note or technical caveat.", {}),
    ])

    # B3 — quality concern  (combined-cohort)
    add_heading(doc, "B3.  EEG Quality Concern rule-in",
                level=2, color=ORANGE, size=14)
    add_para(doc,
             "Combined-cohort baseline:  quality-concern prevalence is 15% "
             "(15 of 101 labelled EDFs).  Note: quality labels parse only "
             "where the 2022 doctor's-report template was used.",
             italic=True, color=GREY, size=10, space_after=6)
    add_rich_para(doc, [
        ("Condition:  ", {"bold": True}),
        ("PDR Max Post.  z-score ≥ +2.", {}),
    ])
    add_rich_para(doc, [
        ("Confidence:  ", {"bold": True}),
        ("33% PPV on the combined cohort — 2.2× the 15% base rate "
         "(+18 pp lift).  When this flag fires, the recording is "
         "twice as likely to be doctor-flagged Fair/Poor as average.", {}),
    ])
    add_rich_para(doc, [
        ("Action:  ", {"bold": True}),
        ("Flag for careful quality review.  Use Section A3/A4 (Total OOB "
         "or State Shift thresholds) as the primary quality signal — "
         "this single flag complements rather than replaces them.", {}),
    ])

    # B4 — clinical abnormality  (combined-cohort)
    add_heading(doc, "B4.  Clinical Abnormality rule-in  (LIMITED)",
                level=2, color=ORANGE, size=14)
    add_para(doc,
             "Combined-cohort baseline:  clinical-abnormality prevalence is "
             "8% (25 of 310 labelled EDFs).  At this prevalence, even high-"
             "specificity flags struggle to achieve high PPV.",
             italic=True, color=GREY, size=10, space_after=6)
    abn_rows = [
        ("PDR Symmetry",  "z ≤ −2", "22%", "+14 pp  (2.8× base rate)"),
    ]
    add_simple_table(doc,
        header=["Metric", "Direction", "PPV (n=310)", "Lift over base rate"],
        rows=abn_rows,
        col_widths_in=[2.2, 1.4, 1.4, 1.6],
        header_fill="C86500",
        alt_fill="FFF3E0",
    )
    add_rich_para(doc, [
        ("Action:  ", {"bold": True}),
        ("This flag adds weight to a neurologist review but does not "
         "constitute a confident call on its own.  Treat as a strong "
         "'look here' prompt rather than a verdict.", {}),
    ], space_before=6)
    add_para(doc,
             "DROPPED:  Frontal Delta high (12% PPV — at baseline), "
             "XS Temp. Alpha low (12% — at baseline).  These were "
             "previously listed at 33% / 20% based on smaller cohorts.",
             italic=True, color=GREY, size=9, space_before=4)

    # B5 — paroxysmal
    add_heading(doc, "B5.  Paroxysmal events", level=2, color=ORANGE, size=14)
    add_para(doc,
             "No usable rule-in flag at this cohort size.  Paroxysmal "
             "events were observed in only 10 of 244 labelled EDFs in the "
             "combined cross-cohort (~4% prevalence).  For paroxysmal "
             "events, rely on the rule-OUT (Section A2) alone.")

    # ===== SECTION C — DECISION FLOW =====
    add_page_break(doc)
    add_heading(doc, "Section C.  Per-recording decision procedure",
                level=1, color=NAVY, size=22, space_before=0)
    add_para(doc,
             "For each Brain Panel report, walk through this checklist in "
             "order.  Stop at the first step that fires.",
             italic=True, color=GREY, size=11, space_after=10)

    # Step 1
    add_heading(doc, "Step 1.  Read the Total OOB count", level=2, color=NAVY)
    add_para(doc, "Total OOB < 4:", bold=True, color=GREEN, space_before=4)
    add_bullet(doc, "Rule out clinical abnormality (96% NPV)", indent=0.5, color=GREEN)
    add_bullet(doc, "Rule out EEG quality concern (96% NPV)", indent=0.5, color=GREEN)
    add_bullet(doc, "If also Total OOB < 2, rule out paroxysmal events (100% NPV)", indent=0.5, color=GREEN)
    add_para(doc, "→  Route to fast review.  Stop.", bold=True, color=GREEN,
             space_before=2, space_after=10)

    add_para(doc, "Total OOB ≥ 4:", bold=True, color=ORANGE)
    add_para(doc, "→  Continue to Step 2.", bold=True, color=ORANGE,
             space_before=0, space_after=10)

    # Step 2
    add_heading(doc, "Step 2.  Check the rule-IN flags  (Section B)",
                level=2, color=NAVY)
    add_bullet(doc,
        "B1 (XS Temp. Alpha z ≤ −2) fires?  →  Drowsiness present "
        "(PPV 65%, +10 pp lift over base rate).  Document as a signal, "
        "not a confident call.", indent=0.3)
    add_bullet(doc,
        "Any B2 (artifact) flag fires?  →  Document moderate/severe "
        "artifact (PPV 62–100% combined cohort).  Consider technical note.",
        indent=0.3)
    add_bullet(doc,
        "B3 (PDR Max Post. ≥ +2) fires?  →  Possible Fair/Poor quality "
        "(PPV 33%, 2.2× base rate).  Careful review.", indent=0.3)
    add_bullet(doc,
        "B4 (PDR Symmetry ≤ −2) fires?  →  Possible abnormality "
        "(PPV 22%, 2.8× base rate of 8%).  Full neurologist read warranted.",
        indent=0.3)

    # Step 3
    add_heading(doc, "Step 3.  Middle band — no machine confidence",
                level=2, color=NAVY)
    add_para(doc,
             "Recording with Total OOB ≥ 4 but no rule-IN flags fired: "
             "the Brain Panel cannot make a confident call either way.  "
             "Full neurologist review.")

    # ===== SECTION D — SUMMARY TABLE =====
    add_page_break(doc)
    add_heading(doc, "Section D.  At-a-glance summary",
                level=1, color=NAVY, size=22, space_before=0)
    add_para(doc,
             "One row per clinical outcome.  Use this as the lookup table "
             "during routine reads.",
             italic=True, color=GREY, size=11, space_after=10)

    sum_header = ["Outcome", "Rule-OUT (absent)", "NPV",
                  "Rule-IN (present)", "PPV"]
    sum_rows = [
        ["Clinical Abnormality",
         "Total OOB < 4", "92%",
         "PDR Symmetry ≤ −2  (modest lift)", "22%"],
        ["Paroxysmal Events",
         "Total OOB < 2", "100%",
         "(none available)", "—"],
        ["EEG Quality Concern",
         "Total OOB < 4", "95%",
         "PDR Max Post. ≥ +2", "33%"],
        ["EEG Quality (strict)",
         "State Shift OOB = 0", "87%",
         "—", "—"],
        ["Drowsiness",
         "(rule-OUT unreliable — prevalence too high)", "—",
         "XS Temp. Alpha ≤ −2  (only flag that beats baseline)", "65%"],
        ["Artifact (Mod/Sev)",
         "(rule-OUT unreliable)", "—",
         "PDR Moment 3 ≤ −2 / Focal Theta Index ≤ −2 / Focal Beta Amp. ≥ +2", "62–100%"],
    ]
    add_simple_table(doc,
        header=sum_header,
        rows=sum_rows,
        col_widths_in=[1.6, 2.0, 0.6, 2.4, 0.6],
        header_fill="1F3A5F",
        alt_fill=LIGHT_GREY,
    )

    # ===== SECTION E — CAVEATS =====
    add_heading(doc, "Section E.  Important caveats",
                level=1, color=NAVY, size=22, space_before=12)
    cav = [
        ("These rules complement, not replace, neurologist review.  The "
         "Brain Panel is a screening tool; the neurologist owns the final "
         "read."),
        ("Drowsiness rule-OUT is structurally weak because drowsiness is "
         "highly prevalent (~60–65%) in clinical screening cohorts.  For "
         "drowsiness, rely on the rule-IN (Section B1) — a positive flag is "
         "high confidence, but a negative panel does NOT confidently rule "
         "out drowsiness."),
        ("Clinical abnormality and paroxysmal events are rare.  Rule-OUT "
         "works well by virtue of low prevalence; rule-IN is structurally "
         "weaker.  Full neurologist review remains essential when the "
         "rule-OUT condition is not met."),
        ("Section B PPVs are COMBINED-COHORT values (n=341 EDFs from two "
         "independent cohorts, all labelled by Dr. P. David Ims).  Flags "
         "with PPV at or below the outcome's prevalence in the cohort were "
         "DROPPED, since at-or-below-prevalence PPV means the flag adds no "
         "information.  Many flags that had high PPV in smaller cohorts "
         "(78-100%) collapsed to 47-65% on the larger combined cohort — "
         "this is the honest cross-cohort estimate."),
        ("PIPELINE VERSION DEPENDENCY: these rules apply to PDFs generated "
         "by the current (post-2026-06-12 bug-fix) Brain Panel pipeline.  "
         "Reports produced by older pipeline versions have different "
         "z-score distributions for STD Raw, Global STD, and the Moment-3 "
         "metrics, and these rules may not apply to those reports without "
         "re-derivation."),
        ("\"No call\" is informative.  If a recording sits in the gap "
         "(Total OOB ≥ 4, no rule-IN flag), the Brain Panel is explicitly "
         "admitting it cannot make a confident call.  This is a deliberate "
         "feature: the panel does not pretend to detect what it cannot."),
    ]
    for i, txt in enumerate(cav, 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.first_line_indent = Inches(-0.3)
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(f"{i}.  ")
        run.bold = True; run.font.color.rgb = NAVY
        run.font.name = "Calibri"; run.font.size = Pt(11)
        run = p.add_run(txt)
        run.font.name = "Calibri"; run.font.size = Pt(11)

    # ===== SECTION F — ONE-LINER PER OUTCOME =====
    add_page_break(doc)
    add_heading(doc, "Section F.  One-line summary per outcome",
                level=1, color=NAVY, size=22, space_before=0)
    add_para(doc,
             "If you have time for only one number per outcome, look at this.",
             italic=True, color=GREY, size=11, space_after=10)

    f_rows = [
        ["Drowsiness",
         "XS Temp. Alpha z ≤ −2.  Positive → drowsy (PPV 65%, modest lift "
         "over 55% base rate).  No flag gives high-confidence rule-in."],
        ["Artifact (Mod/Severe)",
         "PDR Moment 3 z ≤ −2.  Positive → artifact (PPV 100% but low "
         "sensitivity).  Focal Theta Index z ≤ −2 (PPV 67%) and Focal Beta "
         "Amp. z ≥ +2 (PPV 62%) are also useful rule-ins."],
        ["EEG Quality",
         "Total OOB count.  < 4 = good quality (95% NPV).  "
         "PDR Max Post. ≥ +2 → quality concern (PPV 33%)."],
        ["Clinical Abnormality",
         "Total OOB count.  < 4 rules it out (92% NPV).  "
         "PDR Symmetry z ≤ −2 → 22% PPV (2.8× base rate of 8%)."],
        ["Paroxysmal",
         "Total OOB count.  < 2 rules it out (100% NPV).  "
         "No rule confidently rules it in."],
    ]
    add_simple_table(doc,
        header=["Outcome", "The one thing to look at"],
        rows=f_rows,
        col_widths_in=[1.8, 5.4],
        header_fill="1F3A5F",
        alt_fill=LIGHT_GREY,
    )

    # ===== PRINTABLE CHECKLIST =====
    add_page_break(doc)
    add_heading(doc, "Per-recording checklist", level=1, color=NAVY,
                size=22, space_before=0)
    add_para(doc,
             "Print this page.  Fill out one per recording during review.",
             italic=True, color=GREY, size=11, space_after=14)

    # Patient header
    add_para(doc, "Patient ID:  ___________________________      "
             "Date:  ____________      Recording:  ____________",
             size=11, space_after=10)
    add_para(doc, "Reviewer:  ___________________________      "
             "Session type (EC / EO):  ____________",
             size=11, space_after=14)

    # STEP 1
    add_heading(doc, "Step 1.  Total OOB count from the Brain Panel report:  "
                "________",
                level=2, color=NAVY, size=14)
    add_para(doc, "Tick the appropriate row:", bold=True, space_after=6)
    add_checkbox_line(doc,
        "Total OOB < 4   →   Rule-OUT clinical abnormality, EEG quality "
        "concern, paroxysmal (if also <2).  Route to fast review.  STOP HERE.",
        indent=0.2, size=11)
    add_checkbox_line(doc,
        "Total OOB ≥ 4   →   Continue to Step 2.",
        indent=0.2, size=11)

    # STEP 2
    add_heading(doc, "Step 2.  Check rule-IN flags  (tick any that apply)",
                level=2, color=NAVY, size=14, space_before=14)
    add_para(doc, "Drowsiness  (only one flag has confirmed lift over base rate):",
             bold=True, space_after=4, space_before=4)
    add_checkbox_line(doc,
        "XS Temp. Alpha  (z ≤ −2)  →  PPV 65%  (vs 55% base rate)",
        indent=0.3, size=11)

    add_para(doc, "Artifact (Moderate/Severe)  (any one = useful rule-in):",
             bold=True, space_after=4, space_before=8)
    for metric, dir_, ppv in [
        ("PDR Moment 3",      "z ≤ −2", "100% (very low sens)"),
        ("Focal Theta Index", "z ≤ −2",  "67%"),
        ("Focal Beta Amp.",   "z ≥ +2",  "62%"),
    ]:
        add_checkbox_line(doc, f"{metric}  ({dir_})  →  PPV {ppv}",
                          indent=0.3, size=11)

    add_para(doc, "EEG Quality Concern  (modest):",
             bold=True, space_after=4, space_before=8)
    add_checkbox_line(doc,
        "PDR Max Post.  (z ≥ +2)  →  PPV 33%  (2.2× base rate of 15%)",
        indent=0.3, size=11)

    add_para(doc, "Clinical Abnormality  (modest):",
             bold=True, space_after=4, space_before=8)
    add_checkbox_line(doc,
        "PDR Symmetry  (z ≤ −2)  →  PPV 22%  (2.8× base rate of 8%)",
        indent=0.3, size=11)

    # Step 3 — disposition
    add_heading(doc, "Step 3.  Disposition  (tick one)",
                level=2, color=NAVY, size=14, space_before=14)
    add_checkbox_line(doc,
        "Fast review — cleared by Step 1.",
        indent=0.2, size=11, bold=False)
    add_checkbox_line(doc,
        "Confident positive call documented (Step 2 flag fired).  "
        "Findings:  _______________________________",
        indent=0.2, size=11, bold=False)
    add_checkbox_line(doc,
        "Full neurologist review — Total OOB ≥ 4 with no rule-IN flag.  "
        "Brain Panel cannot make a confident call.",
        indent=0.2, size=11, bold=False)

    add_para(doc, "Notes:", bold=True, space_before=14, space_after=4)
    for _ in range(4):
        add_para(doc, "  __________________________________________________"
                       "__________________________________________________",
                 size=11, space_after=10)

    # ----- footer with source provenance -----
    add_para(doc,
             "Derived from analyses in research/validation_2026/out/  "
             "(derive_rule_in_detectors.md, derive_rule_out_detectors.md, "
             "validate_rule_in_original_cohort.md, "
             "validate_rule_in_combined.md, check_pipeline_drift.py).  "
             "Derivation: 91-EDF subset of n=98 v2025_brainml cohort.  "
             "Cross-cohort validation: 100-EDF original study cohort + "
             "242 newly-processed EDFs from STS Q.A. Reviews tree "
             "(combined n=341, all labelled by Dr. P. David Ims).  "
             "All z-scores from the post-2026-06-12 bug-fix pipeline.",
             italic=True, color=GREY, size=8, space_before=14, space_after=0)

    # Save
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc.save(OUT)
    print(f"Wrote {OUT}  ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    build()
