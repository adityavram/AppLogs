#!/bin/bash
set -e

PLIST_FILE="${HOME}/Library/LaunchAgents/com.applogs.safari.plist"

if [ -f "$PLIST_FILE" ]; then
  launchctl unload "$PLIST_FILE" 2>/dev/null || true
  rm "$PLIST_FILE"
  echo "Stopped and removed AppLogs Safari daemon."
else
  echo "AppLogs Safari integration not installed."
fi