"""Build the printable Quick Steps document for the 2026-09 server update.

Mirrors QUICK_STEPS.md in this folder. Rebuild after editing that file:

    py deploy/server-2026-09/build_quicksteps_docx.py
"""
import os

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "Quick Steps - Server Update 2026-09.docx")
BS = chr(92)   # backslash, kept out of string literals to avoid escaping noise

doc = Document()

sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
sec.left_margin = sec.right_margin = Inches(1)
sec.top_margin = sec.bottom_margin = Inches(0.8)

st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(11)
st.paragraph_format.space_after = Pt(5)

for lvl, size in ((1, 16), (2, 13)):
    h = doc.styles["Heading %d" % lvl]
    h.font.name = "Calibri"
    h.font.size = Pt(size)
    h.font.bold = True
    h.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    h.paragraph_format.space_before = Pt(14 if lvl == 1 else 10)
    h.paragraph_format.space_after = Pt(4)
    h.paragraph_format.keep_with_next = True


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def rich(parts, after=5, style=None, keep=False):
    """parts: list of (text, kind) with kind in {'', 'b', 'i', 'code'}."""
    p = doc.add_paragraph(style=style)
    for text, kind in parts:
        r = p.add_run(text)
        if kind == "b":
            r.bold = True
        elif kind == "i":
            r.italic = True
        elif kind == "code":
            r.font.name = "Consolas"
            r.font.size = Pt(10)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.keep_with_next = keep
    return p


def code_block(lines):
    """Shaded one-cell table of monospace lines -- prints cleanly."""
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.rows[0].cells[0]
    c.width = Inches(6.5)
    shade(c, "F2F2F2")
    c.paragraphs[0].text = ""
    first = True
    for ln in lines:
        p = c.paragraphs[0] if first else c.add_paragraph()
        first = False
        r = p.add_run(ln)
        r.font.name = "Consolas"
        r.font.size = Pt(10)
        p.paragraph_format.space_after = Pt(0)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def bullet(parts):
    p = rich(parts, after=3, style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.25)
    return p


def numbered(parts):
    return rich(parts, after=4, style="List Number")


def table(headers, rows, widths, code_col=0):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, txt, w in zip(t.rows[0].cells, headers, widths):
        c.width = w
        c.paragraphs[0].text = ""
        r = c.paragraphs[0].add_run(txt)
        r.bold = True
        shade(c, "D9E2F3")
    for row in rows:
        cells = t.add_row().cells
        for i, (c, txt, w) in enumerate(zip(cells, row, widths)):
            c.width = w
            c.paragraphs[0].text = ""
            r = c.paragraphs[0].add_run(txt)
            if i == code_col:
                r.font.name = "Consolas"
                r.font.size = Pt(9.5)
            c.paragraphs[0].paragraph_format.space_after = Pt(0)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


# ---- title -----------------------------------------------------------------
t = doc.add_paragraph()
r = t.add_run("STS EEG Screening Server Update")
r.bold, r.font.size = True, Pt(22)
r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
t.paragraph_format.space_after = Pt(0)

t2 = doc.add_paragraph()
r = t2.add_run("Global STD fix  +  image cascades   \u2014   September 2026")
r.font.size = Pt(13)
r.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
t2.paragraph_format.space_after = Pt(12)

rich([("Four steps on each server. Do the development server first; when its "
       "results look right, do production the same way. Everything is a file copy "
       "through your normal Remote Desktop session \u2014 no scripts required.", "")],
     after=6)
rich([("Each study is now processed in ", ""), ("two passes", "b"),
      (": the brain panel is written first, in seconds, and the image cascade "
       "follows over the next few minutes. The panel reaches the practitioner "
       "straight away, and a cascade failure can no longer destroy it.", "")],
     after=10)

# ---- what changes ----------------------------------------------------------
doc.add_heading("What this changes", level=1)
bullet([("Global STD ", "b"),
        ("on page 1 of every Brain Panel currently prints ", ""), ("1000.00", "code"),
        (" with z ", ""), ("2642.71", "code"),
        (". After the update it reads about ", ""), ("2.5", "code"),
        (", inside the normal range. No other metric moves \u2014 verified 47 of 48 "
         "identical against this server's own output.", "")])
bullet([("An image cascade ", "b"), ("(", ""), ("<study>.imagecascade.pdf", "code"),
        (", one page per ICA component) is written next to every panel, a few "
         "minutes after the panel itself.", "")])
bullet([("Disk: ", "b"),
        ("roughly 10\u201315 MB per study. 1,000 studies use about 15 GB of "
         "production's 100 GB free. The new watchdog warns below 10 GB.", "")])

# ---- files -----------------------------------------------------------------
doc.add_heading("The files", level=1)
rich([("On your workstation, open this folder in Explorer:", "")], after=4, keep=True)
code_block([("C:" + BS + "BrainPanel" + BS + "clean_eeg_project 2025" + BS +
             "deploy" + BS + "server-2026-09" + BS + "staged")])

