"""Render the 60 Hz line-noise survey as a shareable PDF.

Writes out/Line_Noise_60Hz_Survey.pdf. The bar charts are drawn here from
figures transcribed out of out/line_noise_summary.json -- re-run
line_noise_summary.py and update the literals below if the survey is re-run
over a different corpus. The four example spectra (fig_clean / fig_moderate /
fig_dominant / fig_alias .png, cropped page-3 rasters) are read from --figdir;
out/ is gitignored, so regenerate them before building on a fresh checkout.

    py line_noise_pdf.py [--figdir DIR]
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle, Image, KeepTogether,
                                HRFlowable)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

# ---------------------------------------------------------------- identity
INK      = colors.HexColor("#131A21")
INK2     = colors.HexColor("#3C4854")
MUTED    = colors.HexColor("#66727F")
RULE     = colors.HexColor("#D5DCE4")
RULE_STR = colors.HexColor("#B9C3CD")
SUNKEN   = colors.HexColor("#EEF1F5")
ACCENT   = colors.HexColor("#0D6A79")
ACC_SOFT = colors.HexColor("#DCECEF")
# Ordinal severity ramp, light -> dark: none, minor, moderate, severe, dominant.
SEVH = ["#8E9BAA", "#FB794A", "#D45624", "#A83903", "#722604"]

WF = r"C:\Windows\Fonts"
def _reg(name, fn):
    try:
        pdfmetrics.registerFont(TTFont(name, os.path.join(WF, fn)))
        return True
    except Exception:
        return False

HAVE = all([_reg("Body", "georgia.ttf"), _reg("Body-B", "georgiab.ttf"),
            _reg("Head", "arialbd.ttf"), _reg("Head-R", "arial.ttf"),
            _reg("Mono", "consola.ttf"), _reg("Mono-B", "consolab.ttf")])
if HAVE:
    F_BODY, F_BODYB = "Body", "Body-B"
    F_HEAD, F_HEADR = "Head", "Head-R"
    F_MONO, F_MONOB = "Mono", "Mono-B"
    pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-B",
                                  italic="Body", boldItalic="Body-B")
else:  # built-in fallback
    F_BODY, F_BODYB = "Times-Roman", "Times-Bold"
    F_HEAD, F_HEADR = "Helvetica-Bold", "Helvetica"
    F_MONO, F_MONOB = "Courier", "Courier-Bold"

S = {
    "h1": ParagraphStyle("h1", fontName=F_HEAD, fontSize=25, leading=28,
                         textColor=INK, spaceAfter=7),
    "sub": ParagraphStyle("sub", fontName=F_BODY, fontSize=11.5, leading=16.5,
                          textColor=INK2, spaceAfter=13),
    "eyebrow": ParagraphStyle("eyebrow", fontName=F_MONOB, fontSize=7.2,
                              leading=10, textColor=ACCENT, spaceAfter=4),
    "h2": ParagraphStyle("h2", fontName=F_HEAD, fontSize=14.5, leading=17.5,
                         textColor=INK, spaceBefore=2, spaceAfter=6),
    "h3": ParagraphStyle("h3", fontName=F_HEAD, fontSize=10.5, leading=13.5,
                         textColor=INK, spaceBefore=8, spaceAfter=4),
    "p": ParagraphStyle("p", fontName=F_BODY, fontSize=9.6, leading=14.4,
                        textColor=INK, spaceAfter=7, alignment=TA_LEFT),
    "li": ParagraphStyle("li", fontName=F_BODY, fontSize=9.6, leading=14.2,
                         textColor=INK, spaceAfter=4, leftIndent=13,
                         bulletIndent=3),
    "cap": ParagraphStyle("cap", fontName=F_BODY, fontSize=8.2, leading=11.8,
                          textColor=MUTED, spaceBefore=4, spaceAfter=9),
    "note": ParagraphStyle("note", fontName=F_BODY, fontSize=9.2, leading=13.6,
                           textColor=INK, spaceAfter=5),
    "meta": ParagraphStyle("meta", fontName=F_MONO, fontSize=7.6, leading=11.5,
                           textColor=MUTED, spaceAfter=11),
    "foot": ParagraphStyle("foot", fontName=F_MONO, fontSize=7.2, leading=11,
                           textColor=MUTED),
    "tileV": ParagraphStyle("tileV", fontName=F_HEAD, fontSize=19, leading=21,
                            textColor=INK),
    "tileL": ParagraphStyle("tileL", fontName=F_BODY, fontSize=7.6, leading=10.2,
                            textColor=INK2),
    "tileN": ParagraphStyle("tileN", fontName=F_MONO, fontSize=6.6, leading=9,
                            textColor=MUTED),
    "th": ParagraphStyle("th", fontName=F_MONOB, fontSize=6.6, leading=9,
                         textColor=MUTED),
    "td": ParagraphStyle("td", fontName=F_MONO, fontSize=7.6, leading=10.4,
                         textColor=INK2),
    "tdL": ParagraphStyle("tdL", fontName=F_MONO, fontSize=7.6, leading=10.4,
                          textColor=INK),
}

def P(t, s="p"): return Paragraph(t, S[s])
def LI(t): return Paragraph('<bullet>&bull;</bullet>' + t, S["li"])
def M(t): return '<font face="%s">%s</font>' % (F_MONO, t)
def B(t): return "<b>%s</b>" % t


# ---------------------------------------------------------------- charts
def _fig(w_in, h_in):
    fig, ax = plt.subplots(figsize=(w_in, h_in), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#B9C3CD")
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(length=0, labelsize=6.5, colors="#66727F")
    ax.grid(axis="y", color="#D5DCE4", linewidth=0.7)
    ax.set_axisbelow(True)
    return fig, ax


def _save(fig, name):
    p = os.path.join(OUT, "_pdf_" + name + ".png")
    fig.savefig(p, bbox_inches="tight", pad_inches=0.04, facecolor="white")
    plt.close(fig)
    return p


def chart_zhist():
    lab = ["-1 to 0", "0 to 1", "1 to 2", "2 to 3", "3 to 5", "5 to 10", "\u2265 10"]
    val = [538, 73, 35, 14, 12, 16, 14]
    col = [SEVH[0]] * 3 + [SEVH[1], SEVH[2], SEVH[3], SEVH[4]]
    fig, ax = _fig(6.4, 2.05)
    b = ax.bar(range(len(val)), val, color=col, width=0.66)
    for r, v in zip(b, val):
        ax.text(r.get_x() + r.get_width() / 2, v + 12, str(v), ha="center",
                fontsize=7, color="#131A21", fontweight="bold")
    ax.axvline(2.5, color="#0D6A79", lw=1.1, ls=(0, (3, 3)))
    ax.text(2.62, 470, "z = 2  out of bounds", fontsize=6.6, color="#0D6A79",
            fontweight="bold")
    ax.set_xticks(range(len(lab)))
    ax.set_xticklabels(lab)
    ax.set_ylim(0, 610)
    ax.set_ylabel("records", fontsize=6.8, color="#66727F")
    return _save(fig, "zhist")


def chart_sevbar():
    segs = [("None", 213), ("Minor", 226), ("Moderate", 202), ("Severe", 50), ("Dominant", 40)]
    tot = sum(v for _, v in segs)
    fig, ax = plt.subplots(figsize=(6.4, 0.92), dpi=200)
    fig.patch.set_facecolor("white")
    left = 0.0
    for i, (lb, v) in enumerate(segs):
        w = 100.0 * v / tot
        ax.barh(0, w - 0.28, left=left, height=0.82, color=SEVH[i])
        if w > 7:
            ax.text(left + w / 2, -0.68, "%.1f%%" % w, ha="center", fontsize=7,
                    color="#131A21", fontweight="bold")
            ax.text(left + w / 2, 0, lb, ha="center", va="center", fontsize=6.8,
                    color="white" if i in (0, 3, 4) else "#131A21", fontweight="bold")
        left += w
    ax.set_xlim(0, 100)
    ax.set_ylim(-1.15, 0.6)
    ax.axis("off")
    return _save(fig, "sevbar")


def chart_pcthist():
    lab = ["0-2", "2-5", "5-10", "10-20", "20-35", "35-50", "50-75", "75-100"]
    val = [36, 103, 87, 106, 62, 34, 31, 59]
    col = [SEVH[1]] * 3 + [SEVH[2]] * 3 + [SEVH[3], SEVH[4]]
    fig, ax = _fig(6.4, 2.05)
    b = ax.bar(range(len(val)), val, color=col, width=0.66)
    for r, v in zip(b, val):
        ax.text(r.get_x() + r.get_width() / 2, v + 2.4, str(v), ha="center",
                fontsize=7, color="#131A21", fontweight="bold")
    ax.set_xticks(range(len(lab)))
    ax.set_xticklabels(lab)
    ax.set_ylim(0, 128)
    ax.set_xlabel("60 Hz peak height as % of the record's dominant spectral peak",
                  fontsize=6.8, color="#66727F", labelpad=6)
    ax.set_ylabel("records", fontsize=6.8, color="#66727F")
    return _save(fig, "pcthist")


def chart_year():
    yrs = ["2022", "2023", "2024", "2025", "2026"]
    val = [61.7, 49.3, 39.1, 39.9, 23.2]
    ns = [60, 146, 179, 193, 138]
    fig, ax = _fig(6.4, 2.05)
    b = ax.bar(range(5), val, color=SEVH[2], width=0.52)
    for r, v, nn in zip(b, val, ns):
        ax.text(r.get_x() + r.get_width() / 2, v + 1.4, "%.1f%%" % v, ha="center",
                fontsize=7, color="#131A21", fontweight="bold")
        ax.text(r.get_x() + r.get_width() / 2, -5.2, "n=%d" % nn, ha="center",
                fontsize=6.2, color="#66727F")
    ax.set_xticks(range(5))
    ax.set_xticklabels(yrs)
    ax.set_ylim(0, 70)
    ax.set_ylabel("% moderate or worse", fontsize=6.8, color="#66727F")
    return _save(fig, "year")


def chart_ruler():
    fig, ax = plt.subplots(figsize=(6.4, 0.78), dpi=200)
    fig.patch.set_facecolor("white")
    ax.plot([0, 64], [0, 0], color="#B9C3CD", lw=1.0)
    for i in range(7):
        ax.plot([i * 10, i * 10], [0, -0.16], color="#B9C3CD", lw=1.0)
        ax.text(i * 10, -0.46, str(i * 10), ha="center", fontsize=6.4, color="#66727F")
    ax.text(65.5, -0.46, "Hz", ha="left", fontsize=6.4, color="#66727F")
    for f, c, t1, t2 in ((16, SEVH[2], "16 Hz", "240 Hz alias"),
                         (60, SEVH[4], "60 Hz", "mains")):
        ax.plot([f, f], [0, 0.62], color=c, lw=1.6)
        ax.text(f, 0.74, t1, ha="center", fontsize=7, color=c, fontweight="bold")
        ax.text(f, 1.10, t2, ha="center", fontsize=6.2, color="#66727F")
    ax.set_xlim(-2, 70)
    ax.set_ylim(-0.75, 1.45)
    ax.axis("off")
    return _save(fig, "ruler")


# ---------------------------------------------------------------- tables
def table(head, rows, widths, aligns=None, hl=None, colorcol=None):
    data = [[Paragraph(h, S["th"]) for h in head]]
    for r in rows:
        cells = []
        for j, c in enumerate(r):
            st = S["tdL"] if j == 0 else S["td"]
            if colorcol and j in colorcol and colorcol[j](r):
                c = '<font color="#722604"><b>%s</b></font>' % c
            cells.append(Paragraph(str(c), st))
        data.append(cells)
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    cmds = [
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, RULE_STR),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
    ]
    for j in range(1, len(head)):
        cmds.append(("ALIGN", (j, 0), (j, -1), "RIGHT"))
    for i in (hl or []):
        cmds.append(("BACKGROUND", (0, i + 1), (-1, i + 1), ACC_SOFT))
    t.setStyle(TableStyle(cmds))
    return t


def tiles():
    data = [[
        ([Paragraph('<font color="#8E9BAA">8.0%</font>', S["tileV"]),
                      Spacer(1, 2), P("flagged by the panel<br/>(Diffuse 60Hz z &ge; 2)", "tileL"),
                      Spacer(1, 1), P("56 / 702", "tileN")]),
        ([Paragraph('<font color="#D45624">70.9%</font>', S["tileV"]),
                      Spacer(1, 2), P("show a visible 60 Hz line in the page-3 spectrum", "tileL"),
                      Spacer(1, 1), P("518 / 731", "tileN")]),
        ([Paragraph('<font color="#A83903">39.9%</font>', S["tileV"]),
                      Spacer(1, 2), P("60 Hz reaches &ge;10% of the record's tallest peak", "tileL"),
                      Spacer(1, 1), P("292 / 731", "tileN")]),
        ([Paragraph('<font color="#722604">5.5%</font>', S["tileV"]),
                      Spacer(1, 2), P("60 Hz <i>is</i> the tallest peak in the spectrum", "tileL"),
                      Spacer(1, 1), P("40 / 731", "tileN")]),
    ]]
    w = 6.9 * inch / 4
    t = Table(data, colWidths=[w] * 4, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, RULE),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def note(title, paras):
    inner = [Paragraph(B(title), S["note"])] + [Paragraph(t, S["note"]) for t in paras]
    t = Table([[inner]], colWidths=[6.9 * inch], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SUNKEN),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
    ]))
    return t


def figure(path, width, caption=None):
    from PIL import Image as PILImage
    w, h = PILImage.open(path).size
    im = Image(path, width=width, height=width * h / w)
    im.hAlign = "LEFT"
    out = [Spacer(1, 5), im]
    if caption:
        out.append(P(caption, "cap"))
    else:
        out.append(Spacer(1, 9))
    return out


def spectra_row(figdir):
    items, caps = [], []
    spec = [("clean", "None", "Peak ratio 1.0 &middot; 0.3% of dominant peak &middot; panel z &minus;0.75"),
            ("moderate", "Moderate", "Peak ratio 27.9 &middot; 25% of dominant peak &middot; panel z 1.35"),
            ("dominant", "Dominant", "Peak ratio 84.7 &middot; tallest peak in the spectrum &middot; panel z 0.16")]
    from PIL import Image as PILImage
    cw = 6.9 * inch / 3 - 8
    for i, (tag, lb, cap) in enumerate(spec):
        p = os.path.join(figdir, "fig_%s.png" % tag)
        w, h = PILImage.open(p).size
        im = Image(p, width=cw, height=cw * h / w)
        col = ["#8E9BAA", "#D45624", "#722604"][i]
        items.append([Paragraph('<font color="%s"><b>%s</b></font>' % (col, lb), S["h3"]),
                      im, Paragraph(cap, S["cap"])])
    t = Table([items], colWidths=[6.9 * inch / 3] * 3, hAlign="LEFT")
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    return t


# ---------------------------------------------------------------- document
def header_footer(canvas, doc):
    canvas.saveState()
    w, h = LETTER
    canvas.setFont(F_MONO, 6.8)
    canvas.setFillColor(MUTED)
    if doc.page > 1:
        canvas.drawString(0.8 * inch, h - 0.52 * inch,
                          "60 Hz LINE-NOISE SURVEY  \u00b7  BRAIN PANEL REPORT ARCHIVE")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(0.8 * inch, h - 0.62 * inch, w - 0.8 * inch, h - 0.62 * inch)
    canvas.drawRightString(w - 0.8 * inch, 0.5 * inch, "%d" % doc.page)
    canvas.drawString(0.8 * inch, 0.5 * inch,
                      "Stress Therapy Solutions  \u00b7  research/validation_2026")
    canvas.restoreState()


def build(figdir):
    path = os.path.join(OUT, "Line_Noise_60Hz_Survey.pdf")
    doc = BaseDocTemplate(path, pagesize=LETTER,
                          leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                          topMargin=0.78 * inch, bottomMargin=0.75 * inch,
                          title="60 Hz Line-Noise Survey of the Brain Panel Report Archive",
                          author="Stress Therapy Solutions", subject="EEG quality assurance")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=header_footer)])

    zh, sb, ph, yr, ru = chart_zhist(), chart_sevbar(), chart_pcthist(), chart_year(), chart_ruler()
    W = 6.9 * inch
    E = []

    # ---- masthead
    E += [P("BRAIN PANEL ARCHIVE \u00b7 LINE-NOISE SURVEY", "eyebrow"),
          P("Mains Hum in the Panel Archive", "h1"),
          P("Every " + M(".icale.rep.pdf") + " on file, measured two ways: the " + B("Diffuse 60Hz")
            + " row on page 1, and the actual height of the 60 Hz and 16 Hz peaks in the page 3 "
              "spectrum. The two disagree, and the direction of the disagreement matters.", "sub"),
          P("932 report PDFs&nbsp;&nbsp;\u00b7&nbsp;&nbsp;843 unique recordings&nbsp;&nbsp;\u00b7&nbsp;&nbsp;"
            "2022&ndash;2026 Q.A. review folders&nbsp;&nbsp;\u00b7&nbsp;&nbsp;731 with a readable spectrum"
            "&nbsp;&nbsp;\u00b7&nbsp;&nbsp;702 with EC_191 z-scores", "meta"),
          tiles(), Spacer(1, 16)]

    # ---- what was measured
    E += [P("THE TWO FREQUENCIES", "eyebrow"), P("What was measured, and where", "h2"),
          P(B("60 Hz") + " is the mains fundamental &mdash; it sits below the 128 Hz Nyquist limit and "
            "appears in the spectrum where you would expect it. " + B("16 Hz") + " is not a brain rhythm "
            "at all: it is where the <i>fourth</i> harmonic at 240 Hz lands after aliasing, since "
            "|240 &minus; 256| = 16. A peak there is evidence that energy well above the anti-alias "
            "corner is reaching the converter.")]
    E += figure(ru, W, "The page-3 display spans 0&ndash;64 Hz. Across the 518 records with a detectable "
                       "line, the measured mains peak sits at a median of <b>59.91 Hz</b> (5th&ndash;95th "
                       "percentile 59.82&ndash;59.98) and is <b>0.53 Hz</b> wide at half height &mdash; a "
                       "pure tone, not a physiological band.")

    # ---- page 1
    E += [Spacer(1, 4), P("PAGE 1 \u00b7 THE PANEL METRIC", "eyebrow"),
          P("Diffuse 60Hz flags 8% of records", "h2"),
          P("Tabulating the " + M("Diffuse 60Hz") + " row across the 702 reports scored against the "
            "EC_191 / 192-file database:"),
          KeepTogether(table(["THRESHOLD", "RECORDS", "SHARE", "READING"],
                [["z &ge; 1", "91", "13.0%", "above typical"],
                 ["z &ge; 1.5", "72", "10.3%", "approaching range"],
                 ["z &ge; 2", "56", "8.0%", "out of bounds &mdash; the report's own flag"],
                 ["z &ge; 3", "42", "6.0%", "clearly excessive"],
                 ["z &ge; 5", "30", "4.3%", "extreme"],
                 ["z &ge; 10", "14", "2.0%", "see the gain caveat below"]],
                [1.15 * inch, 0.95 * inch, 0.9 * inch, 3.9 * inch], hl=[2])),
          Spacer(1, 6)]
    E += figure(zh, W, "Distribution of the <b>Diffuse 60Hz</b> z-score. 77% of all records sit between "
                       "z = &minus;1 and 0 &mdash; <i>below</i> the database mean. The out-of-bounds line "
                       "at z = 2 is reached by only 56 records.")
    E += [P("Why the flag is so hard to trip", "h3"),
          P("On a current report the row reads " + M("Typ 37.03") + " with a normal range of "
            + M("&minus;57.99 to 132.05") + ". That range is symmetric about the mean and runs deep into "
            "negative territory for a quantity that cannot be negative &mdash; the signature of a reference "
            "distribution with a long right tail and a standard deviation of roughly <b>47.5</b>. The "
            "EC_191 database was built from 192 real recordings, and those recordings carry line noise too."),
          P("The practical consequence: a record needs an absolute 60 Hz band amplitude above 132 before "
            "the panel calls it abnormal. The median record measures <b>10.4</b>; the 90th percentile is "
            "<b>109.3</b>.")]

    # ---- page 3
    E += [Spacer(1, 10), P("PAGE 3 \u00b7 THE SPECTRUM", "eyebrow"),
          P("The spectrum tells a different story", "h2"),
          P("Reading the peak heights straight off the page-3 plot gives a much more sensitive picture. "
            "Records are graded by how tall the 60 Hz line stands relative to the record's own dominant "
            "rhythm &mdash; the alpha peak, in most cases.")]
    E += figure(sb, W)
    E += [KeepTogether(table(["BAND", "DEFINITION", "RECORDS", "SHARE"],
                [["None", "no line \u2265 2\u00d7 the local spectral floor", "213", "29.1%"],
                 ["Minor", "present, &lt; 10% of dominant peak", "226", "30.9%"],
                 ["Moderate", "10&ndash;50% of dominant peak", "202", "27.6%"],
                 ["Severe", "50&ndash;99%", "50", "6.8%"],
                 ["Dominant", "60 Hz <b>is</b> the tallest peak", "40", "5.5%"]],
                [1.0 * inch, 3.5 * inch, 1.1 * inch, 1.3 * inch], hl=[2, 3, 4])),
          Spacer(1, 8)]
    E += figure(ph, W, "Among the 518 records with a detectable line, how tall it gets. The distribution "
                       "is bimodal: most contamination is small, but <b>59 records</b> reach 75% or more "
                       "of the record's dominant rhythm.")
    E += [spectra_row(figdir), Spacer(1, 6)]

    # ---- disagreement
    E += [P("THE DISAGREEMENT", "eyebrow"), P("Why the two measures diverge", "h2"),
          P("They are not measuring the same thing, and the difference is in the code rather than in the "
            "statistics."),
          LI("The panel metric is built from " + M("mysigs") + " &mdash; the <b>raw, un-normalised</b> "
             "signal through a 55&ndash;65 Hz band-pass. It reports mains amplitude in absolute terms."),
          LI("The page-3 spectrum is built from " + M("myvisualsigs") + ", which is <b>RMS-normalised to "
             "std = 10</b> before the FFT. It reports mains amplitude <i>relative to the brain signal it "
             "is competing with</i>."),
          Spacer(1, 3),
          P("For judging whether a recording is still readable, the relative measure is the one that "
            "matters &mdash; and it is the one the panel does not report."),
          KeepTogether(table(["CROSS-TABULATION (n = 701)", "RECORDS", "SHARE"],
                [["Flagged by panel only", "13", "1.9%"],
                 ["Moderate-or-worse in spectrum, <b>not</b> flagged", "233", "33.2%"],
                 ["Both agree", "42", "6.0%"],
                 ["Neither", "413", "58.9%"]],
                [4.0 * inch, 1.4 * inch, 1.5 * inch], hl=[1])),
          Spacer(1, 10),
          note("The z &ge; 10 group is a gain artefact, not worse hum.",
               ["The 14 records with z &ge; 10 have a median " + M("STD Raw") + " of <b>678.8</b> against "
                "<b>36.9</b> for everyone else &mdash; roughly 17&times; the normal recording amplitude. "
                "Their " + M("Diffuse 60Hz") + " value is high (median 926 vs 10) largely because "
                "<i>everything</i> in those files is high. Relative to their own signal the 60 Hz fraction "
                "is elevated about 8-fold, which is real, but the extreme z-scores overstate it. Because "
                "the metric is absolute, it partly tracks amplifier gain and unit conventions."]),
          Spacer(1, 12)]

    # ---- worst offenders
    worst = [["CB1963 \u00b7\u00b7\u00b7 AGE 61 EC", "119.8&times;", "100%", "2.11", "flagged"],
             ["raw_615043", "101.6&times;", "100%", "10.72", "flagged"],
             ["62034 \u00b7\u00b7\u00b7 AGE 23 EC", "99.8&times;", "100%", "11.85", "flagged"],
             ["1119 \u00b7\u00b7\u00b7 AGE 58 EC", "93.3&times;", "100%", "0.40", "within limits"],
             ["1119 \u00b7\u00b7\u00b7 AGE 58 EC (dup)", "93.3&times;", "100%", "0.40", "within limits"],
             ["jpde0004 \u00b7\u00b7\u00b7 AGE 42 EC", "84.7&times;", "100%", "0.16", "within limits"],
             ["0048 \u00b7\u00b7\u00b7 AGE 14 EC", "81.9&times;", "100%", "6.12", "flagged"],
             ["raw_619620", "80.2&times;", "100%", "0.33", "within limits"],
             ["001 \u00b7\u00b7\u00b7 61216 EC", "79.4&times;", "100%", "8.29", "flagged"],
             ["RM0013LG \u00b7\u00b7\u00b7 AGE 56 EC", "76.3&times;", "100%", "&minus;0.05", "within limits"],
             ["Jo0440 \u00b7\u00b7\u00b7 AGE 70 EC", "74.2&times;", "100%", "7.54", "flagged"],
             ["SJLA00001 \u00b7\u00b7\u00b7 AGE 62 EC", "72.9&times;", "100%", "0.24", "within limits"]]
    E += [P("Worst offenders by spectral height", "h3"),
          P("The twelve records where 60 Hz dominates most decisively. Patient identifiers are redacted "
            "here; full filenames are in " + M("out/line_noise_survey.csv") + "."),
          table(["RECORD", "PEAK RATIO", "% OF DOMINANT PEAK", "PANEL z", "PANEL VERDICT"],
                worst, [2.35 * inch, 0.95 * inch, 1.45 * inch, 0.8 * inch, 1.35 * inch],
                colorcol={4: lambda r: r[4] == "within limits"}),
          P("Eight of these twelve are reported as within normal limits on page 1.", "cap"),
          Spacer(1, 8)]

    # ---- 16 Hz
    E += [P("16 Hz \u00b7 THE 240 Hz ALIAS", "eyebrow"),
          P("The subharmonic is real but rare", "h2"),
          P("A narrow line near 16 Hz shows up in a small minority of records, and where it appears it "
            "looks exactly like an alias should: sharp, and sitting on top of ordinary beta rather than "
            "shaping it."),
          KeepTogether(table(["16 Hz PROMINENCE", "RECORDS", "SHARE", "OF THOSE, NARROW (&lt;1.2 Hz WIDE)"],
                [["&ge; 1.5&times; local floor", "26", "3.6%", "19"],
                 ["&ge; 2&times;", "10", "1.4%", "7"],
                 ["&ge; 3&times;", "3", "0.4%", "3"],
                 ["&ge; 5&times;", "1", "0.1%", "1"]],
                [1.75 * inch, 1.0 * inch, 0.95 * inch, 3.2 * inch], hl=[1])),
          Spacer(1, 10)]

    from PIL import Image as PILImage
    ap = os.path.join(figdir, "fig_alias.png")
    aw, ah = PILImage.open(ap).size
    iw = 2.5 * inch
    aimg = Image(ap, width=iw, height=iw * ah / aw)
    side = [Paragraph('<font color="#D45624"><b>Strongest 16 Hz case</b></font>', S["h3"]),
            P("The tall narrow line left of centre sits at <b>15.74 Hz</b> and is <b>0.53 Hz</b> wide "
              "&mdash; 5.7&times; the surrounding beta floor. The same record carries a 60 Hz peak "
              "40.6&times; its floor. Panel z for " + M("Diffuse 60Hz") + ": <b>0.69</b>.", "note"),
            P("Across all 10 detections the alias lands between <b>15.74</b> and <b>16.42 Hz</b>, median "
              "<b>15.96</b>, median width <b>0.68 Hz</b>. That is squarely where a 240 Hz tone folds back "
              "&mdash; the small offset below 16.0 implies a source near 240.2 Hz or a sample clock a "
              "fraction under 256 S/s.", "note")]
    at = Table([[aimg, side]], colWidths=[2.6 * inch, 4.3 * inch], hAlign="LEFT")
    at.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (0, 0), 0),
                            ("LEFTPADDING", (1, 0), (1, 0), 12),
                            ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    E += [at, Spacer(1, 10),
          P(B("It travels with heavy mains, but is not a general companion to it.") + " Rank correlation "
            "between the 16 Hz and 60 Hz prominences across all 731 records is essentially zero. Yet among "
            "the 10 records with a real 16 Hz line, <b>70%</b> also carry a 60 Hz peak at 10&times; the "
            "floor or more, against a base rate of 36.5%, and their median 60 Hz prominence is 12.1&times; "
            "versus 5.7&times; elsewhere. So the alias marks a specific equipment or environment failure "
            "that happens on top of heavy line noise &mdash; not something that scales with it.")]

    alias = [["upload_dublei \u00b7\u00b7\u00b7 AGE 14 EC", "5.70&times;", "15.74", "0.53", "40.6&times;", "0.69"],
             ["1277 \u00b7\u00b7\u00b7 AGE 52 EC", "4.76&times;", "15.96", "0.61", "10.8&times;", "0.61"],
             ["1277 \u00b7\u00b7\u00b7 AGE 52 EC (dup)", "4.76&times;", "15.96", "0.61", "10.8&times;", "0.61"],
             ["1414 \u00b7\u00b7\u00b7 AGE 66 EC", "2.84&times;", "15.89", "1.44", "1.0&times;", "1.82"],
             ["raw_619620", "2.66&times;", "15.89", "0.53", "80.2&times;", "0.33"],
             ["1238 \u00b7\u00b7\u00b7 AGE 50 EC", "2.50&times;", "15.74", "1.44", "13.5&times;", "0.81"],
             ["1339 \u00b7\u00b7\u00b7 AGE 8 EC", "2.08&times;", "16.42", "0.76", "8.3&times;", "0.14"],
             ["TBNY00004 \u00b7\u00b7\u00b7 AGE 23 EC", "2.04&times;", "15.96", "1.06", "4.4&times;", "&minus;0.74"],
             ["JPDE0001 \u00b7\u00b7\u00b7 AGE 36 EC", "2.04&times;", "16.27", "0.38", "16.9&times;", "&minus;0.66"],
             ["Jo0429_1201 \u00b7\u00b7\u00b7 AGE 46 EC", "2.02&times;", "15.96", "2.34", "14.2&times;", "1.72"]]
    E += [Spacer(1, 4),
          table(["RECORD", "16 Hz RATIO", "PEAK (Hz)", "WIDTH (Hz)", "60 Hz RATIO", "PANEL z"],
                alias, [2.35 * inch, 0.95 * inch, 0.85 * inch, 0.9 * inch, 0.95 * inch, 0.9 * inch],
                hl=[0, 1, 2]),
          Spacer(1, 14)]

    # ---- trend
    E += [P("TREND", "eyebrow"), P("It has been getting better", "h2"),
          P("Grouping by the year of the Q.A. review folder, the share of recordings with "
            "moderate-or-worse contamination has fallen by roughly two thirds since 2022.")]
    E += figure(yr, W, "Median 60 Hz height as a share of the dominant peak fell alongside it: "
                       "<b>15.7% \u2192 9.6% \u2192 6.6% \u2192 6.4% \u2192 3.4%</b> from 2022 to 2026. "
                       "The 2026 folders are partial-year.")

    # ---- method
    E += [Spacer(1, 4), P("METHOD", "eyebrow"), P("How the peaks were recovered", "h2"),
          P("The page-3 FFT panel is stored inside each PDF as a 1200&times;1500 PNG, so the original "
            "raster was extracted losslessly and the curves measured directly in pixels. The plot has no "
            "drawn axes, but its geometry is fully determined by the report generator:"),
          LI("<b>Frequency.</b> Seven tick marks at 0, 10 &hellip; 60 Hz give the x scale by least squares. "
             "It came out identical on every file &mdash; the axis line is 847 px long in all 731."),
          LI("<b>Amplitude.</b> Matplotlib's default subplot box and 5% autoscale margin put the data value "
             "&minus;950 at pixel row 1282.5 regardless of amplitude scale (measured 1282&ndash;1283 "
             "everywhere). The axis line, drawn 30 units above it, then fixes the scale."),
          LI("<b>Separation.</b> Curves are separated from the channel legend by connected-component width "
             "&mdash; the spectra span the plot, glyphs do not. Raising the width threshold from 150 px to "
             "500 px changed nothing on a 180-file check."),
          Spacer(1, 3),
          P(B("Validation.") + " Each report's page-3 paragraph states the posterior alpha amplitude it "
            "computed internally. Measuring the spectrum's global maximum and applying the report's own "
            "conversion reproduces that number to within 1% across a 230-file sample (worst case "
            "0.989&times;; 40% land exactly on it, being the same peak). The amplitude calibration is sound."),
          Spacer(1, 6),
          note("Two caveats on the numbers above.",
               [B("The displayed 60 Hz peak understates reality.") + " " + M("myvisualsigs") + " is "
                "band-passed 1.5&ndash;45 Hz before the FFT, and a single-pass 4-pole is only about "
                "&minus;10 dB at 60 Hz. True mains amplitude is roughly three times what the plot shows. "
                "The 16 Hz alias sits inside the pass-band and is shown at full strength.",
                B("Page-3 amplitudes are relative.") + " Because the signal is RMS-normalised to std = 10 "
                "before the FFT, &ldquo;% of dominant peak&rdquo; compares mains against that record's own "
                "brain signal. It is the right measure for readability and the wrong one for absolute "
                "field strength."]),
          Spacer(1, 10),
          P("Coverage", "h3"),
          P("Of 932 PDFs, 843 are unique by filename. 106 are legacy 2013-format Auto Scan reports with no "
            "z-scores and no embedded plots; 35 were scored against a different reference database. That "
            "leaves <b>702</b> for the page-1 tabulation and <b>731</b> for the spectral measurements. A "
            "handful of recordings appear twice under slightly different filenames and survive filename "
            "de-duplication &mdash; " + M("1119") + " and " + M("1277") + " are visible in the tables "
            "above. ICA has no random seed, so re-running the same EDF gives slightly different panel "
            "values; 36 of the 76 duplicate-filename groups differ in " + M("d60_z") + "."),
          Spacer(1, 12),
          HRFlowable(width="100%", thickness=0.5, color=RULE, spaceAfter=8),
          P("Source: 932 " + M(".icale.rep.pdf") + " reports under "
            + M("STS EEG Quality Assurance Reviews") + ".<br/>"
            "Per-record data: " + M("research/validation_2026/out/line_noise_survey.csv")
            + " &nbsp;\u00b7&nbsp; summary: " + M("line_noise_summary.json") + "<br/>"
            "Scripts: " + M("line_noise_survey.py") + ", " + M("line_noise_summary.py") + ", "
            + M("line_noise_pdf.py"), "foot")]

    doc.build(E)
    for f in (zh, sb, ph, yr, ru):
        try:
            os.remove(f)
        except OSError:
            pass
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--figdir", default=OUT)
    a = ap.parse_args()
    p = build(a.figdir)
    print("wrote", p, round(os.path.getsize(p) / 1024), "KB")
