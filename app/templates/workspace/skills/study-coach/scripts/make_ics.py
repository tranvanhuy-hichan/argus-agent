#!/usr/bin/env python3
"""Create an .ics calendar file (opens in Google Calendar, Outlook, Apple Calendar) from a JSON list of events.

Usage: make_ics.py events.json output.ics
Each event: {"title": "...", "start": "2026-11-05 09:00", "end": "2026-11-05 10:00" | "duration_min": 60,
             "location": "...", "notes": "...", "remind_min": 15, "all_day": false}
Times are floating local times (no time zone), so they show at the same clock time wherever you open them.
"""
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone


def fmt(dt, all_day):
    return dt.strftime("%Y%m%d") if all_day else dt.strftime("%Y%m%dT%H%M%S")


def esc(s):
    return str(s).replace("\\", "\\\\").replace(";", "\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    out, b = [], line.encode("utf-8")
    while len(b) > 74:
        cut = 74
        while cut and (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode("utf-8"))
        b = b[cut:]
        b = b" " + b
    out.append(b.decode("utf-8"))
    return "\r\n".join(out)


def parse(s, all_day):
    for f in (("%Y-%m-%d",) if all_day else ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S")):
        try:
            return datetime.strptime(s.strip(), f)
        except ValueError:
            pass
    sys.exit(f"Cannot read date/time: {s!r} (use YYYY-MM-DD HH:MM)")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    events = json.load(open(sys.argv[1], encoding="utf-8"))
    if isinstance(events, dict):
        events = [events]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Argus//Skills//EN", "CALSCALE:GREGORIAN"]
    for e in events:
        all_day = bool(e.get("all_day"))
        start = parse(e["start"], all_day)
        if e.get("end"):
            end = parse(e["end"], all_day)
        else:
            end = start + (timedelta(days=1) if all_day else timedelta(minutes=int(e.get("duration_min", 60))))
        lines += ["BEGIN:VEVENT", f"UID:{uuid.uuid4()}@argus", f"DTSTAMP:{stamp}"]
        lines.append(f"DTSTART;VALUE=DATE:{fmt(start, True)}" if all_day else f"DTSTART:{fmt(start, False)}")
        lines.append(f"DTEND;VALUE=DATE:{fmt(end, True)}" if all_day else f"DTEND:{fmt(end, False)}")
        lines.append(f"SUMMARY:{esc(e['title'])}")
        if e.get("location"):
            lines.append(f"LOCATION:{esc(e['location'])}")
        if e.get("notes"):
            lines.append(f"DESCRIPTION:{esc(e['notes'])}")
        if e.get("remind_min") is not None:
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{esc(e['title'])}", f"TRIGGER:-PT{int(e['remind_min'])}M", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    open(sys.argv[2], "w", encoding="utf-8", newline="").write("\r\n".join(fold(l) for l in lines) + "\r\n")
    print(f"Wrote {sys.argv[2]} with {len(events)} event(s)")


main()
