"""AppLogs Enrichment Pipeline.

Post-processes raw JSONL logs from all sources and adds:
- context: state snapshot at the time of each action (recent actions, focused app, time features)
- outcome: what happened after the action (retry, undo, next action delay)
- workflow_id: cluster of related actions across sources

Input:  ~/.applogs/logs/*.jsonl (raw events)
Output: ~/.applogs/logs/enriched.jsonl (state-action-outcome triplets)
"""

import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import re


LOG_DIR = Path.home() / '.applogs' / 'logs'
RAW_FILES = {
    'shell': 'shell-commands.jsonl',
    'chrome': 'chrome-events.jsonl',
    'safari': 'safari-events.jsonl',
    'office': 'office-events.jsonl',
}
ENRICHED_FILE = LOG_DIR / 'enriched.jsonl'

RECENT_ACTION_WINDOW = 10
WORKFLOW_GAP_SECONDS = 300
RETRY_WINDOW_SECONDS = 60
UNDO_PATTERNS = [
    r'^git\s+revert',
    r'^git\s+reset',
    r'^git\s+checkout\s+\.',  # discard changes
    r'^rm\s+',
    r'^undo$',
]


def load_all_raw_logs():
    """Load and merge all raw logs, sorted by timestamp."""
    logs = []
    for source, filename in RAW_FILES.items():
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
                    entry['_source'] = source
                    logs.append(entry)
                except json.JSONDecodeError:
                    continue
    
    logs.sort(key=lambda x: x.get('timestamp', ''))
    return logs


def parse_timestamp(ts):
    """Parse ISO timestamp, return datetime or None."""
    if not ts:
        return None
    try:
        # Fix malformed timestamps like 2026-07-14T03:14:00.3NZ
        # The .3N is not valid, replace with milliseconds
        import re
        clean = re.sub(r'\.\d+N', '', ts)  # remove .3N style fractional
        clean = clean.replace('Z', '+00:00')
        if '+' not in clean and 'T' in clean:
            clean = clean + '+00:00'
        return datetime.fromisoformat(clean)
    except (ValueError, TypeError):
        return None


def extract_time_features(ts):
    """Extract time-based features from timestamp."""
    dt = parse_timestamp(ts)
    if not dt:
        return {}
    return {
        'hour': dt.hour,
        'day_of_week': dt.weekday(),
        'is_weekend': dt.weekday() >= 5,
        'minute_of_day': dt.hour * 60 + dt.minute,
    }


def extract_action_summary(entry):
    """Extract a human-readable action summary from a log entry."""
    source = entry.get('_source', '?')
    event_type = entry.get('type', '?')
    
    if source == 'shell':
        cmd = entry.get('command', '?')
        base = cmd.split()[0] if cmd else 'unknown'
        return f'{base} ({event_type})'
    elif source in ('chrome', 'safari'):
        url = entry.get('url', '')
        if not url:
            return f'{event_type}'
        domain = extract_domain(url)
        return f'{domain or url[:30]} ({event_type})'
    elif source == 'office':
        app = entry.get('app', '?')
        doc = entry.get('doc_name', '')
        return f'{app}: {doc} ({event_type})' if doc else f'{app} ({event_type})'
    return f'{event_type}'


def extract_domain(url):
    """Extract domain from URL."""
    if not url or url.startswith('chrome://') or url.startswith('favorites://'):
        return None
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or None
    except Exception:
        return None


def infer_focused_app(entry, recent_actions):
    """Infer what app was focused when this action occurred."""
    source = entry.get('_source', '?')
    
    # If it's an app_focus event, that tells us directly
    if entry.get('type') == 'app_focus':
        return entry.get('app') or entry.get('_source')
    
    # If it's a shell command, terminal was focused
    if source == 'shell':
        return 'terminal'
    
    # If it's a chrome/safari event with tab_focus or navigation, browser was focused
    if source in ('chrome', 'safari') and entry.get('type') in ('tab_focus', 'navigation', 'page_load'):
        return source
    
    # If it's an office doc_focus or app_focus, office was focused
    if source == 'office' and entry.get('type') in ('doc_focus', 'app_focus', 'doc_open', 'doc_save'):
        return entry.get('app', 'office')
    
    # Fall back to most recent app_focus in window
    for action in reversed(recent_actions):
        if action.get('type') in ('app_focus', 'tab_focus'):
            return action.get('app') or action.get('_source')
    
    return source


