#!/usr/bin/env python3
"""AppLogs Calendar Integration - Daemon.

Polls macOS Calendar via AppleScript to detect meeting transitions and
writes them to ~/.applogs/logs/calendar-events.jsonl.

Event types emitted:

  meeting_start    — a calendar event has just begun (its start time
                     has arrived and it was not previously active)
  meeting_end      — a previously-active event has concluded
  meeting_upcoming — an event will start within UPCOMING_WINDOW_MIN
                     minutes; this is the preload-trigger signal that
                     lets the model learn "N minutes before a meeting
                     titled X, the user switches to app Y"

This is the contextual force-multiplier. By joining calendar events
against app-focus transitions (from the appfocus integration), the
model can learn temporal patterns like "5 minutes before a meeting
titled 'standup', the user opens Teams 80% of the time" — which is
what makes preloads timely, not just correct.

Requires Automation permission for Calendar (the "Terminal wants to
control Calendar" prompt). This is NOT an Accessibility (AX) query and
does not touch tccd in the way AX does — it is the same permission
class as the Office daemon's `tell application "Microsoft Word"`.
"""

import json
import subprocess
import time
import signal
import sys
from pathlib import Path
from datetime import datetime, timezone

LOG_DIR = Path.home() / '.applogs' / 'logs'
LOG_FILE = LOG_DIR / 'calendar-events.jsonl'
POLL_INTERVAL = 60           # calendar changes slowly; 60s is enough
LOOKBACK_HOURS = 2           # query events started within last 2h (catch active meetings)
LOOKFORWARD_HOURS = 1        # query events starting within next 1h (catch upcoming)
UPCOMING_WINDOW_MIN = 5      # emit meeting_upcoming when event starts within this many minutes


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def log_event(event):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {'timestamp': now_iso(), **event}
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    print(f'[AppLogs Calendar] {entry}')


def run_applescript(script):
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return result.stdout.strip()
        print(f'[AppLogs Calendar] AppleScript error: {result.stderr.strip()}', file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print('[AppLogs Calendar] AppleScript timed out (30s)', file=sys.stderr)
        return None
    except FileNotFoundError:
        return None


# AppleScript that queries all calendars for events in a time window
# and returns tab-separated records, one per line.
# Fields: summary \t start_iso \t end_iso \t location \t all_day \t uid \t calendar_name \t attendees_count
_QUERY_SCRIPT = '''
on formatDate(dt)
    set y to year of dt
    set m to (month of dt) as number
    set dy to day of dt
    set h to hours of dt
    set mn to minutes of dt
    set s to seconds of dt
    return (y as string) & "-" & text -2 thru -1 of ("0" & (m as string)) & "-" & text -2 thru -1 of ("0" & (dy as string)) & "T" & text -2 thru -1 of ("0" & (h as string)) & ":" & text -2 thru -1 of ("0" & (mn as string)) & ":" & text -2 thru -1 of ("0" & (s as string))
end formatDate

tell application "Calendar"
    set now to current date
    set winStart to now - ({lookback} * hours)
    set winEnd to now + ({lookforward} * hours)
    set output to ""
    repeat with c in calendars
        set calName to name of c
        try
            set evs to (every event of c whose start date is greater than winStart and start date is less than winEnd)
        on error
            set evs to {{}}
        end try
        repeat with e in evs
            try
                set evtSummary to summary of e
            on error
                set evtSummary to "(untitled)"
            end try
            try
                set evtStart to my formatDate(start date of e)
            on error
                set evtStart to ""
            end try
            try
                set evtEnd to my formatDate(end date of e)
            on error
                set evtEnd to ""
            end try
            try
                set evtLoc to location of e
                if evtLoc is missing value then set evtLoc to ""
            on error
                set evtLoc to ""
            end try
            try
                set evtAllDay to allday event of e
            on error
                set evtAllDay to false
            end try
            try
                set evtUid to uid of e
                if evtUid is missing value then set evtUid to ""
            on error
                set evtUid to ""
            end try
            try
                set attCount to count of attendees of e
            on error
                set attCount to 0
            end try
            set output to output & evtSummary & "\\t" & evtStart & "\\t" & evtEnd & "\\t" & evtLoc & "\\t" & evtAllDay & "\\t" & evtUid & "\\t" & calName & "\\t" & attCount & "\\n"
        end repeat
    end repeat
    return output
end tell
'''


def query_calendar_events():
    """Return a list of event dicts for events in the query window."""
    script = _QUERY_SCRIPT.format(
        lookback=LOOKBACK_HOURS,
        lookforward=LOOKFORWARD_HOURS,
    )
    raw = run_applescript(script)
    if not raw:
        return []

    events = []
    for line in raw.split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) < 8:
            continue
        summary, start_iso, end_iso, location, all_day, uid, cal_name, att_count = parts[:8]

        # Parse local-time ISO strings and convert to UTC.
        start_utc = parse_local_to_utc(start_iso)
        end_utc = parse_local_to_utc(end_iso)

        event_id = uid if uid else f'{summary}:{start_iso}'
        all_day_bool = all_day.strip().lower() == 'true'

        try:
            attendees = int(att_count.strip()) if att_count.strip() else 0
        except ValueError:
            attendees = 0

        events.append({
            'title': summary,
            'start_time': start_utc or start_iso,
            'end_time': end_utc or end_iso,
            'location': location,
            'all_day': all_day_bool,
            'event_id': event_id,
            'calendar_name': cal_name,
            'attendees_count': attendees,
        })
    return events


