"""Show chronological activity timeline across all sources."""

import json
from pathlib import Path
from query import query_logs
from datetime import datetime

WORKFLOWS_FILE = Path.home() / '.applogs' / 'logs' / 'workflows.json'


def _load_workflows():
    """Load annotated workflows if available."""
    if not WORKFLOWS_FILE.exists():
        return {}
    try:
        with open(WORKFLOWS_FILE) as f:
            workflows = json.load(f)
        # Build timestamp -> workflow label lookup
        ts_map = {}
        for wf in workflows:
            label = wf.get('label', 'unknown')
            start = wf.get('start_ts', '')[:19]
            end = wf.get('end_ts', '')[:19]
            ts_map[label] = (start, end, wf.get('action_count', 0))
        return ts_map
    except (json.JSONDecodeError, Exception):
        return {}


def show_timeline(today=False, since=None, limit=100, show_workflows=False):
    logs = query_logs(source='all', today=today, since=since, limit=limit)
    
    if not logs:
        print('No logs found.')
        print('Make sure you have integrations installed: applogs install all')
        return 1
    
    workflows = _load_workflows() if show_workflows else {}
    
    print('Activity Timeline')
    print('=' * 70)
    if workflows:
        print(f'  ({len(workflows)} workflows detected)')
    print()
    
    current_date = None
    current_workflow = None
    
    for log in logs:
        ts = log.get('timestamp', '')
        if not ts:
            continue
        
        log_date = ts[:10]
        log_time = ts[11:19] if len(ts) > 11 else '?'
        
        if log_date != current_date:
            current_date = log_date
            print(f'\n--- {log_date} ---\n')
        
        # Check workflow boundaries
        if workflows:
            for label, (start, end, count) in workflows.items():
                if start and end and start[:19] <= ts[:19] <= end[:19]:
                    if label != current_workflow:
                        current_workflow = label
                        print(f'  ┌── [{label}] ({count} actions) ──')
                    break
            else:
                if current_workflow:
                    print(f'  └── end workflow ──')
                    current_workflow = None
        
        source = log.get('_source', '?')
        event_type = log.get('type', '?')
        
        if source == 'shell':
            cmd = log.get('command', '?')[:50]
            exit_code = log.get('exit_code', '?')
            marker = 'x' if exit_code != 0 else '.'
            print(f'  {log_time}  [{marker}] {cmd}')
        elif source == 'chrome':
            url = log.get('url', '?')
            title = log.get('title', '')
            duration = log.get('duration_ms')
            
            if event_type == 'tab_blur' and duration:
                secs = duration / 1000
                if secs > 60:
                    time_str = f'{int(secs // 60)}m{int(secs % 60)}s'
                else:
                    time_str = f'{int(secs)}s'
                print(f'  {log_time}  [~] {title[:40]:40s}  ({time_str})')
            elif event_type in ('tab_focus', 'navigation'):
                domain = _extract_domain(url)
                print(f'  {log_time}  [>] {domain or title[:40]}')
        elif source == 'safari':
            url = log.get('url', '?')
            title = log.get('title', '')
            duration = log.get('duration_s')
            
            if event_type == 'app_blur' and duration:
                if duration > 60:
                    time_str = f'{int(duration // 60)}m{int(duration % 60)}s'
                else:
                    time_str = f'{duration:.0f}s'
                print(f'  {log_time}  [~] Safari                                    ({time_str})')
            elif event_type in ('tab_focus', 'navigation'):
                domain = _extract_domain(url)
                print(f'  {log_time}  [>] {domain or title[:40]}')
            elif event_type == 'app_launch':
                print(f'  {log_time}  [L] Safari launched')
            elif event_type == 'app_quit':
                print(f'  {log_time}  [Q] Safari quit')
        elif source == 'office':
            app = log.get('app', '?')
            doc = log.get('doc_name', '')
            if event_type == 'app_focus':
                print(f'  {log_time}  [W] {app}')
            elif event_type == 'app_blur':
                print(f'  {log_time}  [ ] {app}')
            elif event_type == 'doc_open':
                print(f'  {log_time}  [+] {app}: {doc}')
            elif event_type == 'doc_close':
                print(f'  {log_time}  [-] {app}: {doc}')
            elif event_type == 'doc_focus':
                print(f'  {log_time}  [W] {app}: {doc}')
            elif event_type == 'doc_save':
                print(f'  {log_time}  [S] {app}: {doc}')
            elif event_type == 'app_launch':
                print(f'  {log_time}  [L] {app} launched')
            elif event_type == 'app_quit':
                print(f'  {log_time}  [Q] {app} quit')
    
    if current_workflow:
        print(f'  └── end workflow ──')
    
    print(f'\n{len(logs)} events shown')
    return 0


def _extract_domain(url):
    if not url or url.startswith('chrome://'):
        return url
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or url[:40]
    except Exception:
        return url[:40]