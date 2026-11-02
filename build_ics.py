#!/usr/bin/env python3
"""Build an iCal feed from the Northeast Georgia Council (Scouting America) calendar.

Source: the Councilware calendar on https://www.nega-bsa.org/calendar/, which loads
events from render.php as JSON. That endpoint truncates long date ranges, so this
script queries one month at a time and de-duplicates.
"""
import hashlib
import json
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

BASE = "https://www.nega-bsa.org/wp-content/plugins/councilware/calendar/render.php"
CALENDAR_ID = 1          # "Council Calendar" = every district and program merged
MONTHS_BACK = 1
MONTHS_AHEAD = 13
OUT = "docs/nega.ics"
UA = "Mozilla/5.0 (nega-scouting-calendar feed builder; +https://github.com)"


def month_starts():
    today = date.today().replace(day=1)
    y, m = today.year, today.month - MONTHS_BACK
    for _ in range(MONTHS_BACK + MONTHS_AHEAD + 1):
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        yield date(y, m, 1)
        m += 1


def next_month(d):
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def fetch(start, end):
    url = f"{BASE}?calendarID={CALENDAR_ID}&start={start}&end={end}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                raise
            print(f"retry {start}: {e}", file=sys.stderr)
            time.sleep(5)


def esc(s):
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    out, b = [], line.encode("utf-8")
    while len(b) > 75:
        cut = 75
        while (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode())
        b = b" " + b[cut:]
    out.append(b.decode())
    return "\r\n".join(out)


def main():
    events = {}
    for m in month_starts():
        for ev in fetch(m.isoformat(), next_month(m).isoformat()):
            if str(ev.get("isCancelled", "false")).lower() == "true":
                continue
            events[(ev["eventId"], ev["start"])] = ev

    if not events:
        sys.exit("No events returned; refusing to overwrite the feed with an empty calendar.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//nega-scouting-calendar//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "X-WR-CALNAME:NEGA Scouting", "X-WR-TIMEZONE:America/New_York",
        "X-WR-CALDESC:Northeast Georgia Council events (auto-synced from nega-bsa.org)",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H", "X-PUBLISHED-TTL:PT12H",
        "BEGIN:VTIMEZONE", "TZID:America/New_York",
        "BEGIN:DAYLIGHT", "TZOFFSETFROM:-0500", "TZOFFSETTO:-0400", "TZNAME:EDT",
        "DTSTART:19700308T020000", "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU", "END:DAYLIGHT",
        "BEGIN:STANDARD", "TZOFFSETFROM:-0400", "TZOFFSETTO:-0500", "TZNAME:EST",
        "DTSTART:19701101T020000", "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU", "END:STANDARD",
        "END:VTIMEZONE",
    ]
    for ev in sorted(events.values(), key=lambda e: (e["start"], e["title"])):
        s, e = ev["start"], ev.get("end") or ""
        url = ev.get("eventPageURL") or "https://www.nega-bsa.org/calendar/"
        uid = hashlib.md5(f'{ev["eventId"]}|{s}'.encode()).hexdigest() + "@nega-bsa.org"
        lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}", "SUMMARY:" + esc(ev["title"])]
        if s.endswith("T00:00:00") and (not e or e.endswith("T23:59:59")):
            d0 = date.fromisoformat(s[:10])
            d1 = date.fromisoformat((e or s)[:10]) + timedelta(days=1)
            lines += [f"DTSTART;VALUE=DATE:{d0:%Y%m%d}", f"DTEND;VALUE=DATE:{d1:%Y%m%d}"]
        else:
            f = lambda x: x.replace("-", "").replace(":", "")  # noqa: E731
            lines += [f"DTSTART;TZID=America/New_York:{f(s)}",
                      f"DTEND;TZID=America/New_York:{f(e or s)}"]
        if ev.get("location"):
            lines.append("LOCATION:" + esc(ev["location"]))
        desc = f"Details: {url}"
        if ev.get("registrationURL"):
            desc += f"\nRegister: {ev['registrationURL']}"
        lines += ["DESCRIPTION:" + esc(desc), f"URL:{url}", "END:VEVENT"]
    lines.append("END:VCALENDAR")

    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        fh.write("\r\n".join(fold(l) for l in lines) + "\r\n")
    print(f"Wrote {len(events)} events to {OUT}")


if __name__ == "__main__":
    main()
