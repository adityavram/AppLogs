# AppLogs Office Integration

Logs Microsoft Word, PowerPoint, and Excel activity to AppLogs.

## What it Captures

- **App launch/quit** — when Office apps open and close
- **App focus/blur** — when you switch to/from an Office app
- **Document open/close** — when documents are opened or closed
- **Document focus** — when you switch between documents
- **Document saves** — when you save a document

## How It Works

A Python daemon polls Office apps every 2 seconds via AppleScript, detects state changes, and writes events to `~/.applogs/logs/office-events.jsonl`.

The daemon runs as a macOS LaunchAgent — it starts automatically on login and stays running in the background.

## Install

```bash
./install.sh
```

This will:
- Install a LaunchAgent that runs the daemon on login
- Start the daemon immediately

macOS will prompt you to grant accessibility/automation permissions for the terminal or Python. Allow this so AppleScript can query the Office apps.

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
tail -5 ~/.applogs/logs/office-events.jsonl | jq .

# Filter by app
grep '"word"' ~/.applogs/logs/office-events.jsonl | jq .

# See only saves
grep 'doc_save' ~/.applogs/logs/office-events.jsonl | jq .
```

## Log Format

```json
{"timestamp":"2024-07-13T22:34:56.123Z","type":"app_launch","app":"word","bundle_name":"Microsoft Word"}
{"timestamp":"2024-07-13T22:35:00.456Z","type":"doc_open","app":"word","doc_name":"Report.docx","doc_path":"/Users/you/Documents/Report.docx"}
{"timestamp":"2024-07-13T22:40:00.789Z","type":"doc_save","app":"word","doc_name":"Report.docx","doc_path":"/Users/you/Documents/Report.docx"}
{"timestamp":"2024-07-13T22:41:00.123Z","type":"doc_close","app":"word","doc_name":"Report.docx"}
```

## Event Types

| Type | Description |
|------|-------------|
| `app_launch` | Office app started |
| `app_quit` | Office app closed |
| `app_focus` | Office app became frontmost |
| `app_blur` | Office app lost focus |
| `doc_open` | Document opened |
| `doc_close` | Document closed |
| `doc_focus` | Switched to a different document |
| `doc_save` | Document saved |

## Supported Apps

- Microsoft Word
- Microsoft PowerPoint
- Microsoft Excel

## Privacy

- All data stays on your machine
- The daemon only reads document names and modified state
- No document content is ever accessed

## Troubleshooting

### No events appearing

1. Make sure the daemon is running:
   ```bash
   launchctl list | grep applogs
   ```
2. Check the log:
   ```bash
   cat /tmp/applogs-office.log
   ```
3. Make sure Office apps are installed and you've opened them at least once
4. Grant automation permissions in System Settings → Privacy & Security → Automation