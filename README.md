# NEGA Scouting calendar feed

Auto-updating iCal feed of Northeast Georgia Council (Scouting America) events, built from the Councilware calendar at https://www.nega-bsa.org/calendar/ (the "Council Calendar" view, which merges every district and program).

- `build_ics.py` pulls events month by month (1 month back, 13 ahead) and writes `docs/nega.ics`.
- `.github/workflows/build.yml` runs it daily and commits only when events change.
- GitHub Pages serves `docs/`, so the feed lives at `https://<user>.github.io/nega-scouting-calendar/nega.ics`.

Subscribe in Google Calendar: Other calendars > + > From URL > paste the feed URL.

Notes: the source endpoint is undocumented and may change. If the workflow fails or returns zero events, it leaves the last good feed in place.
