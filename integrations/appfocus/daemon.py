#!/usr/bin/env python3
"""AppLogs AppFocus Integration - Daemon.

Polls System Events for the frontmost non-background process and logs
app_focus / app_blur (with duration) for EVERY application, not just a
handful. This is the cross-app state layer that the per-app daemons
(safari, office) cannot provide on their own, and it replaces the
primitive track_apps.py "Opened: <app>" poller with real focus/blur
state transitions.

Optionally captures the front window title of the focused app via the
accessibility (AX) API exposed through System Events — this gives
editor/note file names for apps (Sublime, VS Code, Obsidian) that lack
an AppleScript dictionary.

WARNING: AX window-title capture is OFF by default. Querying
`front window of process "X"` triggers an Accessibility permission
prompt routed through tccd; a wedged prompt can spin tccd to hours of
CPU and take down System Settings and Finder. Enable AX only explicitly
via the --capture-window-title flag or the APPFOCUS_CAPTURE_WINDOW_TITLE
env var, and never auto-enable it via a LaunchAgent. With AX off the
daemon logs focus/blur + duration only and never touches TCC.

Writes to ~/.applogs/logs/appfocus-events.jsonl.
"""

import json
import os
import subprocess
import time
import signal
import sys
from pathlib import Path
from datetime import datetime, timezone

LOG_DIR = Path.home() / '.applogs' / 'logs'
LOG_FILE = LOG_DIR / 'appfocus-events.jsonl'
POLL_INTERVAL = 2
MIN_FOCUS_DURATION_S = 2  # ignore sub-2s focus flickers (noise)

# Process names that should never be logged as focused activity.
# These are the tracker's own subprocesses and UI chrome that leak into
# the frontmost process list.
NOISE_PROCESSES = {
    'osascript',
    'appfocus',
    'track_apps',
}


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def log_event(event):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {'timestamp': now_iso(), **event}
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    print(f'[AppLogs AppFocus] {entry}')


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


def get_frontmost_process():
    """Return (name, bundle_id) of the frontmost non-background process.

    Uses UI elements via System Events, which requires Accessibility
    permission. Falls back to the simpler `frontmost` query if the UI
    script is unavailable.
    """
    # Preferred: get both name and bundle id of the frontmost application process.
    script = '''
    tell application "System Events"
        set p to first application process whose frontmost is true
        try
            return (name of p) & "\\n" & (bundle identifier of p)
        on error
            return (name of p) & "\\n"
        end try
    end tell
    '''
    result = run_applescript(script)
    if not result:
        return None, None
    parts = result.split('\n', 1)
    name = parts[0].strip() if parts else ''
    bundle_id = parts[1].strip() if len(parts) > 1 else None
    if not name or name == 'missing value':
        return None, None
    return name, bundle_id


def get_front_window_title(process_name):
    """Best-effort front window title for the focused process via AX.

    Returns '' if unavailable (many apps expose this; Electron apps
    typically include the file/note name in the window title).
    """
    # Escape double quotes in the process name for AppleScript.
    safe = process_name.replace('"', '\\"')
    script = f'''
    tell application "System Events"
        try
            tell process "{safe}"
                set w to front window
                return title of w
            end tell
        on error
            return ""
        end try
    end tell
    '''
    result = run_applescript(script)
    if not result or result == 'missing value':
        return ''
    return result


class AppFocusMonitor:
    def __init__(self, capture_window_title=False):
        self.running = True
        self.focused_app = None
        self.focused_bundle = None
        self.focus_since = None
        # AX window-title capture is OFF by default. See module docstring
        # for the safety rationale — enabling it triggers an Accessibility
        # prompt routed through tccd that can wedge System Settings/Finder.
        self.capture_window_title = capture_window_title

    def signal_handler(self, signum, frame):
        self.running = False

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        print(f'[AppLogs AppFocus] Daemon started, polling every {POLL_INTERVAL}s')
        print(f'[AppLogs AppFocus] Log file: {LOG_FILE}')
        if self.capture_window_title:
            print('[AppLogs AppFocus] Window-title capture enabled (requires Accessibility permission)')

        while self.running:
            try:
                self.poll()
            except Exception as e:
                print(f'[AppLogs AppFocus] Error during poll: {e}', file=sys.stderr)
            time.sleep(POLL_INTERVAL)

        # Emit a final blur for whatever was focused when we stopped.
        if self.focused_app and self.focus_since:
            duration = time.time() - self.focus_since
            if duration >= MIN_FOCUS_DURATION_S:
                log_event({
                    'type': 'app_blur',
                    'app': self.focused_app,
                    'bundle_id': self.focused_bundle,
                    'duration_s': round(duration, 1),
                })
        print('[AppLogs AppFocus] Daemon stopped')

    def poll(self):
        name, bundle_id = get_frontmost_process()
        if not name:
            return

        # Filter noise: the tracker's own subprocess and known chrome.
        if name.lower() in NOISE_PROCESSES:
            return

        # No change in focus — nothing to log.
        if name == self.focused_app:
            return

        now = time.time()

        # Emit blur for the previously focused app.
        if self.focused_app and self.focus_since is not None:
            duration = now - self.focus_since
            if duration >= MIN_FOCUS_DURATION_S:
                log_event({
                    'type': 'app_blur',
                    'app': self.focused_app,
                    'bundle_id': self.focused_bundle,
                    'duration_s': round(duration, 1),
                })

        # Emit focus for the newly focused app.
        window_title = ''
        if self.capture_window_title:
            window_title = get_front_window_title(name)

        event = {
            'type': 'app_focus',
            'app': name,
            'bundle_id': bundle_id,
        }
        if window_title:
            event['window_title'] = window_title
        log_event(event)

        self.focused_app = name
        self.focused_bundle = bundle_id
        self.focus_since = now


def main():
    # AX window-title capture is OFF by default. It may be enabled
    # explicitly via the --capture-window-title flag or the
    # APPFOCUS_CAPTURE_WINDOW_TITLE env var (set to "1" or "true").
    # Enabling it triggers an Accessibility permission prompt routed
    # through tccd; a wedged prompt can take down System Settings and
    # Finder. Do NOT enable this in a LaunchAgent.
    enable_ax = False
    if '--capture-window-title' in sys.argv:
        enable_ax = True
    env_val = os.environ.get('APPFOCUS_CAPTURE_WINDOW_TITLE', '').strip().lower()
    if env_val in ('1', 'true', 'yes', 'on'):
        enable_ax = True

    if enable_ax:
        print('[AppLogs AppFocus] WARNING: AX window-title capture ENABLED.',
              file=sys.stderr)
        print('[AppLogs AppFocus] WARNING: this triggers an Accessibility prompt',
              file=sys.stderr)
        print('[AppLogs AppFocus] WARNING: routed through tccd. If System Settings',
              file=sys.stderr)
        print('[AppLogs AppFocus] WARNING: or Finder stops responding, REBOOT —',
              file=sys.stderr)
        print('[AppLogs AppFocus] WARNING: do not kill tccd/cfprefsd.',
              file=sys.stderr)

    monitor = AppFocusMonitor(capture_window_title=enable_ax)
    monitor.run()


if __name__ == '__main__':
    main()