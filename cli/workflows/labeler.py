"""Template-based workflow labeling.

Matches detected workflows against known patterns to assign labels.
"""

import re


WORKFLOW_TEMPLATES = [
    {
        'label': 'fix_bug',
        'description': 'Read issue/PR, create branch, implement, commit, push',
        'patterns': [
            {
                'keywords': [r'issue-\d+', r'pr-\d+'],
                'app_sequence': [('browser', 'view'), ('terminal', 'shell_command')],
                'min_actions': 3,
            },
            {
                'app_sequence': [('browser', 'view'), ('terminal', 'shell_command'), ('terminal', 'shell_command')],
                'commands': [r'git\s+checkout.*-b.*fix', r'git\s+commit'],
                'min_actions': 3,
            },
        ],
    },
    {
        'label': 'deploy',
        'description': 'Build, test, push/deploy',
        'patterns': [
            {
                'commands': [r'npm\s+(run\s+)?build', r'git\s+push'],
                'min_actions': 2,
            },
            {
                'commands': [r'docker\s+build', r'docker\s+push'],
                'min_actions': 2,
            },
        ],
    },
    {
        'label': 'research_topic',
        'description': 'Search, read, ask AI, search more',
        'patterns': [
            {
                'app_sequence': [('browser', 'view'), ('browser', 'view'), ('browser', 'view')],
                'keywords': [r'search:'],
                'min_actions': 3,
            },
            {
                'app_sequence': [('browser', 'view'), ('browser', 'view')],
                'page_categories': ['search', 'ai'],
                'min_actions': 2,
            },
        ],
    },
    {
        'label': 'write_document',
        'description': 'Open Office doc, edit, save',
        'patterns': [
            {
                'app_sequence': [('word', 'edit'), ('word', 'save')],
                'min_actions': 2,
            },
            {
                'app_sequence': [('excel', 'edit'), ('excel', 'save')],
                'min_actions': 2,
            },
            {
                'app_sequence': [('powerpoint', 'edit'), ('powerpoint', 'save')],
                'min_actions': 2,
            },
        ],
    },
    {
        'label': 'review_code',
        'description': 'Browse GitHub PR/repo, possibly comment',
        'patterns': [
            {
                'keywords': [r'pr-\d+'],
                'app_sequence': [('browser', 'view'), ('browser', 'view')],
                'min_actions': 2,
            },
        ],
    },
    {
        'label': 'browse_session',
        'description': 'General browsing across multiple sites',
        'patterns': [
            {
                'app_sequence': [('browser', 'view'), ('browser', 'view'), ('browser', 'view')],
                'min_actions': 3,
            },
        ],
    },
    {
        'label': 'terminal_session',
        'description': 'General terminal work',
        'patterns': [
            {
                'app_sequence': [('terminal', 'shell_command'), ('terminal', 'shell_command')],
                'min_actions': 2,
            },
        ],
    },
    {
        'label': 'write_and_research',
        'description': 'Write document while looking things up',
        'patterns': [
            {
                'app_sequence_contains': [('word', 'edit'), ('browser', 'view')],
                'min_actions': 3,
            },
        ],
    },
]


def label_workflow(workflow):
    """Try to match a workflow against templates. Returns label + confidence or None."""
    actions = workflow.get('actions', [])
    if not actions:
        return None
    
    keywords = workflow.get('keywords', [])
    app_sequence = workflow.get('app_sequence', [])
    app_sequence_tuples = [tuple(a) if isinstance(a, list) else a for a in app_sequence]
    
    # Extract commands from shell actions
    commands = []
    for action in actions:
        if action.get('_source') == 'shell' or action.get('source') == 'shell':
            cmd = action.get('command', '')
            if cmd:
                commands.append(cmd)
    
    # Extract page categories
    page_categories = set()
    for action in actions:
        ctx = action.get('context', {})
        if isinstance(ctx, dict) and 'page_category' in ctx:
            cat = ctx.get('page_category')
            if cat:
                page_categories.add(cat)
    
    for template in WORKFLOW_TEMPLATES:
        for pattern in template['patterns']:
            if _matches(pattern, keywords, app_sequence_tuples, commands, page_categories, len(actions)):
                return {
                    'label': template['label'],
                    'description': template['description'],
                    'confidence': 'template',
                }
    
    return None


def _matches(pattern, keywords, app_sequence, commands, page_categories, action_count):
    """Check if a pattern matches the workflow."""
    if action_count < pattern.get('min_actions', 0):
        return False
    
    # Check keywords
    if 'keywords' in pattern:
        for kw_pattern in pattern['keywords']:
            matched = False
            for kw in keywords:
                if re.search(kw_pattern, str(kw)):
                    matched = True
                    break
            if not matched:
                return False
    
    # Check exact app sequence (subsequence match)
    if 'app_sequence' in pattern:
        if not _is_subsequence(pattern['app_sequence'], app_sequence):
            return False
    
    # Check app sequence contains (any order)
    if 'app_sequence_contains' in pattern:
        for required in pattern['app_sequence_contains']:
            if tuple(required) not in app_sequence:
                return False
    
    # Check commands
    if 'commands' in pattern:
        for cmd_pattern in pattern['commands']:
            matched = False
            for cmd in commands:
                if re.search(cmd_pattern, cmd):
                    matched = True
                    break
            if not matched:
                return False
    
    # Check page categories
    if 'page_categories' in pattern:
        for cat in pattern['page_categories']:
            if cat not in page_categories:
                return False
    
    return True


def _is_subsequence(pattern_seq, actual_seq):
    """Check if pattern_seq is a subsequence of actual_seq (in order, not necessarily contiguous)."""
    if not pattern_seq:
        return True
    
    idx = 0
    for actual in actual_seq:
        if idx < len(pattern_seq) and tuple(pattern_seq[idx]) == tuple(actual) if isinstance(actual, list) else pattern_seq[idx] == actual:
            idx += 1
        if idx >= len(pattern_seq):
            return True
    
    return idx >= len(pattern_seq)