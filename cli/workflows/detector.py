"""Workflow detector v2: content continuity + app-transition patterns.

Builds on Phase 1's temporal clustering (5-min gap) by adding:
1. Content continuity — links actions that reference the same topic/issue/file
2. App-transition patterns — recognizes meaningful cross-app flows
3. Intent boundaries — workflow ends when focus shifts to unrelated context
"""

import re
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict


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


def extract_keywords(entry):
    """Extract content identifiers from an event (issue numbers, branch names, file names, search queries)."""
    keywords = set()
    source = entry.get('_source', '')
    text = ''
    
    if source == 'shell':
        text = entry.get('command', '')
        # Extract git branch references
        branch_match = re.search(r'git\s+\w+\s+(-b\s+)?([\w/\-\.]+)', text)
        if branch_match:
            keywords.add(branch_match.group(2))
        # Extract file paths
        for match in re.finditer(r'[\w\-/]+\.\w+', text):
            keywords.add(match.group(0).split('/')[-1])
    elif source in ('chrome', 'safari'):
        url = entry.get('url', '')
        title = entry.get('title', '')
        text = f'{url} {title}'
        # Extract issue/PR numbers from URLs
        issue_match = re.search(r'/issues/(\d+)', url)
        if issue_match:
            keywords.add(f'issue-{issue_match.group(1)}')
        pr_match = re.search(r'/pull/(\d+)', url)
        if pr_match:
            keywords.add(f'pr-{pr_match.group(1)}')
        # Extract search queries
        q_match = re.search(r'[?&]q=([^&]+)', url)
        if q_match:
            query = q_match.group(1).replace('+', ' ').lower()
            keywords.add(f'search:{query[:30]}')
    elif source == 'office':
        doc = entry.get('doc_name', '')
        if doc:
            keywords.add(doc.lower().rsplit('.', 1)[0])
    
    return keywords


def extract_app_transition(entry):
    """Get the app-transition signature of an event."""
    source = entry.get('_source', '?')
    event_type = entry.get('type', '?')
    
    if source == 'shell':
        return ('terminal', event_type)
    elif source in ('chrome', 'safari'):
        if event_type in ('navigation', 'tab_focus'):
            return ('browser', 'view')
        return ('browser', event_type)
    elif source == 'office':
        app = entry.get('app', 'office')
        if event_type in ('doc_open', 'doc_focus'):
            return (app, 'edit')
        elif event_type == 'doc_save':
            return (app, 'save')
        return (app, event_type)
    return (source, event_type)


def detect_workflows(logs, gap_seconds=300):
    """Detect workflows using temporal + content continuity + app transitions.
    
    Returns list of workflows, each a dict with:
    - id, start_ts, end_ts, actions, keywords, app_sequence, label (to be filled later)
    """
    if not logs:
        return []
    
    workflows = []
    current = {
        'id': 0,
        'start_ts': parse_timestamp(logs[0].get('timestamp')),
        'end_ts': parse_timestamp(logs[0].get('timestamp')),
        'actions': [],
        'keywords': set(),
        'app_sequence': [],
    }
    
    for entry in logs:
        ts = parse_timestamp(entry.get('timestamp'))
        if not ts:
            continue
        
        entry_keywords = extract_keywords(entry)
        entry_app = extract_app_transition(entry)
        
        # Check if this action belongs in the current workflow
        gap = (ts - current['end_ts']).total_seconds() if current['end_ts'] else 0
        
        # Content continuity: does this share keywords with current workflow?
        current_keywords = current['keywords'] if isinstance(current['keywords'], set) else set(current['keywords'])
        shares_keywords = bool(entry_keywords & current_keywords)
        
        # Temporal gap: within 5 minutes
        within_gap = gap <= gap_seconds
        
        # Intent boundary: focus shifted to completely different domain
        # (e.g., went from coding to watching YouTube)
        if within_gap and not shares_keywords:
            # Check if the app transition makes sense
            # Allow browser->terminal (reading issue -> implementing fix)
            # Allow terminal->browser (running command -> checking result)
            # But browser(video) -> browser(code) might be a new workflow
            last_app = current['app_sequence'][-1] if current['app_sequence'] else None
            if last_app and entry_app:
                # Same source type, different content domain = probably new workflow
                if last_app[0] == entry_app[0] and last_app != entry_app:
                    # Check page category change
                    prev_cat = _get_category(current['actions'][-1]) if current['actions'] else None
                    curr_cat = _get_category(entry)
                    if prev_cat and curr_cat and prev_cat != curr_cat:
                        # Different page category in same browser = new workflow
                        _close_workflow(workflows, current)
                        current = _new_workflow(workflows, current, entry, ts, entry_keywords, entry_app)
                        continue
        
        if not within_gap and not shares_keywords:
            # New workflow
            _close_workflow(workflows, current)
            current = _new_workflow(workflows, current, entry, ts, entry_keywords, entry_app)
        else:
            # Same workflow
            current['end_ts'] = ts
            current['actions'].append(entry)
            current['keywords'].update(entry_keywords)
            current['app_sequence'].append(entry_app)
    
    _close_workflow(workflows, current)
    return workflows


def _get_category(entry):
    """Extract page category from enriched entry context or URL."""
    if isinstance(entry, dict):
        ctx = entry.get('context', {})
        if isinstance(ctx, dict) and 'page_category' in ctx:
            return ctx.get('page_category')
    return None


def _close_workflow(workflows, current):
    """Close the current workflow and add it to the list."""
    if current and current['actions']:
        wf_copy = dict(current)
        wf_copy['keywords'] = list(current['keywords'])
        workflows.append(wf_copy)


def _new_workflow(workflows, current, entry, ts, keywords, app):
    """Start a new workflow."""
    return {
        'id': current['id'] + 1 if current else 0,
        'start_ts': ts,
        'end_ts': ts,
        'actions': [entry],
        'keywords': set(keywords) if not isinstance(keywords, set) else keywords,
        'app_sequence': [app],
    }


def workflows_to_json(workflows):
    """Convert workflows to JSON-serializable format."""
    result = []
    for wf in workflows:
        result.append({
            'id': wf['id'],
            'start_ts': wf['start_ts'].isoformat() if wf['start_ts'] else None,
            'end_ts': wf['end_ts'].isoformat() if wf['end_ts'] else None,
            'action_count': len(wf['actions']),
            'keywords': wf.get('keywords', []),
            'app_sequence': [list(a) for a in wf.get('app_sequence', [])],
            'action_summaries': [
                {
                    'source': a.get('_source', a.get('source', '?')),
                    'type': a.get('type', '?'),
                    'summary': a.get('action', _summarize(a)),
                }
                for a in wf['actions']
            ],
        })
    return result


def _summarize(entry):
    """Fallback summary for raw entries."""
    source = entry.get('_source', entry.get('source', '?'))
    if source == 'shell':
        return entry.get('command', '?')[:60]
    elif source in ('chrome', 'safari'):
        return entry.get('url', '?')[:60]
    elif source == 'office':
        return f"{entry.get('app', '?')}: {entry.get('doc_name', '')}"
    return entry.get('type', '?')