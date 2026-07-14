"""Query and filter logs from all AppLogs sources."""

import json
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict


LOG_DIR = Path.home() / '.applogs' / 'logs'

SOURCE_FILES = {
    'shell': 'shell-commands.jsonl',
    'chrome': 'chrome-events.jsonl',
    'office': 'office-events.jsonl',
}


def load_logs(source='all', limit=None):
    """Load logs from one or all sources."""
    logs = []
    
    sources = [source] if source != 'all' else list(SOURCE_FILES.keys())
    
    for src in sources:
        filename = SOURCE_FILES.get(src)
        if not filename:
            continue
        
        filepath = LOG_DIR / filename
        if not filepath.exists():
            continue
        
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    entry['_source'] = src
                    logs.append(entry)
                except json.JSONDecodeError:
                    continue
    
    logs.sort(key=lambda x: x.get('timestamp', ''))
    
    if limit:
        logs = logs[-limit:]
    
    return logs


def query_logs(source='all', event_type=None, today=False, since=None, grep=None, limit=50):
    """Query logs with filters."""
    logs = load_logs(source=source)
    
    if today:
        today_str = date.today().isoformat()
        logs = [l for l in logs if l.get('timestamp', '').startswith(today_str)]
    
    if since:
        logs = [l for l in logs if l.get('timestamp', '') >= since]
    
    if event_type:
        logs = [l for l in logs if l.get('type') == event_type]
    
    if grep:
        grep_lower = grep.lower()
        logs = [l for l in logs if grep_lower in json.dumps(l).lower()]
    
    if limit:
        logs = logs[-limit:]
    
    return logs


def print_logs(logs):
    """Pretty print log entries."""
    if not logs:
        print('No logs found.')
        return
    
    for log in logs:
        timestamp = log.get('timestamp', '?')[:19]
        source = log.get('_source', '?')
        event_type = log.get('type', '?')
        
        if source == 'shell':
            cmd = log.get('command', '?')[:60]
            exit_code = log.get('exit_code', '?')
            print(f'  {timestamp}  [{source}] {event_type:15s}  cmd={cmd!r}  exit={exit_code}')
        elif source == 'chrome':
            url = log.get('url', '?')[:50]
            title = log.get('title', '')[:30]
            print(f'  {timestamp}  [{source}] {event_type:15s}  url={url!r}  title={title!r}')
        elif source == 'office':
            app = log.get('app', '?')
            doc = log.get('doc_name', '')
            detail = f'app={app} doc={doc!r}' if doc else f'app={app}'
            print(f'  {timestamp}  [{source}] {event_type:15s}  {detail}')
        else:
            print(f'  {timestamp}  [{source}] {event_type:15s}  {json.dumps(log)[:80]}')
    
    print(f'\n{len(logs)} entries')