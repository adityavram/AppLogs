#!/bin/bash
set -e

PLIST_FILE="${HOME}/Library/LaunchAgents/com.applogs.refine.plist"

if [ -f "$PLIST_FILE" ]; then
  launchctl unload "$PLIST_FILE" 2>/dev/null || true
  rm "$PLIST_FILE"
  echo "Removed weekly refinement job."
else
  echo "Weekly refinement job not installed."
fi