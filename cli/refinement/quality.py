"""Data quality layer: deduplicate, filter noise, normalize actions, freshness-weight screen state."""

import re
import json
from datetime import datetime
from collections import defaultdict


DEDUP_WINDOW_SECONDS = 5
SCREEN_STATE_FRESHNESS_SECONDS = 120
MIN_WORKFLOW_ACTIONS = 3
NOISE_PATTERNS = [
    r'^PROMPT_COMMAND=',
    r'^applogs_pre(cmd|exec)',
    r'^applogs_trap_debug',
]

ACTION_NORMALIZATIONS = [
    (r'^git\s+push', 'vcs_deploy'),
    (r'^git\s+commit', 'vcs_commit'),
    (r'^git\s+checkout\s+-b', 'vcs_branch_create'),
    (r'^git\s+checkout', 'vcs_branch_switch'),
    (r'^git\s+(pull|fetch)', 'vcs_sync'),
    (r'^git\s+status', 'vcs_status'),
    (r'^git\s+revert', 'vcs_revert'),
    (r'^git\s+merge', 'vcs_merge'),
    (r'^git\s+add', 'vcs_stage'),
    (r'^git\s+log', 'vcs_history'),
    (r'^git\s+diff', 'vcs_diff'),
    (r'^npm\s+(run\s+)?(test|jest)', 'run_tests'),
    (r'^npm\s+(run\s+)?(build|compile)', 'build'),
    (r'^npm\s+(install|i)\s', 'install_deps'),
    (r'^npm\s+(run\s+)?(dev|start)', 'run_dev_server'),
    (r'^python3?\s+.*\.py', 'run_python'),
    (r'^pip3?\s+install', 'install_deps'),
    (r'^docker\s+build', 'docker_build'),
    (r'^docker\s+run', 'docker_run'),
    (r'^docker\s+push', 'docker_push'),
    (r'^curl\s', 'http_request'),
    (r'^wget\s', 'http_request'),
    (r'^ssh\s', 'ssh_connect'),
    (r'^scp\s', 'file_transfer'),
    (r'^rsync\s', 'file_transfer'),
    (r'^cat\s', 'file_read'),
    (r'^tail\s', 'file_read'),
    (r'^head\s', 'file_read'),
    (r'^grep\s', 'search'),
    (r'^find\s', 'search'),
    (r'^ls\s', 'list_files'),
    (r'^ls$', 'list_files'),
    (r'^cd\s', 'change_dir'),
    (r'^pwd', 'print_dir'),
    (r'^echo\s', 'print'),
    (r'^mkdir\s', 'create_dir'),
    (r'^rm\s', 'delete_file'),
    (r'^mv\s', 'move_file'),
    (r'^cp\s', 'copy_file'),
    (r'^touch\s', 'create_file'),
    (r'^chmod\s', 'change_perms'),
    (r'^./applogs\s+(\w+)', 'applogs_{cmd}'),
    (r'^code\s', 'open_editor'),
    (r'^vim\s', 'open_editor'),
    (r'^nano\s', 'open_editor'),
    (r'^brew\s+install', 'install_deps'),
    (r'^jq\s', 'process_json'),
]


def parse_timestamp(ts):
    if not ts:
        return None
    try:
        clean = re.sub(r'\.\d+N', '', ts)
        clean = clean.replace('Z', '+00:00')
        if '+' not in clean and 'T' in clean:
            clean = clean + '+00:00'
        return datetime.fromisoformat(clean)
    except (ValueError, TypeError):
        return None


