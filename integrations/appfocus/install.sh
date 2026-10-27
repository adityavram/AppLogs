#!/bin/bash
set -e

INTEGRATION_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${HOME}/.applogs/logs"
LAUNCH_AGENT_DIR="${HOME}/Library/LaunchAgents"
PLIST_FILE="$LAUNCH_AGENT_DIR/com.applogs.appfocus.plist"
DAEMON="$INTEGRATION_DIR/daemon.py"

mkdir -p "$LOG_DIR" "$LAUNCH_AGENT_DIR"

cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.applogs.appfocus</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>$DAEMON</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/applogs-appfocus.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/applogs-appfocus.error.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load "$PLIST_FILE"

echo "AppLogs AppFocus integration installed!"
echo ""
echo "The daemon is now running and will auto-start on login."
echo "Logs: $LOG_DIR/appfocus-events.jsonl"
echo ""
echo "Window-title capture is OFF by default. It triggers an"
echo "Accessibility prompt routed through tccd that can wedge"
echo "System Settings/Finder if enabled blindly. To enable it"
echo "MANUALLY (not via launchd), run the daemon directly with"
echo "  --capture-window-title"
echo "or set APPFOCUS_CAPTURE_WINDOW_TITLE=1, and grant"
echo "Accessibility to the running process under System Settings"
echo "> Privacy & Security > Accessibility. Reboot (do NOT kill"
echo "tccd/cfprefsd) if System Settings stops responding."
echo ""
echo "Manage the daemon:"
echo "  Stop:   launchctl unload $PLIST_FILE"
echo "  Start:  launchctl load $PLIST_FILE"
echo "  Status: launchctl list | grep applogs"
echo "  Logs:   tail -f /tmp/applogs-appfocus.log"