#!/bin/bash
set -e

INTEGRATION_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${HOME}/.applogs/logs"
HOST_SCRIPT="$INTEGRATION_DIR/native_host.py"
HOST_WRAPPER="$INTEGRATION_DIR/native_host_wrapper.sh"
MANIFEST_DIR="${HOME}/Library/Application Support/Google/Chrome/NativeMessagingHosts"
MANIFEST_FILE="$MANIFEST_DIR/com.applogs.chrome.json"

mkdir -p "$LOG_DIR" "$MANIFEST_DIR"

# Create wrapper script so Chrome can execute the Python host
cat > "$HOST_WRAPPER" << EOF
#!/bin/bash
exec python3 "$HOST_SCRIPT"
EOF
chmod +x "$HOST_WRAPPER"

# Install native host manifest
echo ""
echo "Native Messaging Setup"
echo "======================="
echo ""
echo "To enable automatic logging, you need to connect this extension to the native host."
echo ""
echo "1. Load this extension in Chrome: chrome://extensions/ (Developer mode -> Load unpacked)"
echo "   Select: $INTEGRATION_DIR"
echo ""
echo "2. Find the extension ID (a 32-character string like abcdefghijklmnopqrstuvwxyz123456)"
echo "   Copy it and run:"
echo ""
echo "   $INTEGRATION_DIR/setup_native_host.sh <EXTENSION_ID>"
echo ""
echo "   Or just paste it here:"
read -p "   Extension ID: " EXT_ID

if [ -n "$EXT_ID" ]; then
  "$INTEGRATION_DIR/setup_native_host.sh" "$EXT_ID"
else
  echo "Skipped native host setup. Run setup_native_host.sh later with your extension ID."
fi

echo ""
echo "Chrome extension folder: $INTEGRATION_DIR"
echo "Logs location: $LOG_DIR/chrome-events.jsonl"