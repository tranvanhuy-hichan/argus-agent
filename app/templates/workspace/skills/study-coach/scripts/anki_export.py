#!/usr/bin/env python3
"""Export flashcards to a tab-separated file that Anki (File > Import), Quizlet and Excel can import.

Usage: anki_export.py cards.json output.tsv
cards.json: [{"front": "Question", "back": "Answer", "tags": "chapter1 important"}, ...]
(also accepts the keys q / a). Fields keep line breaks as <br> so multi-line answers survive.
"""
import json
import sys


def clean(s):
    return str(s).replace("\t", " ").replace("\r", "").replace("\n", "<br>").strip()


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cards = json.load(open(sys.argv[1], encoding="utf-8"))
    rows = []
    for c in cards:
        front, back = c.get("front", c.get("q")), c.get("back", c.get("a"))
        if not front or not back:
            continue
        tags = c.get("tags", "")
        rows.append("\t".join([clean(front), clean(back), clean(" ".join(tags) if isinstance(tags, list) else tags)]))
    with open(sys.argv[2], "w", encoding="utf-8", newline="") as f:
        f.write("#separator:tab\n#html:true\n#tags column:3\n" + "\n".join(rows) + "\n")
    print(f"Wrote {sys.argv[2]} with {len(rows)} cards")


main()
