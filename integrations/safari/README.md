# AppLogs Safari Integration

Logs Safari browsing activity to AppLogs.

## What it Captures

- **App launch/quit** — when Safari opens and closes
- **App focus/blur** — when you switch to/from Safari (with duration)
- **Navigation** — when you navigate to a new URL
- **Tab focus** — when you switch to a tab with a different URL
- **Tab open/close** — when tabs are opened or closed

## How It Works

A Python daemon polls Safari every 2 seconds via AppleScript, detects state changes, and writes events to `~/.applogs/logs/safari-events.jsonl`.

Runs as a macOS LaunchAgent — starts automatically on login and stays running in the background.

## Install

```bash
./install.sh
```

macOS will prompt you to grant automation permissions. Allow this so AppleScript can query Safari.

## Uninstall

```bash
./uninstall.sh
```

## Run Manually (for testing)

```bash
python3 daemon.py
```

Press Ctrl+C to stop.

## Logs

```bash
# View recent events
tail -5 ~/.applogs/logs/safari-events.jsonl | jq .

# See only navigations
grep '"navigation"' ~/.applogs/logs/safari-events.jsonl | jq .
```

## Log Format

```json
{"timestamp":"2024-07-13T22:34:56.123Z","type":"app_launch"}
{"timestamp":"2024-07-13T22:35:00.456Z","type":"tab_focus","url":"https://github.com","title":"GitHub"}
{"timestamp":"2024-07-13T22:35:10.789Z","type":"navigation","url":"https://google.com","title":"Google","from_url":"https://github.com"}
{"timestamp":"2024-07-13T22:40:00.123Z","type":"app_blur","duration_s":300.5}
```

## Event Types

| Type | Description |
|------|-------------|
| `app_launch` | Safari started |
| `app_quit` | Safari closed |
| `app_focus` | Safari became frontmost |
| `app_blur` | Safari lost focus (with duration) |
| `tab_focus` | Switched to a tab |
| `navigation` | Navigated to a new URL |
| `tab_open` | New tab opened |
| `tab_close` | Tab closed |

## Privacy

- All data stays on your machine
- Only URLs and titles are read
- No page content is accessed

## Troubleshooting

### No events appearing

1. Check the daemon is running:
   ```bash
   launchctl list | grep applogs
   ```
2. Check the log:
   ```bash
   cat /tmp/applogs-safari.log
   ```
3. Grant automation permissions in System Settings → Privacy & Security → Automation
4. Test manually:
   ```bash
   python3 daemon.py
   ```