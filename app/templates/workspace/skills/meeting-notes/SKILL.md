---
name: meeting-notes
description: "Turn meeting notes or transcripts into minutes with decisions, action items (owner and due date), and calendar files for follow-ups. Use after any meeting or call."
---
# Meeting notes

> Scripts need Python 3. Run them with `python3`; if that command is not found use `python` (or `py` on Windows). Create output files in the current working folder and tell the user the **full path** (use `pwd`, or the path returned by `write`).

## Input
Rough notes, a transcript, or a voice-to-text dump. If it is a file, use `read_document`. Do not invent attendees, dates or owners; mark unknowns as "TBD".

## Minutes format
**Meeting: [topic]**: date, attendees, purpose.
- **Summary**: 2-3 sentences.
- **Discussion**: grouped by topic, 1-3 bullets each, with who raised what only when it matters.
- **Decisions**: each as a complete sentence ("Launch moves to 20 Nov").
- **Action items** as a table: Task | Owner | Due | Status. Every action needs an owner and a date; if missing, list it under "Needs an owner".
- **Open issues / parking lot** and **Next meeting**.
Resolve relative dates ("next Friday") into real dates using the meeting date; if the meeting date is unknown, ask once.

## Follow-up files (do this when there are dated actions or a next meeting)
1. Write the events to a JSON file: `[{"title":"Send draft to client (Lan)","start":"2026-11-14 09:00","duration_min":30,"notes":"From the 4 Nov sync","remind_min":60}]`. Use `"all_day": true` with `start` as `YYYY-MM-DD` for deadlines.
2. Run: `python3 "{baseDir}/scripts/make_ics.py" events.json follow-ups.ics`.
3. Tell the user the path; they open the `.ics` to add everything to Google, Outlook or Apple Calendar.
4. Offer a ready-to-send follow-up email (use the `email-writer` skill) and, with the user's permission, `notify` reminders.

Keep minutes to one page. Facts only; no judgement about people.
