# AppLogs Setup Guide

This guide walks you through installing AppLogs from scratch. It takes about 5 minutes.

## Prerequisites

- macOS
- Google Chrome
- Python 3 (pre-installed on macOS)
- Bash or Zsh (default on macOS)
- Microsoft Office (optional, for Office integration)

## Step 1: Clone or Download AppLogs

```bash
git clone <repo-url> ~/AppLogs
cd ~/AppLogs
```

Or if you already have the directory, just `cd` into it.

## Step 2: Install the Shell Integration

The shell integration logs every command you run in the terminal.

```bash
cd ~/AppLogs
./applogs install shell
```

This will:
- Copy the hook script to `~/.config/applogs/`
- Add a source line to your shell config (`.zshrc` or `.bashrc`)

**Activate it in your current session:**

```bash
source ~/.config/applogs/applogs.sh
```

**Verify it works:**

```bash
echo "applogs test"
tail -1 ~/.applogs/logs/shell-commands.jsonl | jq .
```

You should see a JSON entry with your `echo` command.

## Step 3: Install the Chrome Extension

The Chrome extension logs your browsing activity — tab switches, navigations, time spent per site.

### 3a. Load the extension

1. Open Chrome and go to `chrome://extensions/`
2. Toggle **Developer mode** on (top right corner)
3. Click **Load unpacked**
4. Select the folder: `~/AppLogs/integrations/chrome/`
5. You should see "AppLogs Chrome Collector" appear in the list

### 3b. Find your extension ID

On the `chrome://extensions/` page, find the AppLogs Chrome Collector card.
You'll see a 32-character string labeled **ID** (e.g. `pclodgncchlimgccjhnbkhmdgaadimfl`).
Copy it.

### 3c. Set up native messaging

Native messaging lets the extension write logs directly to disk — no manual export needed.

```bash
~/AppLogs/integrations/chrome/setup_native_host.sh YOUR_EXTENSION_ID
```

Replace `YOUR_EXTENSION_ID` with the ID you copied.

### 3d. Reload the extension

Go back to `chrome://extensions/` and click the **reload** icon on the AppLogs card.

### 3e. Verify the connection

1. Click the AppLogs extension icon in your Chrome toolbar (pin it if needed via the puzzle piece icon)
2. The popup should say **Native host: Connected**
3. Browse to a few websites
4. Check the logs:

```bash
tail -3 ~/.applogs/logs/chrome-events.jsonl | jq .
```

You should see entries for the pages you visited.

## Step 4: Install the Office Integration (Optional)

The Office integration logs activity in Microsoft Word, PowerPoint, and Excel — document opens, closes, focus changes, and saves.

```bash
cd ~/AppLogs
./applogs install office
```

This will:
- Install a macOS LaunchAgent that runs the daemon on login
- Start the daemon immediately

**macOS will prompt you to grant automation permissions.** When you see the prompt, click **OK** to allow AppLogs to query Office apps via AppleScript.

If you miss the prompt, go to **System Settings → Privacy & Security → Automation** and enable permissions for Python/Terminal under the Office apps.

**Verify it works:**

1. Open Word, Excel, or PowerPoint
2. Open or create a document
3. Check the logs:

```bash
tail -3 ~/.applogs/logs/office-events.jsonl | jq .
```

You should see entries for app launch, document focus, etc.

**Running manually (for testing):**

If you prefer not to install the LaunchAgent, you can run the daemon directly:

```bash
python3 ~/AppLogs/integrations/office/daemon.py
```

Press Ctrl+C to stop.

## Step 5: Verify Everything Works

Run the status check:

```bash
cd ~/AppLogs
./applogs status
```

You should see all installed integrations active with log counts.

Run a combined analysis:

```bash
./applogs timeline --today
./applogs analyze --today
```

You should see your terminal commands, browser activity, and Office events merged into a single timeline.

## Step 6: Pin the Chrome Extension (Recommended)

To make the AppLogs icon always visible:

1. Click the puzzle piece icon in Chrome's toolbar
2. Find "AppLogs Chrome Collector"
3. Click the pin icon

## Troubleshooting

### Shell integration not logging

Make sure you sourced the script:
```bash
source ~/.config/applogs/applogs.sh
```

Or restart your terminal. The install script adds it to your shell config so it loads automatically on new sessions.

### Chrome extension says "Native host: Not connected"

1. Make sure you ran `setup_native_host.sh` with the correct extension ID
2. Check the manifest exists:
   ```bash
   cat ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/com.applogs.chrome.json
   ```
3. Make sure the wrapper script is executable:
   ```bash
   ls -la ~/AppLogs/integrations/chrome/native_host_wrapper.sh
   ```
   If it doesn't exist, create it:
   ```bash
   echo '#!/bin/bash' > ~/AppLogs/integrations/chrome/native_host_wrapper.sh
   echo 'exec python3 ~/AppLogs/integrations/chrome/native_host.py' >> ~/AppLogs/integrations/chrome/native_host_wrapper.sh
   chmod +x ~/AppLogs/integrations/chrome/native_host_wrapper.sh
   ```
4. Reload the extension at `chrome://extensions/`

### No Chrome logs appearing

- Make sure you reloaded the extension after running `setup_native_host.sh`
- Check the browser console for errors (right-click the extension → Inspect popup)
- Try browsing to a new page — the extension logs on navigation, not on every click

### `jq: command not found`

Install jq:
```bash
brew install jq
```

### Office integration not logging

1. Make sure the daemon is running:
   ```bash
   launchctl list | grep applogs
   ```
   If not, start it:
   ```bash
   ~/AppLogs/integrations/office/install.sh
   ```

2. Check the daemon log for errors:
   ```bash
   cat /tmp/applogs-office.log
   cat /tmp/applogs-office.error.log
   ```

3. Make sure Office apps are installed and you've opened them at least once

4. Grant automation permissions in **System Settings → Privacy & Security → Automation**. Allow Python/Terminal to control Microsoft Word, PowerPoint, and Excel.

5. Test the daemon manually:
   ```bash
   python3 ~/AppLogs/integrations/office/daemon.py
   ```
   Open an Office app and watch for log output in the terminal.

## Next Steps

Once setup is complete, check out the [Usage Guide](USAGE.md) to learn how to get value from your logs.