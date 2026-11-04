---
name: document-summarizer
description: "Summarize documents, PDFs, articles, reports and long chats into key points, decisions and actions. Use when the user shares a file or text and wants the gist, an abstract or the main takeaways."
---
# Document summarizer

## Get the content
- Uploaded or attached file (PDF, Word, Excel, PowerPoint, text): call `read_document` with its path. For a document stored in the user's knowledge base, use `kb_search` and read the matching passages.
- Link: use `web_fetch`.
- Pasted text: use it directly.
- If extraction returns little or garbled text (scanned PDF), say so and ask for a text version instead of guessing.

## Long documents
Work in sections: read page ranges or chapters in turn, write a 2-3 line note per section, then merge. Never summarize something you have not actually read.

## Output (adapt length to the request; default is about 15% of the original)
1. **One-sentence gist**: what this document is and what it concludes.
2. **Key points**: 4-7 bullets, most important first. Keep numbers, dates, names and units exact.
3. **Decisions / conclusions** and **Open questions or risks** if the document has them.
4. **Actions** (owner, deadline) only when the text states them.
5. For reports: a short table of the main figures. For contracts or policies: obligations, deadlines, penalties, exit terms.

## Rules
- Separate facts from the author's opinions and say which is which.
- Quote a phrase only when the exact wording matters.
- Mention page or section for important claims when known, so the user can verify.
- If the user asks something specific ("what does it say about refunds?"), answer that first, then summarize.
- Offer next steps in one line: extract a table, translate, make slides (use the `presentation-builder` skill), or write a Word summary (`word-document-writer`).
