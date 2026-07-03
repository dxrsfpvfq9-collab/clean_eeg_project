# -*- coding: utf-8 -*-
"""Minimal OOXML (.docx) generator supporting tracked changes.

Blocks are dicts; paragraphs carry "segs" = list of ("t"|"del"|"ins", text).
A plain string seg-list shorthand is allowed.
"""
import os, zipfile, html, datetime

AUTHOR = "Claude"
DATE = "2026-06-25T00:00:00Z"

_id = [0]
def nid():
    _id[0] += 1
    return _id[0]

def esc(t):
    return html.escape(t, quote=False)

def runs_from_segs(segs, rpr=""):
    """segs: str or list of (kind,text). Returns xml string of runs/ins/del."""
    if isinstance(segs, str):
        segs = [("t", segs)]
    out = []
    for kind, text in segs:
        if not text:
            continue
        t = esc(text)
        if kind == "t":
            out.append(f'<w:r>{rpr}<w:t xml:space="preserve">{t}</w:t></w:r>')
        elif kind == "ins":
            out.append(f'<w:ins w:id="{nid()}" w:author="{AUTHOR}" w:date="{DATE}">'
                       f'<w:r>{rpr}<w:t xml:space="preserve">{t}</w:t></w:r></w:ins>')
        elif kind == "del":
            out.append(f'<w:del w:id="{nid()}" w:author="{AUTHOR}" w:date="{DATE}">'
                       f'<w:r>{rpr}<w:delText xml:space="preserve">{t}</w:delText></w:r></w:del>')
    return "".join(out)

def para(segs, style=None, jc=None, rpr=""):
    ppr = "<w:pPr>"
    if style:
        ppr += f'<w:pStyle w:val="{style}"/>'
    if jc:
        ppr += f'<w:jc w:val="{jc}"/>'
    ppr += "</w:pPr>"
    if ppr == "<w:pPr></w:pPr>":
        ppr = ""
    return f"<w:p>{ppr}{runs_from_segs(segs, rpr)}</w:p>"

def heading(text, level):
    return para(text, style=f"Heading{level}")

def cell(content, w, shade=None, bold=False):
    rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
    shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>' if shade else ""
    body = runs_from_segs(content, rpr)
    if not body:
        body = "<w:r><w:t/></w:r>"
    return (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{shd}'
            f'<w:tcMar><w:top w:w="60" w:type="dxa"/><w:bottom w:w="60" w:type="dxa"/>'
            f'<w:left w:w="100" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tcMar>'
            f'</w:tcPr><w:p>{("<w:pPr><w:rPr><w:b/></w:rPr></w:pPr>" if bold else "")}{body}</w:p></w:tc>')

def table(rows, widths, header=True):
    border = ('<w:tblBorders>'
              + "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
                        for s in ("top","left","bottom","right","insideH","insideV"))
              + '</w:tblBorders>')
    total = sum(widths)
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{total}" w:type="dxa"/>{border}'
           f'<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>{grid}</w:tblGrid>']
    for ri, row in enumerate(rows):
        is_h = header and ri == 0
        shade = "D9E2F3" if is_h else None
        cells = "".join(cell(c, widths[ci], shade=shade, bold=is_h) for ci, c in enumerate(row))
        out.append(f'<w:tr>{cells}</w:tr>')
    out.append('</w:tbl>')
    # trailing empty paragraph required after table
    out.append('<w:p/>')
    return "".join(out)

def build(blocks, outpath, title="Document"):
    _id[0] = 0
    body = []
    for b in blocks:
        t = b["type"]
        if t == "title":
            body.append(para(b["text"], style="Title", jc="center"))
        elif t == "subtitle":
            body.append(para(b["text"], style="Subtitle", jc="center"))
        elif t == "heading":
            body.append(heading(b["text"], b["level"]))
        elif t == "para":
            body.append(para(b["segs"], jc=b.get("jc")))
        elif t == "caption":
            body.append(para(b["text"], style="Caption"))
        elif t == "bullet":
            body.append(f'<w:p><w:pPr><w:pStyle w:val="ListBullet"/><w:numPr>'
                        f'<w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
                        f'{runs_from_segs(b["segs"])}</w:p>')
        elif t == "table":
            body.append(table(b["rows"], b["widths"], b.get("header", True)))
        elif t == "spacer":
            body.append("<w:p/>")
    sect = ('<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
            '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
            'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>')
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f'<w:body>{"".join(body)}{sect}</w:body></w:document>')

    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="120" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="34"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="22"/><w:i/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="160" w:after="80"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:b/><w:i/><w:sz w:val="22"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/><w:rPr><w:i/><w:sz w:val="20"/><w:color w:val="404040"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="60"/></w:pPr></w:style>
</w:styles>'''

    numbering = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="&#x2022;"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>'''

    settings = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:zoom w:percent="100"/></w:settings>')

    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
        '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '</Types>')

    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '</Relationships>')

    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>'
        '</Relationships>')

    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dc:title>{esc(title)}</dc:title><dc:creator>Claude</dc:creator></cp:coreProperties>')

    with zipfile.ZipFile(outpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/numbering.xml", numbering)
        z.writestr("word/settings.xml", settings)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("docProps/core.xml", core)
    return outpath
