#!/bin/bash
APPLOGS_DIR="${APPLOGS_DIR:-$HOME/.applogs}"
APPLOGS_LOG_FILE="$APPLOGS_DIR/logs/shell-commands.jsonl"

export APPLOGS_SESSION_ID="${APPLOGS_SESSION_ID:-$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "session-$$")}"

mkdir -p "$(dirname "$APPLOGS_LOG_FILE")" 2>/dev/null || true

applogs_write_log() {
  local cmd="$1"
  local cwd="$2"
  local exit_code="$3"
  local duration="$4"
  
  local timestamp=$(python3 -c "from datetime import datetime,timezone; print(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]+'Z')" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%S.000Z")
  local safe_cmd=$(printf '%s' "$cmd" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ')
  local safe_cwd=$(printf '%s' "$cwd" | sed 's/\\/\\\\/g; s/"/\\"/g')
  
  printf '{"timestamp":"%s","type":"shell_command","command":"%s","cwd":"%s","exit_code":%s,"duration_ms":%s,"shell":"%s","session_id":"%s","hostname":"%s"}\n' \
    "$timestamp" "$safe_cmd" "$safe_cwd" "$exit_code" "$duration" "${SHELL##*/}" "$APPLOGS_SESSION_ID" "$(hostname)" >> "$APPLOGS_LOG_FILE"
}

if [ -n "$BASH_VERSION" ]; then
  APPLOGS_CMD=""
  APPLOGS_START=""
  APPLOGS_CWD=""
  
  applogs_preexec() {
    APPLOGS_CMD="$BASH_COMMAND"
    APPLOGS_START=$(date +%s%N)
    APPLOGS_CWD=$(pwd)
  }
  
  applogs_precmd() {
    if [ -n "$APPLOGS_CMD" ]; then
      local end=$(date +%s%N)
      local duration=$(( (end - APPLOGS_START) / 1000000 ))
      applogs_write_log "$APPLOGS_CMD" "$APPLOGS_CWD" $? "$duration"
      APPLOGS_CMD=""
    fi
  }
  
  applogs_trap_debug() {
    if [[ "$BASH_COMMAND" != "applogs_"* ]] && [[ "$BASH_COMMAND" != "PROMPT_COMMAND"* ]] && [[ ! "$BASH_COMMAND" =~ ^\s*$ ]]; then
      applogs_preexec
    fi
  }
  
  trap 'applogs_trap_debug' DEBUG
  PROMPT_COMMAND="applogs_precmd${PROMPT_COMMAND:+;$PROMPT_COMMAND}"

elif [ -n "$ZSH_VERSION" ]; then
  APPLOGS_CMD=""
  APPLOGS_START=""
  APPLOGS_CWD=""
  
  applogs_preexec() {
    APPLOGS_CMD="$1"
    APPLOGS_START=$(date +%s%N)
    APPLOGS_CWD=$(pwd)
  }
  
  applogs_precmd() {
    if [ -n "$APPLOGS_CMD" ]; then
      local end=$(date +%s%N)
      local duration=$(( (end - APPLOGS_START) / 1000000 ))
      applogs_write_log "$APPLOGS_CMD" "$APPLOGS_CWD" $? "$duration"
      APPLOGS_CMD=""
    fi
  }
  
  preexec_functions+=(applogs_preexec)
  precmd_functions+=(applogs_precmd)
fi