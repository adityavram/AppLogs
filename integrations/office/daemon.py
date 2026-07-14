#!/usr/bin/env python3
"""AppLogs Office Integration - Daemon.

Polls Microsoft Word, PowerPoint, and Excel via AppleScript to detect
meaningful events: app launch/quit, document open/close, focus changes,
and saves. Writes to ~/.applogs/logs/office-events.jsonl.
"""

import json
import subprocess
import time
import os
import signal
import sys
from pathlib import Path
from datetime import datetime, timezone

LOG_DIR = Path.home() / '.applogs' / 'logs'
LOG_FILE = LOG_DIR / 'office-events.jsonl'
POLL_INTERVAL = 2  # seconds

APPS = {
    'word': 'Microsoft Word',
    'powerpoint': 'Microsoft PowerPoint',
    'excel': 'Microsoft Excel',
}


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def log_event(event):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {'timestamp': now_iso(), **event}
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    print(f'[AppLogs Office] {entry}')


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


def is_app_running(bundle_name):
    result = run_applescript(
        f'tell application "System Events" to (name of every process) contains "{bundle_name}"'
    )
    return result == 'true'


def get_frontmost_app():
    result = run_applescript(
        'tell application "System Events" to name of first process whose frontmost is true'
    )
    return result


def get_app_documents(bundle_name):
    """Get list of open document names from an Office app."""
    script = f'''
    tell application "{bundle_name}"
        set docNames to {{}}
        repeat with d in documents
            set docNames to docNames & {{name of d}}
        end repeat
        return docNames
    end tell
    '''
    result = run_applescript(script)
    if result is None or result == '':
        return []
    # AppleScript returns list as comma-separated string
    return [d.strip() for d in result.split(',') if d.strip()]


def get_front_document(bundle_name):
    """Get the name of the frontmost document in an Office app."""
    script = f'''
    tell application "{bundle_name}"
        try
            return name of front document
        on error
            return ""
        end try
    end tell
    '''
    return run_applescript(script)


def get_document_path(bundle_name, doc_name):
    """Get the file path of a document."""
    script = f'''
    tell application "{bundle_name}"
        try
            return full name of document "{doc_name}"
        on error
            return ""
        end try
    end tell
    '''
    return run_applescript(script)


def get_modified_state(bundle_name, doc_name):
    """Check if document has unsaved changes."""
    script = f'''
    tell application "{bundle_name}"
        try
            return modified of document "{doc_name}"
        on error
            return false
        end try
    end tell
    '''
    result = run_applescript(script)
    return result == 'true'


def get_active_doc_name(bundle_name):
    """Get a human-friendly name for the front document."""
    name = get_front_document(bundle_name)
    if name and name != '':
        path = get_document_path(bundle_name, name)
        return name, path or ''
    return None, None


class OfficeMonitor:
    def __init__(self):
        self.state = {}
        for key in APPS:
            self.state[key] = {
                'running': False,
                'documents': set(),
                'front_doc': None,
                'modified': {},
                'frontmost': False,
                'focus_since': None,
            }
        self.frontmost_app = None
        self.running = True

    def signal_handler(self, signum, frame):
        self.running = False

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        print(f'[AppLogs Office] Daemon started, polling every {POLL_INTERVAL}s')
        print(f'[AppLogs Office] Log file: {LOG_FILE}')

        while self.running:
            try:
                self.poll()
            except Exception as e:
                print(f'[AppLogs Office] Error during poll: {e}', file=sys.stderr)
            time.sleep(POLL_INTERVAL)

        print('[AppLogs Office] Daemon stopped')

    def poll(self):
        current_frontmost = get_frontmost_app()

        for app_key, bundle_name in APPS.items():
            state = self.state[app_key]
            was_running = state['running']
            is_running = is_app_running(bundle_name)

            # App launched
            if is_running and not was_running:
                log_event({
                    'type': 'app_launch',
                    'app': app_key,
                    'bundle_name': bundle_name,
                })

            # App quit
            if not is_running and was_running:
                log_event({
                    'type': 'app_quit',
                    'app': app_key,
                    'bundle_name': bundle_name,
                })
                state['documents'] = set()
                state['front_doc'] = None
                state['modified'] = {}
                state['frontmost'] = False

            if not is_running:
                state['running'] = False
                continue

            state['running'] = True

            # Check frontmost status
            is_frontmost = (current_frontmost == bundle_name)
            if is_frontmost and not state['frontmost']:
                state['focus_since'] = time.time()
            elif not is_frontmost and state['frontmost']:
                focus_duration = time.time() - (state['focus_since'] or time.time())
                if focus_duration >= 3:
                    log_event({
                        'type': 'app_blur',
                        'app': app_key,
                        'bundle_name': bundle_name,
                        'duration_s': round(focus_duration, 1),
                    })
                state['focus_since'] = None
            elif is_frontmost and state['frontmost'] and state['focus_since'] is None:
                state['focus_since'] = time.time()
            
            if is_frontmost and not state['frontmost']:
                log_event({
                    'type': 'app_focus',
                    'app': app_key,
                    'bundle_name': bundle_name,
                })
            state['frontmost'] = is_frontmost

            # Check documents
            current_docs = set(get_app_documents(bundle_name))
            current_docs = {d for d in current_docs if d and d != 'missing value'}

            # Documents opened
            opened = current_docs - state['documents']
            for doc in opened:
                path = get_document_path(bundle_name, doc)
                log_event({
                    'type': 'doc_open',
                    'app': app_key,
                    'doc_name': doc,
                    'doc_path': path or '',
                })

            # Documents closed
            closed = state['documents'] - current_docs
            for doc in closed:
                log_event({
                    'type': 'doc_close',
                    'app': app_key,
                    'doc_name': doc,
                })

            state['documents'] = current_docs

            # Check front document
            front_doc = get_front_document(bundle_name)
            if front_doc:
                if front_doc == 'missing value' or front_doc == '':
                    front_doc = None
                
                if front_doc and front_doc != state['front_doc']:
                    log_event({
                        'type': 'doc_focus',
                        'app': app_key,
                        'doc_name': front_doc,
                    })
                state['front_doc'] = front_doc

            # Check modified state (detect saves)
            for doc in current_docs:
                is_modified = get_modified_state(bundle_name, doc)
                prev_modified = state['modified'].get(doc, False)

                # Document was modified, now it's not -> save happened
                if prev_modified and not is_modified:
                    path = get_document_path(bundle_name, doc)
                    log_event({
                        'type': 'doc_save',
                        'app': app_key,
                        'doc_name': doc,
                        'doc_path': path or '',
                    })

                state['modified'][doc] = is_modified

        self.frontmost_app = current_frontmost


def main():
    monitor = OfficeMonitor()
    monitor.run()


if __name__ == '__main__':
    main()