def deduplicate_events(events):
    """Collapse rapid identical events and page_load+navigation pairs."""
    if not events:
        return []
    
    deduped = []
    last_by_key = {}
    
    i = 0
    while i < len(events):
        event = events[i]
        ts = parse_timestamp(event.get('timestamp'))
        if not ts:
            deduped.append(event)
            i += 1
            continue
        
        source = event.get('_source', event.get('source', ''))
        event_type = event.get('type', '')
        
        # Skip page_load if a navigation for same URL follows within window
        if source in ('chrome', 'safari') and event_type == 'page_load':
            url = event.get('url', '')
            if url and i + 1 < len(events):
                next_event = events[i + 1]
                next_ts = parse_timestamp(next_event.get('timestamp', ''))
                if (next_ts and 
                    (next_ts - ts).total_seconds() <= DEDUP_WINDOW_SECONDS and
                    next_event.get('_source', next_event.get('source', '')) == source and
                    next_event.get('type') == 'navigation' and
                    next_event.get('url', '') == url):
                    # Skip this page_load, the navigation will be kept
                    i += 1
                    continue
        
        if source == 'shell':
            key = f'{source}:{event_type}:{event.get("command", "")}'
        elif source in ('chrome', 'safari'):
            key = f'{source}:{event_type}:{event.get("url", "")}'
        elif source == 'office':
            key = f'{source}:{event_type}:{event.get("app", "")}:{event.get("doc_name", "")}'
        else:
            key = f'{source}:{event_type}'
        
        last_ts = last_by_key.get(key)
        
        if last_ts and (ts - last_ts).total_seconds() <= DEDUP_WINDOW_SECONDS:
            i += 1
            continue
        
        last_by_key[key] = ts
        deduped.append(event)
        i += 1
    
    return deduped


def sanitize_url(url):
    """Strip sensitive query parameters from URLs."""
    if not url:
        return url
    if url.startswith('chrome://') or url.startswith('favorites://'):
        return url
    
    # Split URL and query string
    if '?' not in url:
        return url
    
    base, query = url.split('?', 1)
    
    # If query contains sensitive params, strip entire query string
    sensitive_indicators = [
        'encrypted_context', 'token', 'password', 'auth', 'session',
        'api_key', 'apikey', 'access_token', 'refresh_token',
        'client_secret', 'code=', 'private_key', 'credential',
        'ci=', 'apc=', 'cuid=', 'attempt_id=',
        'privacy_mutation_token', 'ars=',
    ]
    
    query_lower = query.lower()
    for indicator in sensitive_indicators:
        if indicator in query_lower:
            return base + '?[sanitized]'
    
    # Keep non-sensitive query params (like search queries)
    return url


def filter_noise(events):
    """Remove events that are noise (internal commands, blank events)."""
    filtered = []
    
    for event in events:
        source = event.get('_source', event.get('source', ''))
        
        if source == 'shell':
            command = event.get('command', '')
            is_noise = False
            for pattern in NOISE_PATTERNS:
                if re.match(pattern, command):
                    is_noise = True
                    break
            if is_noise:
                continue
            
            # Skip empty commands
            if not command.strip():
                continue
        
        if source in ('chrome', 'safari'):
            url = event.get('url', '')
            # Skip internal browser pages
            if url and (url.startswith('chrome://') or url.startswith('favorites://')):
                # Only keep if it's a meaningful navigation type
                if event.get('type') == 'tab_focus':
                    continue
        
        filtered.append(event)
    
    return filtered