files_dir = "project" + BS + "files" + BS
proj_dir = "project folder (next to module7.py)"
table(["File", "Goes into", "What it does"],
      [("files" + BS + "edftotextbynameplotproc.py", files_dir, "Global STD fix"),
       ("files" + BS + "edftotextbycommandplotproc.py", files_dir, "panel pass only"),
       ("files" + BS + "Montage_6.py", files_dir, "cascade rendering"),
       ("files" + BS + "dummy_gui.py", files_dir, "cascade component pages"),
       ("files" + BS + "Component_selector.py", files_dir, "same fixes, kept in sync"),
       ("files" + BS + "create_report_pdf.py", files_dir, "cascade screen capture"),
       ("run_cascade.py", proj_dir, "new \u2014 the cascade pass"),
       ("tomwatchdog_serialized.py", proj_dir, "new watchdog \u2014 one at a time")],
      (Inches(2.7), Inches(1.7), Inches(2.1)))

rich([("\u201cProject folder\u201d is the directory containing ", ""),
      ("module7.py", "code"), (". On the development server that is ", ""),
      ("C:" + BS + "app" + BS + "MyCleanEEG" + BS + "CleanEEGProject", "code"),
      (".", "")], after=8)

# ---- steps -----------------------------------------------------------------
doc.add_page_break()
doc.add_heading("On the server", level=1)
rich([("In your Remote Desktop session to the server.", "i")], after=6)

doc.add_heading("1.  Back up the six files being replaced", level=2)
rich([("In the project\u2019s ", ""), ("files" + BS, "code"),
      (" folder, make a new folder called ", ""), ("backup-2026-09", "code"),
      (" and copy these six files into it:", "")], after=4, keep=True)
code_block(["Component_selector.py", "Montage_6.py", "create_report_pdf.py",
            "dummy_gui.py", "edftotextbycommandplotproc.py",
            "edftotextbynameplotproc.py"])

doc.add_heading("2.  Paste the new files in", level=2)
bullet([("Copy the six ", ""), (".py", "code"), (" files from ", ""),
        ("staged" + BS + "files" + BS, "code"), (" into the project\u2019s ", ""),
        ("files" + BS, "code"), (" folder. Say ", ""), ("Yes", "b"),
        (" to overwrite.", "")])
bullet([("Copy ", ""), ("run_cascade.py", "code"), (" and ", ""),
        ("tomwatchdog_serialized.py", "code"),
        (" into the project folder itself, next to ", ""), ("module7.py", "code"),
        (".", "")])

doc.add_heading("3.  Swap the watchdog", level=2)
rich([("In the console window where ", ""), ("tomwatchdog.py", "code"),
      (" is running, press ", ""), ("Ctrl-C", "b"),
      (". Then, in that same window:", "")], after=4, keep=True)
code_block(["set CLEANEEG_NO_BRAIN=1"])
rich([("That switches off the 3D source-localization pages. ", ""),
      ("The servers need it", "b"),
      (" \u2014 those pages render through VTK, which needs OpenGL 3.2+, and the AWS "
       "machines have no graphics card. VTK does not report an error; it kills the "
       "process. Do not set it on a workstation that has a real graphics card.", "")],
     after=6)
rich([("Now start the new watchdog. ", ""), ("Development server:", "b")],
     after=2, keep=True)
code_block(['py tomwatchdog_serialized.py "c:/app/STSEEGScreening/Source/Practitioners"'])
rich([("Production server:", "b")], after=2, keep=True)
code_block(["py tomwatchdog_serialized.py"])
rich([("It prints ", ""), ("monitor dir:", "code"), (" and ", ""),
      ("interpreter:", "code"),
      (" first \u2014 glance at both. The production path is built in; the development "
       "server needs its own path given.", "")], after=4)
rich([("It must run in that console window \u2014 not as a service, not from a "
       "scheduled task. The cascade captures the screen, and only that session has "
       "one.", "b")], after=6)
rich([("Once a study has processed cleanly, make the variable permanent from an "
       "elevated prompt: ", ""), ("setx CLEANEEG_NO_BRAIN 1 /M", "code"), (".", "")],
     after=8)

doc.add_heading("4.  Upload one study and check the result", level=2)
rich([("The panel appears within seconds; the cascade follows. The console "
       "shows:", "")], after=4, keep=True)
code_block(["PROCESSING: ...  (queue depth 0, N GB free)",
            "  PANEL in 6s  rc=0",
            "[CLEANEEG_NO_BRAIN set: skipping 3D source-localization pages]",
            "CASCADE OK: ...imagecascade.pdf",
            "  CASCADE in 66s  rc=0",
            "  DONE in 73s  ..."])
rich([("Those timings are a short sample recording. A full-length study takes "
       "longer \u2014 the panel still in seconds, the cascade in minutes. Then check "
       "the files next to the EDF:", "")], after=4, keep=True)

