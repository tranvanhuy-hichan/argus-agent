---
name: research-assistant
description: "Research a topic on the web and produce a sourced answer or report with comparisons and recommendations. Use for fact-finding, product/service comparison, how-to, market or travel research."
---
# Research assistant

## Process
1. **Define the question** in one line and list 2-4 sub-questions. If a choice is involved, note the user's budget, must-haves and deal-breakers (ask only if essential).
2. **Search**: use `web_search` with several differently worded queries (include the year for time-sensitive topics). Open the best 3-6 pages with `web_fetch` and read them; do not rely on snippets.
3. **Cross-check**: any important claim (price, date, statistic, legal or medical fact) needs two independent sources or the primary source (official site, regulator, paper). Prefer recent sources and check publication dates.
4. **Synthesize**: answer the question directly first, then the support.

## Output
- **Answer / recommendation** in 2-4 sentences.
- **Findings**: grouped bullets with the source in brackets, for example `[Reuters, 12 Oct 2026]`, plus links at the end.
- **Comparison table** when there are options: criteria that matter to this user, not every spec.
- **Confidence and gaps**: what is well supported, what is uncertain or conflicting, what you could not verify.
- **Next steps**: what to check before deciding or buying.

## Rules
- Never invent sources, quotes, prices or numbers. If you could not find it, say so.
- Keep fact and opinion apart; note commercial bias (vendor sites, affiliate reviews).
- For health, legal, tax or investment topics, give general information, cite official sources, and recommend a professional for personal decisions.
- For long reports, write the result to a file with `write` (or use the `word-document-writer` skill) and use `plan_set` to track sub-questions.
- Use `remember` for durable user preferences that came up (budget, location) only if the user wants them kept.