def detect_retry(entry, future_actions):
    """Detect if this action was retried (same command run again shortly after a failure)."""
    source = entry.get('_source')
    if source != 'shell':
        return False
    
    exit_code = entry.get('exit_code', 0)
    command = entry.get('command', '')
    ts = parse_timestamp(entry.get('timestamp'))
    
    if not ts or exit_code == 0:
        return False
    
    # Look for same command in the next RETRY_WINDOW_SECONDS
    for future in future_actions:
        if future.get('_source') != 'shell':
            continue
        future_ts = parse_timestamp(future.get('timestamp'))
        if not future_ts:
            continue
        delta = (future_ts - ts).total_seconds()
        if delta > RETRY_WINDOW_SECONDS:
            break
        if future.get('command', '') == command:
            return True
    
    return False


def detect_undo(entry, future_actions):
    """Detect if this action was undone shortly after."""
    source = entry.get('_source')
    if source != 'shell':
        return False
    
    ts = parse_timestamp(entry.get('timestamp'))
    if not ts:
        return False
    
    for future in future_actions:
        if future.get('_source') != 'shell':
            continue
        future_ts = parse_timestamp(future.get('timestamp'))
        if not future_ts:
            continue
        delta = (future_ts - ts).total_seconds()
        if delta > RETRY_WINDOW_SECONDS:
            break
        cmd = future.get('command', '')
        for pattern in UNDO_PATTERNS:
            if re.match(pattern, cmd):
                return True
    
    return False


def get_next_action_delay(entry, future_actions):
    """Get time until next action (proxy for satisfaction/confidence)."""
    ts = parse_timestamp(entry.get('timestamp'))
    if not ts or not future_actions:
        return None
    
    future_ts = parse_timestamp(future_actions[0].get('timestamp'))
    if not future_ts:
        return None
    
    delta = (future_ts - ts).total_seconds()
    return round(delta, 2)


def assign_workflow_ids(logs):
    """Assign workflow IDs by clustering actions within WORKFLOW_GAP_SECONDS."""
    workflow_id = 0
    prev_ts = None
    
    for entry in logs:
        ts = parse_timestamp(entry.get('timestamp'))
        if not ts:
            entry['_workflow_id'] = workflow_id
            continue
        
        if prev_ts and (ts - prev_ts).total_seconds() > WORKFLOW_GAP_SECONDS:
            workflow_id += 1
        
        entry['_workflow_id'] = workflow_id
        prev_ts = ts
    
    return logs


def enrich_logs():
    """Main enrichment pipeline."""
    logs = load_all_raw_logs()
    
    if not logs:
        print('No raw logs found.')
        return 0
    
    print(f'Loaded {len(logs)} raw events from {len(set(l.get("_source") for l in logs))} sources')
    
    # Assign workflow IDs
    logs = assign_workflow_ids(logs)
    
    enriched = []
    recent_window = []
    
    for i, entry in enumerate(logs):
        future_actions = logs[i+1:i+10]
        
        # Build context
        context = {
            'recent_actions': [
                {
                    'source': a.get('_source'),
                    'type': a.get('type'),
                    'summary': extract_action_summary(a),
                    'timestamp': a.get('timestamp', ''),
                }
                for a in recent_window[-RECENT_ACTION_WINDOW:]
            ],
            'focused_app': infer_focused_app(entry, recent_window),
            'time_features': extract_time_features(entry.get('timestamp')),
            'workflow_id': entry.get('_workflow_id'),
        }
        
        # Build outcome
        outcome = {
            'exit_code': entry.get('exit_code'),
            'duration_ms': entry.get('duration_ms') or entry.get('duration_s'),
            'next_action_delay_s': get_next_action_delay(entry, future_actions),
            'retried': detect_retry(entry, future_actions),
            'undone': detect_undo(entry, future_actions),
        }
        
        # Build enriched entry
        enriched_entry = {
            'timestamp': entry.get('timestamp'),
            'source': entry.get('_source'),
            'type': entry.get('type'),
            'action': extract_action_summary(entry),
            'context': context,
            'outcome': outcome,
        }
        
        # Preserve source-specific fields
        for key in ('command', 'cwd', 'url', 'title', 'app', 'doc_name', 'doc_path', 'from_url', 'duration_ms', 'duration_s', 'exit_code'):
            if key in entry:
                enriched_entry[key] = entry[key]
        
        enriched.append(enriched_entry)
        
        # Update sliding window
        recent_window.append(entry)
    
    # Write enriched file
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(ENRICHED_FILE, 'w') as f:
        for entry in enriched:
            f.write(json.dumps(entry) + '\n')
    
    print(f'Enriched {len(enriched)} events → {ENRICHED_FILE}')
    return len(enriched)


if __name__ == '__main__':
    enrich_logs()