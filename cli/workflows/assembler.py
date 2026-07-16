"""Training data assembler.

Combines enriched logs + workflow detection + annotation into ML-ready training format.
Output: ~/.applogs/logs/training.jsonl
"""

import json
from pathlib import Path
from datetime import datetime


LOG_DIR = Path.home() / '.applogs' / 'logs'
ENRICHED_FILE = LOG_DIR / 'enriched.jsonl'
TRAINING_FILE = LOG_DIR / 'training.jsonl'
WORKFLOWS_FILE = LOG_DIR / 'workflows.json'


def load_enriched():
    """Load enriched logs."""
    if not ENRICHED_FILE.exists():
        return []
    
    logs = []
    with open(ENRICHED_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return logs


def assemble_training_data(workflows, enriched_logs, use_llm=False):
    """Assemble training data from enriched logs and detected workflows.
    
    Each training example is a state-action-outcome triplet with workflow context.
    """
    # Build a lookup from timestamp to workflow
    ts_to_workflow = {}
    for wf in workflows:
        for action in wf.get('actions', []):
            ts = action.get('timestamp', '')
            if ts:
                ts_to_workflow[ts] = wf
    
    training_examples = []
    
    for entry in enriched_logs:
        ts = entry.get('timestamp', '')
        wf = ts_to_workflow.get(ts)
        
        # Base training example
        example = {
            'timestamp': ts,
            'source': entry.get('source'),
            'type': entry.get('type'),
            'action': entry.get('action'),
            'state': {
                'context': entry.get('context', {}),
                'time_features': entry.get('context', {}).get('time_features', {}),
                'screen_state': entry.get('context', {}).get('screen_state', {}),
            },
            'action_details': {},
            'outcome': entry.get('outcome', {}),
        }
        
        # Add source-specific details
        for key in ('command', 'cwd', 'url', 'title', 'app', 'doc_name', 'doc_path'):
            if key in entry:
                example['action_details'][key] = entry[key]
        
        # Add workflow context
        if wf:
            example['workflow'] = {
                'id': wf.get('id'),
                'label': wf.get('label', 'unknown'),
                'intent': wf.get('intent', ''),
                'position_in_workflow': _position_in_workflow(entry, wf),
                'workflow_length': wf.get('action_count', len(wf.get('actions', []))),
            }
        else:
            example['workflow'] = {
                'id': None,
                'label': 'unknown',
                'intent': '',
                'position_in_workflow': 0,
                'workflow_length': 0,
            }
        
        # Add annotation if available
        annotation = wf.get('annotation') if wf else None
        if annotation:
            example['workflow']['satisfaction'] = annotation.get('satisfaction')
            example['workflow']['complexity'] = annotation.get('complexity')
            example['workflow']['llm_label'] = annotation.get('workflow_label')
            example['workflow']['llm_intent'] = annotation.get('intent')
        
        action_annotation = entry.get('_action_annotation')
        if action_annotation:
            example['action_annotation'] = action_annotation
        
        training_examples.append(example)
    
    return training_examples


def _position_in_workflow(entry, workflow):
    """Get the position of this action within its workflow (0-indexed)."""
    actions = workflow.get('actions', [])
    ts = entry.get('timestamp', '')
    for i, a in enumerate(actions):
        if a.get('timestamp', '') == ts:
            return i
    return 0


def write_training_data(examples):
    """Write training examples to JSONL."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRAINING_FILE, 'w') as f:
        for example in examples:
            f.write(json.dumps(example) + '\n')
    
    return len(examples)


def write_workflows(workflows):
    """Write annotated workflows to JSON file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    serializable = []
    for wf in workflows:
        serializable.append({
            'id': wf.get('id'),
            'start_ts': _serialize_ts(wf.get('start_ts')),
            'end_ts': _serialize_ts(wf.get('end_ts')),
            'action_count': wf.get('action_count', len(wf.get('actions', []))),
            'keywords': list(wf.get('keywords', [])),
            'app_sequence': [list(a) if not isinstance(a, list) else a for a in wf.get('app_sequence', [])],
            'action_summaries': wf.get('action_summaries', []),
            'label': wf.get('label'),
            'description': wf.get('description'),
            'annotation': wf.get('annotation'),
        })
    
    with open(WORKFLOWS_FILE, 'w') as f:
        json.dump(serializable, f, indent=2, default=str)


def _serialize_ts(ts):
    """Serialize a timestamp that might be a datetime or string."""
    if ts is None:
        return None
    if hasattr(ts, 'isoformat'):
        return ts.isoformat()
    return str(ts)