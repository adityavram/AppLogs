"""Analyze behavioral patterns from logs."""

import json
from collections import Counter, defaultdict
from datetime import datetime, date
from query import query_logs


def analyze_logs(logs):
    """Compute analysis from logs."""
    analysis = {
        'total_events': len(logs),
        'sources': Counter(),
        'event_types': Counter(),
        'by_hour': defaultdict(int),
        'by_day': defaultdict(int),
        'top_commands': Counter(),
        'top_dirs': Counter(),
        'top_sites': Counter(),
        'time_per_site': defaultdict(int),
        'failed_commands': [],
        'date_range': None,
    }
    
    if not logs:
        return analysis
    
    timestamps = []
    
    for log in logs:
        source = log.get('_source', '?')
        event_type = log.get('type', '?')
        ts = log.get('timestamp', '')
        
        analysis['sources'][source] += 1
        analysis['event_types'][event_type] += 1
        
        if ts:
            timestamps.append(ts)
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                analysis['by_hour'][dt.hour] += 1
                analysis['by_day'][dt.strftime('%Y-%m-%d')] += 1
            except (ValueError, TypeError):
                pass
        
        if source == 'shell':
            cmd = log.get('command', '')
            cwd = log.get('cwd', '')
            exit_code = log.get('exit_code', 0)
            
            base_cmd = cmd.split()[0] if cmd else 'unknown'
            analysis['top_commands'][base_cmd] += 1
            analysis['top_dirs'][cwd] += 1
            
            if exit_code != 0:
                analysis['failed_commands'].append({
                    'command': cmd[:60],
                    'exit_code': exit_code,
                    'timestamp': ts[:19],
                })
        
        elif source == 'chrome':
            url = log.get('url', '')
            duration = log.get('duration_ms', 0)
            
            domain = _extract_domain(url)
            if domain:
                analysis['top_sites'][domain] += 1
                if event_type == 'tab_blur' and duration:
                    analysis['time_per_site'][domain] += duration
    
    if timestamps:
        analysis['date_range'] = (min(timestamps)[:10], max(timestamps)[:10])
    
    return analysis


def print_analysis(analysis):
    if analysis['total_events'] == 0:
        print('No logs found.')
        print('Make sure you have integrations installed: applogs install all')
        return
    
    print('Behavioral Analysis')
    print('=' * 50)
    print()
    
    print(f'Total events: {analysis["total_events"]}')
    if analysis['date_range']:
        print(f'Date range: {analysis["date_range"][0]} to {analysis["date_range"][1]}')
    print()
    
    # Sources
    print('By Source:')
    for source, count in analysis['sources'].most_common():
        print(f'  {source:10s}  {count:5d} events')
    print()
    
    # Event types
    print('Event Types:')
    for etype, count in analysis['event_types'].most_common():
        print(f'  {etype:20s}  {count:5d}')
    print()
    
    # Activity by hour
    if analysis['by_hour']:
        print('Activity by Hour:')
        for hour in range(24):
            count = analysis['by_hour'].get(hour, 0)
            if count > 0:
                bar = '#' * min(count, 40)
                print(f'  {hour:02d}:00  {bar} {count}')
        print()
    
    # Top shell commands
    if analysis['top_commands']:
        print('Top Shell Commands:')
        for cmd, count in analysis['top_commands'].most_common(15):
            print(f'  {count:5d}  {cmd}')
        print()
    
    # Top directories
    if analysis['top_dirs']:
        print('Top Working Directories:')
        for cwd, count in analysis['top_dirs'].most_common(10):
            print(f'  {count:5d}  {cwd}')
        print()
    
    # Top sites
    if analysis['top_sites']:
        print('Most Visited Sites:')
        for site, count in analysis['top_sites'].most_common(15):
            print(f'  {count:5d}  {site}')
        print()
    
    # Time per site
    if analysis['time_per_site']:
        print('Time Spent per Site:')
        sorted_sites = sorted(analysis['time_per_site'].items(), key=lambda x: -x[1])
        for site, ms in sorted_sites[:15]:
            minutes = ms / 60000
            if minutes >= 1:
                print(f'  {minutes:7.1f}m  {site}')
            else:
                print(f'  {ms/1000:7.0f}s  {site}')
        print()
    
    # Failed commands
    if analysis['failed_commands']:
        print(f'Failed Commands ({len(analysis["failed_commands"])}):')
        for fail in analysis['failed_commands'][-10:]:
            print(f'  [{fail["exit_code"]}] {fail["command"]}  ({fail["timestamp"]})')
        print()


def _extract_domain(url):
    if not url or url.startswith('chrome://'):
        return None
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or None
    except Exception:
        return None