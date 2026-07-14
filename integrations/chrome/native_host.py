#!/usr/bin/env python3
"""AppLogs Native Messaging Host.

Receives log entries from the Chrome extension via native messaging
and writes them directly to ~/.applogs/logs/chrome-events.jsonl.
"""

import json
import struct
import sys
import os
from pathlib import Path


LOG_DIR = Path.home() / '.applogs' / 'logs'
LOG_FILE = LOG_DIR / 'chrome-events.jsonl'


def read_message():
    """Read a message from Chrome (length-prefixed binary)."""
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length or len(raw_length) < 4:
        return None
    length = struct.unpack('=I', raw_length)[0]
    if length == 0:
        return None
    data = sys.stdin.buffer.read(length).decode('utf-8')
    return json.loads(data)


def send_message(msg):
    """Send a message back to Chrome."""
    data = json.dumps(msg).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('=I', len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def append_log(entry):
    """Append a log entry to the JSONL file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            msg = read_message()
            if msg is None:
                break

            action = msg.get('action', 'log')

            if action == 'log':
                append_log(msg.get('entry', {}))
                send_message({'status': 'ok'})
            elif action == 'ping':
                send_message({'status': 'ok', 'pong': True})
            else:
                send_message({'status': 'error', 'message': f'unknown action: {action}'})
        except Exception as e:
            try:
                send_message({'status': 'error', 'message': str(e)})
            except Exception:
                pass
            break


if __name__ == '__main__':
    main()