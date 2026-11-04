---
name: daily-planner
description: "Plan the day or week: prioritise tasks, time-block a realistic schedule, break big goals into steps, and create calendar files and reminders. Use when overloaded or unsure what to do first."
---
# Daily planner

> Scripts need Python 3. Run them with `python3`; if that command is not found use `python` (or `py` on Windows). Create output files in the current working folder and tell the user the **full path** (use `pwd`, or the path returned by `write`).

## Collect
Ask for a brain-dump of tasks (messy is fine), fixed commitments (meetings, pick-ups), working hours, and energy pattern (when focus is best). Note deadlines with real dates. Check stored preferences with `memory_search` before asking again.

## Prioritise
1. Mark each task **Must today / Should this week / Could later / Drop or delegate**.
2. Order by deadline and consequence, then by effort. Pick **at most 3 Must items** per day.
3. Split anything over 90 minutes into concrete next actions that start with a verb ("Draft the intro paragraph").
4. Put deep-focus work in the user's best hours, admin and messages in batches, and leave 20-30% of the day unscheduled for surprises. Add breaks and a stopping time.

## Output
- A time-blocked table: Time | Task | Notes, then **"If I only get 3 things done today"** with the top 3.
- Weekly view: one line per day with its theme and Must items.
- What was postponed or dropped and why, so the user can overrule it.

## Make it real
- **Calendar**: write the time blocks and deadlines as JSON and run `python3 "{baseDir}/scripts/make_ics.py" plan.json plan.ics` (fields: `title`, `start` as `YYYY-MM-DD HH:MM`, `duration_min`, `notes`, `remind_min`, or `all_day: true`). Give the user the file path to import into Google, Outlook or Apple Calendar.
- **Reminders**: with the user's agreement, use `notify` for key reminders and `plan_set` to keep the day's checklist visible.
- **Review**: end of day, ask what was done, move leftovers deliberately, and adjust estimates (people usually underestimate by about 1.5x).

Be realistic and kind; never schedule back-to-back for 10 hours.
