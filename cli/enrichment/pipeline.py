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
    r'^git\s+reset\s+--(hard|soft)',
    r'^git\s+checkout\s+--\s',  # discard changes (note: -- not just .
]

UNDO_RELATED_ACTIONS = {
    'git_revert': [r'^git\s+commit'],
    'git_reset': [r'^git\s+commit', r'^git\s+add'],
    'git_checkout_discard': [r'^git\s+add', r'.*\.py$', r'.*\.js$', r'.*\.md$'],
}

PAGE_CATEGORIES = {
    'search': [
        r'google\.com/search',
        r'duckduckgo\.com',
        r'bing\.com/search',
        r'search\.yahoo\.com',
    ],
    'social': [
        r'twitter\.com', r'x\.com',
        r'facebook\.com',
        r'linkedin\.com',
        r'reddit\.com',
        r'instagram\.com',
    ],
    'code': [
        r'github\.com',
        r'gitlab\.com',
        r'stackoverflow\.com',
        r'codepen\.io',
        r'replit\.com',
    ],
    'docs': [
        r'docs\.google\.com',
        r'docs\.microsoft\.com',
        r'readthedocs\.io',
        r'notion\.so',
        r'confluence\.atlassian\.com',
    ],
    'video': [
        r'youtube\.com',
        r'vimeo\.com',
        r'twitch\.tv',
    ],
    'ai': [
        r'chatgpt\.com',
        r'chat\.openai\.com',
        r'claude\.ai',
        r'ollama\.com',
        r'huggingface\.co',
    ],
    'email': [
        r'mail\.google\.com',
        r'outlook\.office\.com',
        r'outlook\.live\.com',
    ],
    'shopping': [
        r'amazon\.com',
        r'ebay\.com',
        r'shopify\.com',
    ],
    'news': [
        r'news\.ycombinator\.com',
        r'cnn\.com',
        r'bbc\.com',
        r'nytimes\.com',
        r'theverge\.com',
    ],
    'productivity': [
        r'wisprflow\.ai',
        r'figma\.com',
        r'trello\.com',
        r'asana\.com',
        r'slack\.com',
        r'notion\.so',
    ],
}

CROSS_SOURCE_WINDOW_SECONDS = 30


def classify_page(url):
    """Classify a URL into a page category."""
    if not url:
        return None
    if url.startswith('chrome://') or url.startswith('favorites://'):
        return 'internal'
    
    for category, patterns in PAGE_CATEGORIES.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return category
    return 'other'


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
    """Detect if this action was undone shortly after by a related revert/reset."""
    source = entry.get('_source')
    if source != 'shell':
        return False
    
    command = entry.get('command', '')
    ts = parse_timestamp(entry.get('timestamp'))
    
    if not ts:
        return False
    
    # Only check for undo of actions that could plausibly be undone
    # (commits, adds, file edits — not random commands)
    is_undoable = bool(re.match(r'^git\s+(commit|add|push)|^.*\.(py|js|ts|md|txt|json)$', command))
    if not is_undoable:
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


def find_cross_source_context(entry, all_logs, index):
    """Find related events from other sources within a time window."""
    ts = parse_timestamp(entry.get('timestamp'))
    if not ts:
        return []
    
    entry_source = entry.get('_source', '?')
    related = []
    
    # Look backwards for context from other sources
    for i in range(max(0, index - 20), index):
        other = all_logs[i]
        if other.get('_source') == entry_source:
            continue
        other_ts = parse_timestamp(other.get('timestamp'))
        if not other_ts:
            continue
        delta = (ts - other_ts).total_seconds()
        if delta <= CROSS_SOURCE_WINDOW_SECONDS and delta >= 0:
            related.append({
                'source': other.get('_source'),
                'type': other.get('type'),
                'summary': extract_action_summary(other),
                'seconds_before': round(delta, 1),
            })
    
    return related[-5:]  # last 5 cross-source events


def build_screen_state(recent_actions):
    """Build a snapshot of what's on screen from recent actions."""
    state = {}
    
    # Most recent browser activity
    for action in reversed(recent_actions):
        source = action.get('_source')
        if source in ('chrome', 'safari'):
            url = action.get('url', '')
            title = action.get('title', '')
            if url and not url.startswith('chrome://') and not url.startswith('favorites://'):
                state['browser'] = {
                    'url': url,
                    'title': title,
                    'domain': extract_domain(url),
                    'category': classify_page(url),
                }
                break
    
    # Most recent office activity
    for action in reversed(recent_actions):
        if action.get('_source') == 'office':
            app = action.get('app', '')
            doc = action.get('doc_name', '')
            if app and doc:
                state['office'] = {
                    'app': app,
                    'document': doc,
                }
                break
    
    # Most recent terminal state
    for action in reversed(recent_actions):
        if action.get('_source') == 'shell':
            state['terminal'] = {
                'cwd': action.get('cwd', ''),
                'last_command': action.get('command', ''),
            }
            break
    
    return state


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
            'cross_source': find_cross_source_context(entry, logs, i),
            'screen_state': build_screen_state(recent_window),
        }
        
        # Add page category for browser events
        if entry.get('_source') in ('chrome', 'safari'):
            url = entry.get('url', '')
            if url:
                context['page_category'] = classify_page(url)
        
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
        for key in ('command', 'cwd', 'url', 'title', 'app', 'doc_name', 'doc_path', 
                     'from_url', 'duration_ms', 'duration_s', 'exit_code',
                     'output_first', 'output_last'):
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