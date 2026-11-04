#!/usr/bin/env python3
"""Convert a CSV into a formatted .xlsx (bold frozen header, auto widths, numbers stored as numbers). Standard library only.

Usage: csv2xlsx.py input.csv output.xlsx [--sheet Name] [--total]
--total adds a SUM row under every numeric column.
"""
import csv
import sys
import zipfile
from xml.sax.saxutils import escape


def col(n):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def num(v):
    try:
        float(v)
        return v if v.strip() == v and not (len(v) > 1 and v.startswith("0") and v[1] != ".") else None
    except ValueError:
        return None


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) < 2:
        sys.exit(__doc__)
    sheet = sys.argv[sys.argv.index("--sheet") + 1] if "--sheet" in sys.argv else "Sheet1"
    raw = open(a[0], encoding="utf-8-sig", errors="replace", newline="").read()
    try:
        d = csv.Sniffer().sniff(raw[:20000], delimiters=",;\t|")
    except csv.Error:
        d = csv.excel
    rows = list(csv.reader(raw.splitlines(), d))
    width = max(len(r) for r in rows)
    numeric = [all(num(r[j]) is not None for r in rows[1:] if j < len(r) and r[j] != "") and any(j < len(r) and r[j] != "" for r in rows[1:]) for j in range(width)]
    xml_rows = []
    for i, r in enumerate(rows):
        cells = []
        for j in range(width):
            v = r[j] if j < len(r) else ""
            ref = f"{col(j)}{i + 1}"
            if i and numeric[j] and v != "":
                cells.append(f'<c r="{ref}"><v>{v}</v></c>')
            elif v != "":
                style = ' s="1"' if i == 0 else ""
                cells.append(f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{escape(v)}</t></is></c>')
        xml_rows.append(f'<row r="{i + 1}">{"".join(cells)}</row>')
    if "--total" in sys.argv and len(rows) > 1:
        n = len(rows) + 1
        cells = [f'<c r="A{n}" t="inlineStr" s="1"><is><t>Total</t></is></c>'] + [
            f'<c r="{col(j)}{n}" s="1"><f>SUM({col(j)}2:{col(j)}{len(rows)})</f></c>' for j in range(1, width) if numeric[j]]
        xml_rows.append(f'<row r="{n}">{"".join(cells)}</row>')
    widths = "".join(f'<col min="{j + 1}" max="{j + 1}" width="{min(60, max(8, max((len(r[j]) for r in rows if j < len(r)), default=8) + 2))}" customWidth="1"/>' for j in range(width))
    ws = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
          '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
          f'<cols>{widths}</cols><sheetData>{"".join(xml_rows)}</sheetData>'
          f'<autoFilter ref="A1:{col(width - 1)}{len(rows)}"/></worksheet>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
              '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE8EDF3"/></patternFill></fill></fills>'
              '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
              '<cellXfs count="2"><xf xfId="0"/><xf xfId="0" fontId="1" fillId="2" applyFont="1" applyFill="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    wb = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{escape(sheet[:31])}" sheetId="1" r:id="rId1"/></sheets></workbook>')
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
    rel = lambda t, tgt, i: f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{t}" Target="{tgt}"/>'
    R = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    with zipfile.ZipFile(a[1], "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", R + rel("officeDocument", "xl/workbook.xml", 1) + "</Relationships>")
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", R + rel("worksheet", "worksheets/sheet1.xml", 1) + rel("styles", "styles.xml", 2) + "</Relationships>")
        z.writestr("xl/worksheets/sheet1.xml", ws)
        z.writestr("xl/styles.xml", styles)
    print(f"Wrote {a[1]} ({len(rows) - 1} data rows, {width} columns)")


main()
