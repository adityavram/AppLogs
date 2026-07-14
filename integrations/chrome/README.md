# AppLogs Chrome Integration

Logs browser activity to AppLogs via native messaging host.

## What it Captures

- Tab focus changes (which tab, when, how long you stayed)
- Page navigations (URL, title, favicon)
- Page loads

## Install

### 1. Load the extension

```bash
./install.sh
```

Or manually:
1. Open Chrome → `chrome://extensions/`
2. Enable **Developer mode** (top right toggle)
3. Click **Load unpacked**
4. Select this directory

### 2. Set up native messaging

Find your extension ID at `chrome://extensions/` (32-character string), then:

```bash
./setup_native_host.sh <EXTENSION_ID>
```

This installs the native messaging manifest so the extension can write logs directly to disk.

### 3. Reload the extension

Go back to `chrome://extensions/` and click the reload icon on AppLogs.

## How It Works

```
Chrome Extension → native messaging → Python host → ~/.applogs/logs/chrome-events.jsonl
```

The extension sends log entries to a local Python script (`native_host.py`) via Chrome's native messaging protocol. The script writes them directly to the JSONL log file. No manual export needed.

## Verify It Works

1. Click the AppLogs extension icon in Chrome
2. The popup should show **Native host: Connected**
3. Browse to a few pages
4. Check the log file:

```bash
tail -3 ~/.applogs/logs/chrome-events.jsonl | jq .
```

## Uninstall

1. Remove extension from `chrome://extensions/`
2. Remove native host manifest:

```bash
rm ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/com.applogs.chrome.json
```

## Log Format

```json
{"timestamp":"2024-07-13T22:34:56.123Z","type":"tab_focus","url":"https://github.com","title":"GitHub","windowId":123}
{"timestamp":"2024-07-13T22:35:10.456Z","type":"tab_blur","url":"https://github.com","title":"GitHub","duration_ms":14334}
{"timestamp":"2024-07-13T22:35:10.789Z","type":"navigation","url":"https://google.com","title":"Google","favIconUrl":""}
```

## Privacy

- No data leaves your machine
- Logs written locally via native messaging host
- You can inspect the host script at `native_host.py`