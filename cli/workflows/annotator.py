"""Ollama LLM annotation module.

Uses local Ollama to semantically annotate workflows and individual actions.
All processing is local — no data leaves the machine.
"""

import json
import re
import subprocess
import urllib.request
import urllib.error
from pathlib import Path


OLLAMA_URL = 'http://localhost:11434/api/generate'
DEFAULT_MODEL = 'llama3.2'

WORKFLOW_PROMPT = """Analyze this user activity sequence and return a JSON annotation. Output ONLY the JSON, no other text.

User actions:
{actions}

Keywords: {keywords}
App flow: {app_sequence}

Return this JSON format exactly:
{{"workflow_label": "short_label", "intent": "one sentence description", "satisfaction": 0.5, "complexity": "medium"}}"""

ACTION_PROMPT = """You are a behavior analysis assistant. Annotate this single user action in context.

Action: {action}
Source: {source}
Context: {context}
Outcome: {outcome}

Respond with ONLY valid JSON (no markdown, no explanation):
{{
  "action_type": "normalized type like vcs_commit, file_edit, web_search, web_browse, doc_write, doc_read, app_switch, deploy, test, build, debug, research, communicate",
  "intent": "what the user intended in a few words",
  "semantic_value": "low|medium|high (how informative is this action for understanding user behavior)"
}}"""


def check_ollama():
    """Check if Ollama is running."""
    try:
        req = urllib.request.Request(OLLAMA_URL.replace('/api/generate', '/api/tags'), method='GET')
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, Exception):
        return False


def call_ollama(prompt, model=DEFAULT_MODEL, timeout=30):
    """Call Ollama generate API, return response text."""
    data = json.dumps({
        'model': model,
        'prompt': prompt,
        'stream': False,
        'options': {'temperature': 0.1},
    }).encode('utf-8')
    
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result.get('response', '').strip()
    except urllib.error.URLError as e:
        return None
    except Exception as e:
        return None


def parse_llm_json(response):
    """Parse JSON from LLM response, handling common formatting issues."""
    if not response:
        return None
    
    # Strip markdown code fences if present
    clean = response.strip()
    if clean.startswith('```'):
        lines = clean.split('\n')
        clean = '\n'.join(l for l in lines if not l.startswith('```'))
    
    # Try direct parse first
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON object
    start = clean.find('{')
    end = clean.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(clean[start:end+1])
        except json.JSONDecodeError:
            pass
    
    # Try fixing common issues (trailing commas, etc.)
    if start >= 0 and end > start:
        fragment = clean[start:end+1]
        fragment = re.sub(r',\s*}', '}', fragment)
        fragment = re.sub(r',\s*]', ']', fragment)
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            pass
    
    return None


def annotate_workflow(workflow, model=DEFAULT_MODEL):
    """Use LLM to annotate a workflow. Returns dict with label, intent, satisfaction, complexity."""
    actions_text = '\n'.join([
        f'  {i+1}. [{a.get("source", a.get("_source", "?"))}] {a.get("summary", a.get("action", "?"))}'
        for i, a in enumerate(workflow.get('action_summaries', workflow.get('actions', [])))
    ])
    
    keywords = ', '.join(workflow.get('keywords', [])) or 'none'
    app_sequence = ' -> '.join([
        f'{a[0]}:{a[1]}' if isinstance(a, list) else f'{a[0]}:{a[1]}'
        for a in workflow.get('app_sequence', [])
    ]) or 'none'
    
    prompt = WORKFLOW_PROMPT.format(
        actions=actions_text,
        keywords=keywords,
        app_sequence=app_sequence,
    )
    
    response = call_ollama(prompt, model=model)
    return parse_llm_json(response)


def annotate_action(entry, model=DEFAULT_MODEL):
    """Use LLM to annotate a single action. Returns dict with action_type, intent, semantic_value."""
    action = entry.get('action', entry.get('command', entry.get('url', entry.get('type', '?'))))
    source = entry.get('source', entry.get('_source', '?'))
    
    context = entry.get('context', {})
    context_str = json.dumps({
        'focused_app': context.get('focused_app'),
        'page_category': context.get('page_category'),
        'screen_state': context.get('screen_state'),
    }) if context else '{}'
    
    outcome = entry.get('outcome', {})
    outcome_str = json.dumps(outcome) if outcome else '{}'
    
    prompt = ACTION_PROMPT.format(
        action=action,
        source=source,
        context=context_str,
        outcome=outcome_str,
    )
    
    response = call_ollama(prompt, model=model, timeout=15)
    return parse_llm_json(response)