"""Workflow quality scoring and refinement pipeline.

Scores each workflow as high/medium/low based on:
- Action diversity (different action types within workflow)
- Cross-source activity (events from multiple sources)
- Outcome signals (exit codes, retries, saves)
- Duration and temporal spread
"""

import json
import re
from pathlib import Path
from datetime import datetime
from collections import Counter

from refinement.quality import (
    deduplicate_events, filter_noise, normalize_action,
    freshness_weight_screen_state, parse_timestamp
)


LOG_DIR = Path.home() / '.applogs' / 'logs'
ENRICHED_FILE = LOG_DIR / 'enriched.jsonl'
WORKFLOWS_FILE = LOG_DIR / 'workflows.json'
TRAINING_READY_FILE = LOG_DIR / 'training-ready.jsonl'
REFINEMENT_REPORT_FILE = LOG_DIR / 'refinement-report.json'


def score_workflow(workflow):
    """Score a workflow's quality. Returns (score 0-1, quality_tier, reasons)."""
    actions = workflow.get('actions', [])
    if not actions:
        return 0.0, 'low', ['no actions']
    
    reasons = []
    score = 0.0
    
    # 1. Action count (0-0.2)
    count = len(actions)
    if count >= 10:
        score += 0.2
        reasons.append('good action count')
    elif count >= 5:
        score += 0.15
        reasons.append('moderate action count')
    elif count >= 3:
        score += 0.1
        reasons.append('minimum action count')
    else:
        reasons.append('too few actions')
    
    # 2. Source diversity (0-0.25)
    sources = set(a.get('_source', a.get('source', '')) for a in actions)
    if len(sources) >= 3:
        score += 0.25
        reasons.append(f'multi-source ({", ".join(sources)})')
    elif len(sources) == 2:
        score += 0.15
        reasons.append(f'cross-source ({", ".join(sources)})')
    else:
        reasons.append(f'single source ({", ".join(sources) if sources else "none"})')
    
    # 3. Action type diversity (0-0.2)
    action_types = set()
    for a in actions:
        source = a.get('_source', a.get('source', ''))
        etype = a.get('type', '')
        if source == 'shell':
            cmd = a.get('command', '')
            if re.match(r'^git\s+(push|commit|checkout|merge)', cmd):
                action_types.add('vcs')
            elif re.match(r'^npm|python|docker', cmd):
                action_types.add('build_run')
            elif re.match(r'^cat|ls|tail|grep|find', cmd):
                action_types.add('inspect')
            else:
                action_types.add('shell_other')
        elif source in ('chrome', 'safari'):
            action_types.add('browse')
        elif source == 'office':
            action_types.add('office')
    
    if len(action_types) >= 3:
        score += 0.2
        reasons.append(f'diverse actions ({", ".join(action_types)})')
    elif len(action_types) == 2:
        score += 0.1
        reasons.append(f'mixed actions ({", ".join(action_types)})')
    else:
        reasons.append('homogeneous actions')
    
    # 4. Outcome signals (0-0.2)
    has_outcome = False
    for a in actions:
        outcome = a.get('outcome', {})
        if outcome.get('exit_code') is not None and outcome.get('exit_code') != 0:
            score += 0.1
            reasons.append('has failures (signal)')
            has_outcome = True
            break
        if outcome.get('retried') or outcome.get('undone'):
            score += 0.1
            reasons.append('has retry/undo signal')
            has_outcome = True
            break
    
    # Check for saves (office)
    for a in actions:
        if a.get('type') == 'doc_save':
            score += 0.1
            reasons.append('has document saves')
            has_outcome = True
            break
    
    if not has_outcome:
        reasons.append('no outcome signals')
    
    # 5. Temporal spread (0-0.15)
    timestamps = [parse_timestamp(a.get('timestamp', '')) for a in actions]
    valid_ts = [t for t in timestamps if t]
    if len(valid_ts) >= 2:
        duration = (max(valid_ts) - min(valid_ts)).total_seconds()
        if duration >= 60:
            score += 0.15
            reasons.append(f'sustained activity ({duration:.0f}s)')
        elif duration >= 15:
            score += 0.1
            reasons.append(f'moderate duration ({duration:.0f}s)')
        else:
            reasons.append(f'brief ({duration:.0f}s)')
    else:
        reasons.append('insufficient timestamps')
    
    # Determine quality tier
    if score >= 0.6:
        tier = 'high'
    elif score >= 0.35:
        tier = 'medium'
    else:
        tier = 'low'
    
    return round(score, 2), tier, reasons


