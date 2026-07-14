#!/usr/bin/env python3
"""AppLogs Safari Integration - Daemon.

Polls Safari via AppleScript to detect meaningful events:
navigation, tab focus/blur, app launch/quit. Writes to
~/.applogs/logs/safari-events.jsonl.
"""

import json
import subprocess
import time
import signal
import sys
from pathlib import Path
from datetime import datetime, timezone

LOG_DIR = Path.home() / '.applogs' / 'logs'
LOG_FILE = LOG_DIR / 'safari-events.jsonl'
POLL_INTERVAL = 2
BUNDLE_NAME = 'Safari'


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def log_event(event):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {'timestamp': now_iso(), **event}
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    print(f'[AppLogs Safari] {entry}')


def run_applescript(script):
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def is_app_running():
    result = run_applescript(
        f'tell application "System Events" to (name of every process) contains "{BUNDLE_NAME}"'
    )
    return result == 'true'


def is_frontmost():
    result = run_applescript(
        'tell application "System Events" to name of first process whose frontmost is true'
    )
    return result == BUNDLE_NAME


def get_active_tab():
    """Get URL and title of the frontmost Safari tab."""
    script = '''
    tell application "Safari"
        try
            set theDoc to front document
            set theURL to URL of theDoc
            set theTitle to name of theDoc
            return theURL & "\\n" & theTitle
        on error
            return ""
        end try
    end tell
    '''
    result = run_applescript(script)
    if not result:
        return None, None
    parts = result.split('\n', 1)
    url = parts[0] if len(parts) > 0 else ''
    title = parts[1] if len(parts) > 1 else ''
    if url == 'missing value':
        url = ''
    if title == 'missing value':
        title = ''
    return url, title


def get_tab_count():
    """Get total number of open tabs across all windows."""
    script = '''
    tell application "Safari"
        set total to 0
        repeat with w in windows
            try
                set total to total + (count of tabs of w)
            on error
                set total to total + 1
            end try
        end repeat
        return total
    end tell
    '''
    result = run_applescript(script)
    try:
        return int(result) if result else 0
    except (ValueError, TypeError):
        return 0


class SafariMonitor:
    def __init__(self):
        self.running = True
        self.was_running = False
        self.was_frontmost = False
        self.last_url = None
        self.last_title = None
        self.focus_since = None
        self.last_tab_count = 0

    def signal_handler(self, signum, frame):
        self.running = False

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        print(f'[AppLogs Safari] Daemon started, polling every {POLL_INTERVAL}s')
        print(f'[AppLogs Safari] Log file: {LOG_FILE}')

        while self.running:
            try:
                self.poll()
            except Exception as e:
                print(f'[AppLogs Safari] Error during poll: {e}', file=sys.stderr)
            time.sleep(POLL_INTERVAL)

        print('[AppLogs Safari] Daemon stopped')

    def poll(self):
        running = is_app_running()

        # App launch
        if running and not self.was_running:
            log_event({'type': 'app_launch'})

        # App quit
        if not running and self.was_running:
            log_event({'type': 'app_quit'})
            self.last_url = None
            self.last_title = None
            self.was_frontmost = False
            self.focus_since = None
            self.last_tab_count = 0

        self.was_running = running

        if not running:
            return

        # Check tab count for open/close
        tab_count = get_tab_count()
        if tab_count != self.last_tab_count:
            if tab_count > self.last_tab_count:
                log_event({'type': 'tab_open', 'tab_count': tab_count})
            elif tab_count < self.last_tab_count:
                log_event({'type': 'tab_close', 'tab_count': tab_count})
            self.last_tab_count = tab_count

        # Check frontmost status
        frontmost = is_frontmost()

        if frontmost and not self.was_frontmost:
            self.focus_since = time.time()
            log_event({'type': 'app_focus'})
        elif not frontmost and self.was_frontmost:
            focus_duration = time.time() - (self.focus_since or time.time())
            if focus_duration >= 3:
                log_event({
                    'type': 'app_blur',
                    'duration_s': round(focus_duration, 1),
                })
            self.focus_since = None

        self.was_frontmost = frontmost

        # Check active tab URL/title (navigation detection)
        if frontmost:
            url, title = get_active_tab()
            if url and url != self.last_url:
                if self.last_url:
                    log_event({
                        'type': 'navigation',
                        'url': url,
                        'title': title,
                        'from_url': self.last_url,
                    })
                else:
                    log_event({
                        'type': 'tab_focus',
                        'url': url,
                        'title': title,
                    })
                self.last_url = url
                self.last_title = title
            elif title and title != self.last_title:
                self.last_title = title


def main():
    monitor = SafariMonitor()
    monitor.run()


if __name__ == '__main__':
    main()