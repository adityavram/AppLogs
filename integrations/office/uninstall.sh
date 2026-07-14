#!/bin/bash
set -e

PLIST_FILE="${HOME}/Library/LaunchAgents/com.applogs.office.plist"

if [ -f "$PLIST_FILE" ]; then
  launchctl unload "$PLIST_FILE" 2>/dev/null || true
  rm "$PLIST_FILE"
  echo "Stopped and removed AppLogs Office daemon."
else
  echo "AppLogs Office integration not installed."
fi