def normalize_action(event):
    """Normalize an action to a standardized type."""
    source = event.get('_source', event.get('source', ''))
    event_type = event.get('type', '')
    
    normalized = event.copy()
    
    if source == 'shell':
        command = event.get('command', '')
        for pattern, action_type in ACTION_NORMALIZATIONS:
            match = re.match(pattern, command)
            if match:
                if '{cmd}' in action_type and match.groups():
                    normalized['action_type'] = action_type.format(cmd=match.group(1))
                else:
                    normalized['action_type'] = action_type
                break
        else:
            base_cmd = command.split()[0] if command else 'unknown'
            normalized['action_type'] = f'cmd_{base_cmd}'
    
    elif source in ('chrome', 'safari'):
        url = event.get('url', '')
        if url:
            normalized['url'] = sanitize_url(url)
        if event_type in ('navigation', 'page_load'):
            normalized['action_type'] = 'web_browse'
        elif event_type == 'tab_focus':
            normalized['action_type'] = 'web_focus'
        elif event_type == 'tab_blur':
            normalized['action_type'] = 'web_blur'
        elif event_type == 'app_focus':
            normalized['action_type'] = 'app_focus'
        elif event_type == 'app_blur':
            normalized['action_type'] = 'app_blur'
        elif event_type == 'app_launch':
            normalized['action_type'] = 'app_launch'
        elif event_type == 'app_quit':
            normalized['action_type'] = 'app_quit'
        else:
            normalized['action_type'] = event_type
    
    elif source == 'office':
        if event_type == 'doc_save':
            normalized['action_type'] = 'doc_save'
        elif event_type == 'doc_open':
            normalized['action_type'] = 'doc_open'
        elif event_type == 'doc_close':
            normalized['action_type'] = 'doc_close'
        elif event_type == 'doc_focus':
            normalized['action_type'] = 'doc_focus'
        elif event_type == 'app_launch':
            normalized['action_type'] = 'app_launch'
        elif event_type == 'app_quit':
            normalized['action_type'] = 'app_quit'
        elif event_type == 'app_focus':
            normalized['action_type'] = 'app_focus'
        elif event_type == 'app_blur':
            normalized['action_type'] = 'app_blur'
        else:
            normalized['action_type'] = event_type
    else:
        normalized['action_type'] = event_type
    
    return normalized


def freshness_weight_screen_state(events):
    """Only keep screen state references that are recent (within FRESHNESS window)."""
    weighted = []
    
    for i, event in enumerate(events):
        ts = parse_timestamp(event.get('timestamp'))
        if not ts:
            weighted.append(event)
            continue
        
        event_copy = event.copy()
        ctx = event_copy.get('context', {})
        if not isinstance(ctx, dict):
            weighted.append(event_copy)
            continue
        
        screen_state = ctx.get('screen_state', {})
        if not isinstance(screen_state, dict):
            weighted.append(event_copy)
            continue
        
        fresh_state = {}
        for app_key, state in screen_state.items():
            if not isinstance(state, dict):
                continue
            state_ts_str = state.get('timestamp', '')
            state_ts = parse_timestamp(state_ts_str)
            
            if state_ts:
                age = (ts - state_ts).total_seconds()
                if age <= SCREEN_STATE_FRESHNESS_SECONDS:
                    fresh_state[app_key] = state
            else:
                # No timestamp — try to infer from recent events
                # Look backwards for the last event from this source
                for j in range(i - 1, max(-1, i - 20), -1):
                    prev = events[j]
                    prev_source = prev.get('_source', prev.get('source', ''))
                    if app_key == 'browser' and prev_source in ('chrome', 'safari'):
                        prev_ts = parse_timestamp(prev.get('timestamp'))
                        if prev_ts and (ts - prev_ts).total_seconds() <= SCREEN_STATE_FRESHNESS_SECONDS:
                            fresh_state[app_key] = state
                        break
                    elif app_key == 'terminal' and prev_source == 'shell':
                        prev_ts = parse_timestamp(prev.get('timestamp'))
                        if prev_ts and (ts - prev_ts).total_seconds() <= SCREEN_STATE_FRESHNESS_SECONDS:
                            fresh_state[app_key] = state
                        break
                    elif app_key == 'office' and prev_source == 'office':
                        prev_ts = parse_timestamp(prev.get('timestamp'))
                        if prev_ts and (ts - prev_ts).total_seconds() <= SCREEN_STATE_FRESHNESS_SECONDS:
                            fresh_state[app_key] = state
                        break
        
        event_copy.setdefault('context', {})['screen_state'] = fresh_state
        weighted.append(event_copy)
    
    return weighted


def filter_small_workflows(events, workflows):
    """Mark events belonging to workflows with < MIN_WORKFLOW_ACTIONS as low quality."""
    small_workflow_ids = set()
    for wf in workflows:
        action_count = wf.get('action_count', len(wf.get('actions', [])))
        if action_count < MIN_WORKFLOW_ACTIONS:
            small_workflow_ids.add(wf.get('id'))
    
    return small_workflow_ids