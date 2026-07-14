#!/bin/bash
set -e

INTEGRATION_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="${HOME}/.config/applogs"
LOG_DIR="${HOME}/.applogs/logs"

mkdir -p "$CONFIG_DIR" "$LOG_DIR"

cp "$INTEGRATION_DIR/applogs.sh" "$CONFIG_DIR/"
chmod 644 "$CONFIG_DIR/applogs.sh"

SHELL_RC=""
if [ -n "$ZSH_VERSION" ]; then
  SHELL_RC="${HOME}/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
  SHELL_RC="${HOME}/.bashrc"
else
  SHELL_NAME=$(basename "${SHELL:-/bin/bash}")
  case "$SHELL_NAME" in
    zsh)  SHELL_RC="${HOME}/.zshrc" ;;
    bash) SHELL_RC="${HOME}/.bashrc" ;;
    *)    SHELL_RC="${HOME}/.profile" ;;
  esac
fi

if ! grep -q "source.*applogs.sh" "$SHELL_RC" 2>/dev/null; then
  echo "" >> "$SHELL_RC"
  echo "# AppLogs shell integration" >> "$SHELL_RC"
  echo "source \"$CONFIG_DIR/applogs.sh\"" >> "$SHELL_RC"
  echo "Added AppLogs to $SHELL_RC"
else
  echo "AppLogs already configured in $SHELL_RC"
fi

echo ""
echo "Installation complete!"
echo "Restart your shell or run: source \"$CONFIG_DIR/applogs.sh\""