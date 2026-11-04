---
name: spreadsheet-helper
description: "Analyze CSV or Excel data, write Excel and Google Sheets formulas, clean messy data, and export formatted .xlsx files. Use for any spreadsheet, table or numbers question."
---
# Spreadsheet helper

## Understand the data first
- CSV/TSV file: run `python3 "{baseDir}/scripts/csv_profile.py" data.csv`. It prints row/column counts, types, missing values, min/max/mean/median, top values and duplicate rows. Base every statement on this output.
- Excel/other file: `read_document` to see the content. For a pasted table, work from the text.
- State what you found in plain words (3-6 bullets: size, quality problems, notable patterns or outliers) before drawing conclusions.

## Formulas
Ask which app (Excel or Google Sheets) if it matters. Give a **copy-ready formula**, one sentence on how it works, and an example result using the user's real cell references.
- Lookups: `XLOOKUP` (or `INDEX`/`MATCH` for older Excel). Sums/counts with conditions: `SUMIFS`, `COUNTIFS`, `AVERAGEIFS`.
- Dates: `TEXT`, `EOMONTH`, `NETWORKDAYS`. Text: `TRIM`, `TEXTSPLIT`/`SPLIT`, `TEXTJOIN`. Dynamic: `FILTER`, `UNIQUE`, `SORT`.
- For summaries by category recommend a PivotTable and list the exact fields for rows, columns and values.
- Error help: explain `#N/A`, `#VALUE!`, `#REF!`, `#DIV/0!` and the fix. Note locale differences (`;` instead of `,` in many regions).

## Cleaning
Trim spaces, unify dates and number formats, remove duplicates, split/merge columns, flag missing values. Never overwrite the original: write a cleaned copy and list every change you made.

## Export a clean .xlsx
`python3 "{baseDir}/scripts/csv2xlsx.py" in.csv out.xlsx --sheet "Data" --total` creates a workbook with a bold frozen header, filters, auto column widths, numbers stored as numbers and (with `--total`) live `SUM` formulas under numeric columns.

## Rules
Never guess numbers; recompute with the script or show the arithmetic. Say how many rows your conclusion is based on. Suggest a chart type when useful (bars to compare, lines over time, no pies beyond 5 slices).