chk = doc.add_table(rows=1, cols=3)
chk.style = "Table Grid"
chk.alignment = WD_TABLE_ALIGNMENT.CENTER
cw = (Inches(0.5), Inches(0.5), Inches(5.5))
for c, txt in zip(chk.rows[0].cells, ("Dev", "Prod", "Check")):
    c.paragraphs[0].text = ""
    r = c.paragraphs[0].add_run(txt)
    r.bold = True
    shade(c, "D9E2F3")
checks = [
    [(".icale.rep.pdf", "code"), (" \u2014 page 1, the ", ""), ("Global STD", "b"),
     (" row reads about ", ""), ("2.5", "b"), (", not 1000.", "")],
    [(".imagecascade.pdf", "code"),
     (" exists, appearing a few minutes after the panel.", "")],
    [("Open the cascade and page through it: component graphs on every page, ", ""),
     ("no black pages", "b"), (".", "")],
    [("Page 1 again: the four ", ""), ("Moment 3", "b"),
     (" rows are in the hundreds to low thousands.", "")],
]
for parts in checks:
    cells = chk.add_row().cells
    for c, w in zip(cells, cw):
        c.width = w
        c.paragraphs[0].text = ""
    for c in cells[:2]:
        r = c.paragraphs[0].add_run("\u2610")
        r.font.size = Pt(14)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = cells[2].paragraphs[0]
    for text, kind in parts:
        r = p.add_run(text)
        if kind == "b":
            r.bold = True
        elif kind == "code":
            r.font.name = "Consolas"
            r.font.size = Pt(10)
    p.paragraph_format.space_after = Pt(0)
for row in chk.rows[:-1]:
    for c in row.cells:
        for pp in c.paragraphs:
            pp.paragraph_format.keep_with_next = True
doc.add_paragraph().paragraph_format.space_after = Pt(2)

rich([("If the Moment 3 rows are in the ", ""), ("tens of thousands", "b"),
      (": that server has numpy 2.x. Also paste ", ""),
      ("staged-optional" + BS + "process" + BS + "detect_artifact.py", "code"),
      (" into the project\u2019s ", ""), ("process" + BS, "code"),
      (" folder and re-run the study. One-time check per server.", "")], after=6)
rich([("That is the whole deployment.", "b"),
      (" Production is the same four steps, starting the watchdog with no "
       "argument, in the console session kept logged in from the development "
       "server.", "")], after=8)

# ---- rollback --------------------------------------------------------------
doc.add_heading("If something is wrong", level=1)
numbered([("Copy the six files from ", ""), ("backup-2026-09", "code"),
          (" back into ", ""), ("files" + BS, "code"), (".", "")])
numbered([("Ctrl-C the new watchdog.", "")])
numbered([("Start the old one: ", ""), ("py tomwatchdog.py", "code"), ("", "")])
rich([("To keep the panel fix but stop cascades, set ", ""),
      ("CASCADE_PASS = False", "code"), (" near the top of ", ""),
      ("tomwatchdog_serialized.py", "code"),
      (" and restart it. Panels are unaffected.", "")], after=4)
rich([("Nothing in this update touches data files, the reference database, or any "
       "existing output, so rollback is a complete undo.", "")], after=8)

# ---- notes -----------------------------------------------------------------
doc.add_heading("Worth knowing", level=1)
bullet([("Why two passes: ", "b"),
        ("the cascade renders inside the same code that builds the panel, so in "
         "one pass the panel came last \u2014 and a cascade crash destroyed it, which "
         "is exactly what the OpenGL failure did on the dev server. Split in two, "
         "the panel is on disk before the cascade starts.", "")])
bullet([("Why the watchdog changes: ", "b"),
        ("the old one starts a new process for every upload with no limit. Two "
         "cascades rendering at once each capture the other\u2019s window, and the "
         "result is wrong with no error. The new one runs one study at a time, "
         "waits for an upload to finish writing, and kills anything past 25 "
         "minutes.", "")])
bullet([("Development server only: ", "b"),
        ("its screen is live only while you are connected. Stay connected while a "
         "cascade renders. Production is unaffected \u2014 its session is held by the "
         "console logged in from dev.", "")])
bullet([("Screen saver / lock screen: ", "b"),
        ("keep both off on any machine rendering cascades. A lock screen firing "
         "mid-render produces black pages.", "")])
bullet([("Older panels: ", "b"),
        ("every panel issued before this update carries the bogus Global STD row. "
         "Nothing else on them is wrong; their out-of-bounds count is one too "
         "high.", "")])
bullet([("Longer documents: ", "b"),
        ("README.md explains each change; MESA_OPENGL.md covers getting the 3D "
         "brain pages working on a server if you ever want them there.", "")])

fp = sec.footer.paragraphs[0]
fp.text = ("deploy" + BS + "server-2026-09" + BS + "Quick Steps  \u2014  "
           "built from production source, verified 2026-09-24")
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
for r in fp.runs:
    r.font.size = Pt(8)
    r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

doc.save(OUT)
print("wrote", OUT)