def parse_local_to_utc(iso_str):
    """Parse a local-time ISO string (no timezone) and return UTC ISO string."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str)
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    except (ValueError, TypeError):
        return None


def parse_utc(iso_str):
    """Parse a UTC ISO string and return a datetime object."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt
    except (ValueError, TypeError):
        return None


class CalendarMonitor:
    def __init__(self):
        self.running = True
        # event_id -> event dict, for events currently in progress
        self.active_events = {}
        # event_ids for which we've already emitted meeting_upcoming
        self.upcoming_emitted = set()
        # event_ids for which we've already emitted meeting_start
        # (survives even after meeting_end, to avoid re-emitting on restart)
        self.started_emitted = set()

    def signal_handler(self, signum, frame):
        self.running = False

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        print(f'[AppLogs Calendar] Daemon started, polling every {POLL_INTERVAL}s')
        print(f'[AppLogs Calendar] Log file: {LOG_FILE}')
        print(f'[AppLogs Calendar] Upcoming window: {UPCOMING_WINDOW_MIN} min')

        while self.running:
            try:
                self.poll()
            except Exception as e:
                print(f'[AppLogs Calendar] Error during poll: {e}', file=sys.stderr)
            time.sleep(POLL_INTERVAL)

        print('[AppLogs Calendar] Daemon stopped')

    def poll(self):
        now = datetime.now(timezone.utc)
        events = query_calendar_events()
        seen_ids = set()

        for evt in events:
            eid = evt['event_id']
            seen_ids.add(eid)
            start = parse_utc(evt['start_time'])
            end = parse_utc(evt['end_time'])

            # Skip events we can't parse times for.
            if not start or not end:
                continue

            # Skip all-day events for start/end/upcoming tracking —
            # they don't represent "meeting" transitions. We still log
            # them as meeting_start once so the model knows they exist.
            if evt['all_day']:
                if eid not in self.started_emitted and start <= now < end:
                    self._emit('meeting_start', evt)
                    self.started_emitted.add(eid)
                    self.active_events[eid] = evt
                if now >= end and eid in self.active_events:
                    self._emit('meeting_end', evt)
                    del self.active_events[eid]
                continue

            # Event is currently in progress.
            if start <= now < end:
                if eid not in self.started_emitted:
                    self._emit('meeting_start', evt)
                    self.started_emitted.add(eid)
                self.active_events[eid] = evt

            # Event has ended and was active — emit meeting_end.
            if now >= end and eid in self.active_events:
                self._emit('meeting_end', evt)
                del self.active_events[eid]

            # Event is upcoming (within the upcoming window).
            minutes_until = (start - now).total_seconds() / 60.0
            if 0 < minutes_until <= UPCOMING_WINDOW_MIN:
                if eid not in self.upcoming_emitted:
                    self._emit('meeting_upcoming', evt, extra={
                        'minutes_until_start': round(minutes_until, 1),
                    })
                    self.upcoming_emitted.add(eid)

        # Clean up: remove stale entries from active_events for events
        # that no longer appear in the query window and have ended.
        stale = [eid for eid in self.active_events if eid not in seen_ids]
        for eid in stale:
            self._emit('meeting_end', self.active_events[eid])
            del self.active_events[eid]

        # Prune upcoming_emitted for events that have already started.
        self.upcoming_emitted = {
            eid for eid in self.upcoming_emitted
            if eid in seen_ids and eid not in self.started_emitted
        }

    def _emit(self, event_type, evt, extra=None):
        event = {
            'type': event_type,
            'title': evt['title'],
            'start_time': evt['start_time'],
            'end_time': evt['end_time'],
            'event_id': evt['event_id'],
            'calendar_name': evt['calendar_name'],
        }
        if evt['location']:
            event['location'] = evt['location']
        if evt['all_day']:
            event['all_day'] = True
        if evt['attendees_count']:
            event['attendees_count'] = evt['attendees_count']
        if extra:
            event.update(extra)
        log_event(event)


def main():
    monitor = CalendarMonitor()
    monitor.run()


if __name__ == '__main__':
    main()