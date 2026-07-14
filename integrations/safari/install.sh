#!/bin/bash
set -e

INTEGRATION_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${HOME}/.applogs/logs"
LAUNCH_AGENT_DIR="${HOME}/Library/LaunchAgents"
PLIST_FILE="$LAUNCH_AGENT_DIR/com.applogs.safari.plist"
DAEMON="$INTEGRATION_DIR/daemon.py"

mkdir -p "$LOG_DIR" "$LAUNCH_AGENT_DIR"

cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.applogs.safari</string>
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
    <string>/tmp/applogs-safari.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/applogs-safari.error.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load "$PLIST_FILE"

echo "AppLogs Safari integration installed!"
echo ""
echo "The daemon is now running and will auto-start on login."
echo "Logs: $LOG_DIR/safari-events.jsonl"
echo ""
echo "Manage the daemon:"
echo "  Stop:   launchctl unload $PLIST_FILE"
echo "  Start:  launchctl load $PLIST_FILE"
echo "  Status: launchctl list | grep applogs"
echo "  Logs:   tail -f /tmp/applogs-safari.log"