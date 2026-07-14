#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "Usage: setup_native_host.sh <EXTENSION_ID>"
  echo ""
  echo "Find your extension ID at chrome://extensions/"
  exit 1
fi

EXTENSION_ID="$1"
INTEGRATION_DIR="$(cd "$(dirname "$0")" && pwd)"
HOST_WRAPPER="$INTEGRATION_DIR/native_host_wrapper.sh"
MANIFEST_DIR="${HOME}/Library/Application Support/Google/Chrome/NativeMessagingHosts"
MANIFEST_FILE="$MANIFEST_DIR/com.applogs.chrome.json"
TEMP_MANIFEST="$INTEGRATION_DIR/native_host_manifest.json"

mkdir -p "$MANIFEST_DIR"

# Generate the manifest with the correct extension ID and host path
cat > "$MANIFEST_FILE" << EOF
{
  "name": "com.applogs.chrome",
  "description": "AppLogs Chrome native messaging host",
  "path": "$HOST_WRAPPER",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://$EXTENSION_ID/"
  ]
}
EOF

echo "Installed native messaging manifest:"
echo "  Manifest: $MANIFEST_FILE"
echo "  Host: $HOST_WRAPPER"
echo "  Extension ID: $EXTENSION_ID"
echo ""
echo "Reload the extension in Chrome to activate native messaging."
echo "Logs will now be written automatically to ~/.applogs/logs/chrome-events.jsonl"