---
name: word-document-writer
description: "Create professional Word (.docx) documents: reports, letters, proposals, CVs, contracts drafts, from the user's content or an outline. Use when the user wants a Word file."
---
# Word document writer

## Workflow
1. Clarify only what is missing: purpose, audience, length, language, any required sections or company name. Otherwise proceed.
2. Draft the document in **Markdown** in a file (use the `write` tool), for example `report.md`:
   - `#` title (one only), `##` sections, `###` sub-sections
   - `-` bullets (indent two spaces for sub-bullets), `1.` numbered steps
   - `**bold**`, `*italic*`, `> quote`, and pipe tables with a header row
   - a line with `---` forces a page break
3. Convert: `python3 "{baseDir}/scripts/md2docx.py" report.md report.docx` (optional `--font "Times New Roman" --size 12`). Default is A4, Calibri 11, styled headings, shaded table headers.
4. Tell the user the file path. Offer to adjust and regenerate.

## Writing quality
- Open with the conclusion or purpose, then support it. Short paragraphs, descriptive headings.
- Reports: Summary → Background → Findings → Recommendations → Next steps.
- Letters and formal documents: sender/recipient block, date, subject line, body, sign-off. Leave `[placeholders]` for facts you do not know; never invent names, numbers or legal clauses.
- Proposals: problem, solution, scope, timeline, cost, terms.
- Contracts, legal and medical documents: produce a draft and state clearly that a qualified person should review it before use.

## Editing an existing .docx
Use `read_document` to read it, rewrite the content as Markdown, and regenerate. Say that complex original formatting (images, headers, tracked changes) will not carry over, and keep the original file untouched.

## Check
Re-read the Markdown for typos, consistent numbering and dates, and that every placeholder is listed to the user at the end.
