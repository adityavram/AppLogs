"""Show chronological activity timeline across all sources."""

from query import query_logs
from datetime import datetime


def show_timeline(today=False, since=None, limit=100):
    logs = query_logs(source='all', today=today, since=since, limit=limit)
    
    if not logs:
        print('No logs found.')
        print('Make sure you have integrations installed: applogs install all')
        return 1
    
    print('Activity Timeline')
    print('=' * 70)
    print()
    
    current_date = None
    
    for log in logs:
        ts = log.get('timestamp', '')
        if not ts:
            continue
        
        log_date = ts[:10]
        log_time = ts[11:19] if len(ts) > 11 else '?'
        
        if log_date != current_date:
            current_date = log_date
            print(f'\n--- {log_date} ---\n')
        
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