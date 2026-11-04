#!/usr/bin/env python3
"""Convert Markdown to a .docx file using only the standard library.

Usage: md2docx.py input.md output.docx [--font Calibri] [--size 11]
Supports: # ## ### headings, paragraphs, **bold**, *italic*, `code`, - / * bullets, 1. numbered lists,
> quotes, --- page break, and | pipe | tables.
"""
import re
import sys
import zipfile
from xml.sax.saxutils import escape


def runs(text, base=""):
    out = []
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)", text):
        if not part:
            continue
        props = base
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            part, props = part[2:-2], props + "<w:b/>"
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            part, props = part[1:-1], props + '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>'
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            part, props = part[1:-1], props + "<w:i/>"
        out.append(f'<w:r><w:rPr>{props}</w:rPr><w:t xml:space="preserve">{escape(part)}</w:t></w:r>')
    return "".join(out)


def para(text, style=None, ind=0, hanging=0, extra="", base=""):
    ppr = (f'<w:pStyle w:val="{style}"/>' if style else "")
    if ind:
        ppr += f'<w:ind w:left="{ind}" w:hanging="{hanging}"/>'
    return f"<w:p><w:pPr>{ppr}{extra}</w:pPr>{runs(text, base)}</w:p>"


def table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows if not re.match(r"^\s*\|?[\s:|-]+\|?\s*$", r)]
    if not cells:
        return ""
    n = max(len(r) for r in cells)
    border = "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="999999"/>' for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
    xml = f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>{border}</w:tblBorders><w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr>'
    for i, r in enumerate(cells):
        xml += "<w:tr>"
        for j in range(n):
            txt = r[j] if j < len(r) else ""
            shade = '<w:shd w:val="clear" w:color="auto" w:fill="E8EDF3"/>' if i == 0 else ""
            xml += f'<w:tc><w:tcPr>{shade}</w:tcPr>{para(txt, base="<w:b/>" if i == 0 else "")}</w:tc>'
        xml += "</w:tr>"
    return xml + "</w:tbl>" + para("")


def convert(md):
    body, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
        elif ln.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            body.append(table(block))
        else:
            i += 1
            m = re.match(r"^(#{1,3})\s+(.*)", ln)
            if m:
                body.append(para(m.group(2), f"Heading{len(m.group(1))}"))
            elif re.match(r"^\s*[-*]\s+", ln):
                depth = (len(ln) - len(ln.lstrip())) // 2
                body.append(para("• " + re.sub(r"^\s*[-*]\s+", "", ln), ind=360 + depth * 360, hanging=240))
            elif re.match(r"^\s*\d+[.)]\s+", ln):
                num = re.match(r"^\s*(\d+)[.)]\s+(.*)", ln)
                body.append(para(f"{num.group(1)}. {num.group(2)}", ind=420, hanging=300))
            elif ln.startswith(">"):
                body.append(para(ln.lstrip("> "), "Quote"))
            elif re.match(r"^(-{3,}|\*{3,})$", ln.strip()):
                body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
            else:
                body.append(para(ln.strip()))
    return "".join(body)


def build(md, out, font="Calibri", size=11):
    half = int(size * 2)
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    doc = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {ns}><w:body>{convert(md)}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr></w:body></w:document>'

    def hstyle(n, sz, color):
        return f'<w:style w:type="paragraph" w:styleId="Heading{n}"><w:name w:val="heading {n}"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="{300 - n * 40}" w:after="120"/></w:pPr><w:rPr><w:b/><w:color w:val="{color}"/><w:sz w:val="{sz}"/></w:rPr></w:style>'
    styles = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {ns}><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:eastAsia="{font}" w:cs="{font}"/><w:sz w:val="{half}"/></w:rPr></w:rPrDefault>'
              f'<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
              f'<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
              + hstyle(1, 36, "1F3864") + hstyle(2, 30, "2F5496") + hstyle(3, 26, "2F5496")
              + '<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="567"/></w:pPr><w:rPr><w:i/><w:color w:val="595959"/></w:rPr></w:style></w:styles>')
    ct = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'
    rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    drels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/_rels/document.xml.rels", drels)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    opt = {sys.argv[i]: sys.argv[i + 1] for i in range(1, len(sys.argv) - 1) if sys.argv[i].startswith("--")}
    if len(a) < 2:
        sys.exit(__doc__)
    build(open(a[0], encoding="utf-8").read(), a[1], opt.get("--font", "Calibri"), float(opt.get("--size", 11)))
    print(f"Wrote {a[1]}")
