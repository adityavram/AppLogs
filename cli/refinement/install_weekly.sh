#!/bin/bash
set -e

INTEGRATION_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$INTEGRATION_DIR/../.." && pwd)"
LAUNCH_AGENT_DIR="${HOME}/Library/LaunchAgents"
PLIST_FILE="$LAUNCH_AGENT_DIR/com.applogs.refine.plist"
JOB_SCRIPT="$INTEGRATION_DIR/weekly_job.py"

mkdir -p "$LAUNCH_AGENT_DIR"

cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.applogs.refine</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>$JOB_SCRIPT</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/applogs-refine.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/applogs-refine.error.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load "$PLIST_FILE"

echo "AppLogs weekly refinement job installed!"
echo ""
echo "Runs every Sunday at 3:00 AM"
echo "Manages the daemon:"
echo "  Run now:  python3 $JOB_SCRIPT"
echo "  Stop:     launchctl unload $PLIST_FILE"
echo "  Start:    launchctl load $PLIST_FILE"
echo "  Status:   launchctl list | grep applogs"
echo "  Logs:     tail -f /tmp/applogs-refine.log"