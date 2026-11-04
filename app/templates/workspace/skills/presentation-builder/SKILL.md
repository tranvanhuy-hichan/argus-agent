---
name: presentation-builder
description: "Build presentations: story outline, slide-by-slide content, speaker notes, and a ready HTML slide deck that also prints to PDF. Use for talks, pitches, reports, lessons."
---
# Presentation builder

## Plan the story first
Ask (once) for: audience, goal (inform, persuade, decide, teach), time (about 2 minutes per slide), and source material. Use `read_document` or `kb_search` for source files, and `web_search` for missing facts, citing sources on the slide.

Structure: **Hook** (question, number or story) → **Problem** → **Core message** (max 3 ideas) → **Evidence** → **Call to action** → Q&A. One idea per slide.

## Write the deck in Markdown (use the `write` tool)
```
# Deck title
Subtitle · Speaker · Date

## Slide title that states the takeaway
- 3 bullets maximum, 8 words each
  - optional sub-point
![Chart caption](chart.png)
> One big number or quote
Notes: what to say, 2-4 sentences
```
Slide titles must be conclusions ("Churn fell 18% after onboarding changes"), not topics ("Churn"). No paragraphs on slides.

## Build
`python3 "{baseDir}/scripts/md2slides.py" deck.md deck.html`
Result: a single self-contained HTML file with light/dark theme, arrow-key and swipe navigation, `F` fullscreen, `N` speaker notes, and one slide per page when printing (Ctrl+P → Save as PDF). Local images are embedded automatically. Tell the user the path and these shortcuts.

## Visuals
For numbers, create a chart image with Python (matplotlib if installed) or suggest the right chart; one message per chart, labeled axes, no 3-D.

## Finish
Provide a 3-line speaking plan (opening, key transitions, closing) and the 5 hardest questions the audience may ask, with short answers. If the user needs a .pptx, explain they can import the HTML-to-PDF into PowerPoint or ask you for an outline to paste into their template.