def refine_logs(use_llm=False):
    """Full refinement pipeline. Returns refinement report."""
    from workflows.detector import detect_workflows, workflows_to_json
    from workflows.labeler import label_workflow
    from workflows.annotator import check_ollama, annotate_workflow
    from enrichment.pipeline import load_all_raw_logs, extract_action_summary, \
        extract_time_features, infer_focused_app, find_cross_source_context, \
        build_screen_state, detect_retry, detect_undo, get_next_action_delay, \
        assign_workflow_ids, classify_page
    
    report = {
        'started_at': datetime.now().isoformat(),
        'steps': [],
    }
    
    # 1. Load raw logs
    raw_logs = load_all_raw_logs()
    report['raw_event_count'] = len(raw_logs)
    report['steps'].append(f'Loaded {len(raw_logs)} raw events')
    
    # 2. Deduplicate
    deduped = deduplicate_events(raw_logs)
    report['deduped_event_count'] = len(deduped)
    report['deduped_removed'] = len(raw_logs) - len(deduped)
    report['steps'].append(f'Deduplicated: removed {len(raw_logs) - len(deduped)} duplicates')
    
    # 3. Filter noise
    filtered = filter_noise(deduped)
    report['filtered_event_count'] = len(filtered)
    report['noise_removed'] = len(deduped) - len(filtered)
    report['steps'].append(f'Filtered noise: removed {len(deduped) - len(filtered)} noise events')
    
    # 4. Normalize actions
    normalized = [normalize_action(e) for e in filtered]
    report['steps'].append(f'Normalized actions for {len(normalized)} events')
    
    # 5. Enrich (inline, same as enrichment pipeline)
    logs = assign_workflow_ids(normalized)
    
    enriched = []
    recent_window = []
    
    for i, entry in enumerate(logs):
        future_actions = logs[i+1:i+10]
        
        context = {
            'recent_actions': [
                {
                    'source': a.get('_source'),
                    'type': a.get('type'),
                    'summary': extract_action_summary(a),
                    'timestamp': a.get('timestamp', ''),
                }
                for a in recent_window[-10:]
            ],
            'focused_app': infer_focused_app(entry, recent_window),
            'time_features': extract_time_features(entry.get('timestamp')),
            'workflow_id': entry.get('_workflow_id'),
            'cross_source': find_cross_source_context(entry, logs, i),
            'screen_state': build_screen_state(recent_window),
        }
        
        if entry.get('_source') in ('chrome', 'safari'):
            url = entry.get('url', '')
            if url:
                context['page_category'] = classify_page(url)
        
        outcome = {
            'exit_code': entry.get('exit_code'),
            'duration_ms': entry.get('duration_ms') or entry.get('duration_s'),
            'next_action_delay_s': get_next_action_delay(entry, future_actions),
            'retried': detect_retry(entry, future_actions),
            'undone': detect_undo(entry, future_actions),
        }
        
        enriched_entry = {
            'timestamp': entry.get('timestamp'),
            'source': entry.get('_source'),
            'type': entry.get('type'),
            'action': extract_action_summary(entry),
            'action_type': entry.get('action_type', ''),
            'context': context,
            'outcome': outcome,
        }
        
        for key in ('command', 'cwd', 'url', 'title', 'app', 'doc_name', 'doc_path',
                     'from_url', 'duration_ms', 'duration_s', 'exit_code'):
            if key in entry:
                enriched_entry[key] = entry[key]
        
        enriched.append(enriched_entry)
        recent_window.append(entry)
    
    # 6. Freshness-weight screen state
    enriched = freshness_weight_screen_state(enriched)
    report['steps'].append(f'Freshness-weighted screen state for {len(enriched)} events')
    
    # 7. Detect workflows
    workflows = detect_workflows(enriched, gap_seconds=300)
    report['workflow_count'] = len(workflows)
    report['steps'].append(f'Detected {len(workflows)} workflows')
    
    # 8. Label workflows (template + LLM)
    for wf in workflows:
        result = label_workflow(wf)
        if result:
            wf['label'] = result['label']
            wf['description'] = result['description']
        else:
            wf['label'] = 'unknown'
            wf['description'] = ''
    
    if use_llm and check_ollama():
        for wf in workflows:
            if wf.get('action_count', len(wf.get('actions', []))) >= 3:
                wf_json = {
                    'action_summaries': workflows_to_json([wf])[0]['action_summaries'],
                    'keywords': wf.get('keywords', []),
                    'app_sequence': wf.get('app_sequence', []),
                }
                result = annotate_workflow(wf_json)
                if result:
                    wf['annotation'] = result
                    if wf.get('label') == 'unknown':
                        wf['label'] = result.get('workflow_label', 'unknown')
                        wf['description'] = result.get('intent', '')
        report['steps'].append('LLM annotation applied')
    
    # 9. Score workflow quality
    quality_distribution = {'high': 0, 'medium': 0, 'low': 0}
    for wf in workflows:
        score, tier, reasons = score_workflow(wf)
        wf['quality_score'] = score
        wf['quality_tier'] = tier
        wf['quality_reasons'] = reasons
        quality_distribution[tier] += 1
    
    report['quality_distribution'] = quality_distribution
    report['steps'].append(
        f'Quality: {quality_distribution["high"]} high, '
        f'{quality_distribution["medium"]} medium, '
        f'{quality_distribution["low"]} low'
    )
    
    # 10. Build training-ready set (only high + medium)
    high_medium_workflows = [wf for wf in workflows if wf['quality_tier'] in ('high', 'medium')]
    high_medium_ids = set(wf['id'] for wf in high_medium_workflows)
    
    training_ready = []
    for entry in enriched:
        wf_id = entry.get('context', {}).get('workflow_id')
        if wf_id in high_medium_ids:
            training_ready.append(entry)
    
    report['training_ready_count'] = len(training_ready)
    report['training_ready_workflows'] = len(high_medium_workflows)
    report['steps'].append(
        f'Training-ready: {len(training_ready)} events from '
        f'{len(high_medium_workflows)} workflows'
    )
    
    # 11. Write outputs
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(TRAINING_READY_FILE, 'w') as f:
        for entry in training_ready:
            f.write(json.dumps(entry, default=str) + '\n')
    
    report['finished_at'] = datetime.now().isoformat()
    report['output_file'] = str(TRAINING_READY_FILE)
    
    with open(REFINEMENT_REPORT_FILE, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    return report