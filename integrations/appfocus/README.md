# AppLogs AppFocus Integration

Logs **app focus/blur with duration for every application** on the machine —
the cross-app state layer that the per-app daemons (Safari, Office) cannot
provide on their own.

This is the single highest-value integration for behavior modeling: it turns
"Opened: Spotify" (the primitive `track_apps.py` record) into
"Spotify focused 12m → blurred to Terminal", which is a real state transition.

## What it captures

Polls `System Events` every 2s for the frontmost non-background process and
emits:

| Event | Fields | When |
|-------|--------|------|
| `app_focus` | `app`, `bundle_id`, `window_title?` | an app becomes frontmost |
| `app_blur`  | `app`, `bundle_id`, `duration_s`    | focus leaves an app (after ≥2s) |

`window_title` is captured best-effort via the Accessibility (AX) API. For apps
without an AppleScript dictionary (Sublime Text, VS Code, Obsidian), the
window title typically contains the open file/note name — this is how we get
editor/note signal without a per-app integration.

## ⚠️ AX window-title capture is OFF by default

Querying `front window of process "X"` via System Events triggers an
**Accessibility permission prompt routed through `tccd`**. A wedged prompt
can spin `tccd` to hours of CPU and take down **System Settings and Finder**
— this has happened on this machine. The default-off behavior is the safety
property; preserve it.

To enable AX **manually** (never via a LaunchAgent):

```bash
# run the daemon directly, not through launchd:
python3 integrations/appfocus/daemon.py --capture-window-title
# or:
APPFOCUS_CAPTURE_WINDOW_TITLE=1 python3 integrations/appfocus/daemon.py
```

Then grant Accessibility to the running process under *System Settings →
Privacy & Security → Accessibility*. If System Settings or Finder stops
responding, **REBOOT** — do not kill `tccd`/`cfprefsd`/`UserNotificationCenter`
(killing them is what escalated the original incident).

With AX off, the daemon logs focus/blur + duration only and never touches TCC.

## Install

```bash
./applogs install appfocus
```

Or directly:

```bash
bash integrations/appfocus/install.sh
```

The installed LaunchAgent runs the daemon with AX **off** (no
`--capture-window-title` flag in the plist). Focus/blur + duration are
captured immediately with no permission prompts. Enable AX only by running
the daemon manually as described above.

## Logs

`~/.applogs/logs/appfocus-events.jsonl`

## Manage

```bash
launchctl unload ~/Library/LaunchAgents/com.applogs.appfocus.plist   # stop
launchctl load   ~/Library/LaunchAgents/com.applogs.appfocus.plist   # start
tail -f /tmp/applogs-appfocus.log
```

## Replacing the primitive tracker

This daemon supersedes `~/Scripts/track_apps.py` (the `com.user.apptracker`
LaunchAgent that writes the daily `*.log` files). To stop the old tracker:

```bash
launchctl unload ~/Library/LaunchAgents/com.user.apptracker.plist
```

The AppLogs project does not depend on `track_apps.py`.