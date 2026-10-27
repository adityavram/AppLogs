# AppLogs Calendar Integration

Logs **meeting transitions** from macOS Calendar — the contextual
force-multiplier that lets the model learn *when* preloads should fire,
not just *what*.

## Why this matters

appfocus + Chrome + Office tell the model what the user is doing.
Calendar tells the model **what's about to happen**. By joining
`meeting_upcoming` events against app-focus transitions, the model can
learn patterns like:

> "5 minutes before a meeting titled 'standup', the user opens Teams
> #engineering 80% of the time"

That temporal pattern is what makes preloads **timely** — preloading
Teams to the standup channel 5 minutes before the meeting, not 2 hours
before and not after it's already started.

## What it captures

Polls macOS Calendar every 60s via AppleScript and emits:

| Event | Fields | When |
|-------|--------|------|
| `meeting_start` | `title`, `start_time`, `end_time`, `event_id`, `calendar_name`, `location?`, `all_day?`, `attendees_count?` | a calendar event's start time arrives |
| `meeting_end` | same as above | a previously-active event concludes |
| `meeting_upcoming` | same + `minutes_until_start` | an event will start within 5 minutes (the preload trigger) |

Times are ISO 8601 UTC. `event_id` is the Calendar event's UID (or a
`title:start_time` fallback), used for dedup and state tracking across
polls.

## Install

```bash
./applogs install calendar
```

Or directly:

```bash
bash integrations/calendar/install.sh
```

After install, grant **Automation** permission for Calendar when
prompted (the "Terminal wants to control Calendar" dialog). This is the
same permission class as the Office daemon — it is **not** an
Accessibility/AX query and does not touch `tccd` in the way AX does.

## Logs

`~/.applogs/logs/calendar-events.jsonl`

## Manage

```bash
launchctl unload ~/Library/LaunchAgents/com.applogs.calendar.plist   # stop
launchctl load   ~/Library/LaunchAgents/com.applogs.calendar.plist   # start
tail -f /tmp/applogs-calendar.log
```