"""AppLogs verification: schema, pipeline round-trip, and live checks.

Three modes:
  applogs verify schema    - validate every JSONL line against required fields
  applogs verify pipeline  - inject synthetic events, run enrich+refine, assert
                             each surfaces in enriched/training-ready with the
                             right shape (regression test for the two bugs that
                             starved the training set in July-Oct 2026)
  applogs verify live      - tail raw logs, run enrich, confirm the newest real
                             event flows into enriched output end-to-end
"""

import json
import sys
import time
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime, timezone


LOG_DIR = Path.home() / '.applogs' / 'logs'

# Required fields per source's raw events.
RAW_REQUIRED = {
    'shell':    {'timestamp', 'type', 'command', 'cwd', 'exit_code'},
    'chrome':   {'timestamp', 'type'},
    'safari':   {'timestamp', 'type'},
    'office':   {'timestamp', 'type', 'app'},
    'appfocus': {'timestamp', 'type', 'app'},
    'calendar': {'timestamp', 'type', 'title', 'event_id'},
}

RAW_FILES = {
    'shell': 'shell-commands.jsonl',
    'chrome': 'chrome-events.jsonl',
    'safari': 'safari-events.jsonl',
    'office': 'office-events.jsonl',
    'appfocus': 'appfocus-events.jsonl',
    'calendar': 'calendar-events.jsonl',
}

ENRICHED_REQUIRED = {'timestamp', 'source', 'type', 'action', 'context', 'outcome'}
CONTEXT_REQUIRED = {'recent_actions', 'focused_app', 'time_features', 'workflow_id'}
OUTCOME_REQUIRED = {'next_action_delay_s', 'retried', 'undone'}


def _ok(msg):
    print(f'  PASS  {msg}')

def _fail(msg):
    print(f'  FAIL  {msg}')

def _iso_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


# --- schema mode ---------------------------------------------------------

def verify_schema():
    print('Schema check\n' + '=' * 50)
    failures = 0
    checks = 0

    for source, fname in RAW_FILES.items():
        fpath = LOG_DIR / fname
        if not fpath.exists():
            print(f'\n[{source}] {fname}: not present (skipped)')
            continue
        required = RAW_REQUIRED[source]
        n_lines = 0
        bad = 0
        missing_field_lines = 0
        invalid_json = 0
        with open(fpath) as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                n_lines += 1
                checks += 1
                try:
                    obj = json.loads(s)
                except json.JSONDecodeError:
                    invalid_json += 1
                    bad += 1
                    continue
                if not required.issubset(obj.keys()):
                    missing_field_lines += 1
                    bad += 1
        status = 'PASS' if bad == 0 else 'FAIL'
        print(f'\n[{source}] {fname}: {n_lines} lines, {bad} bad  {status}')
        if invalid_json:
            _fail(f'{invalid_json} invalid JSON lines')
        if missing_field_lines:
            _fail(f'{missing_field_lines} lines missing required fields {required}')
        if bad == 0 and n_lines:
            _ok(f'all {n_lines} lines have required fields {sorted(required)}')
        if bad:
            failures += 1

    # Enriched + training-ready
    for fname, required in [
        ('enriched.jsonl', ENRICHED_REQUIRED),
        ('training-ready.jsonl', ENRICHED_REQUIRED),
    ]:
        fpath = LOG_DIR / fname
        if not fpath.exists():
            print(f'\n[{fname}]: not present (skipped)')
            continue
        n = 0; bad = 0; ctx_bad = 0; out_bad = 0
        with open(fpath) as f:
            for line in f:
                s = line.strip()
                if not s: continue
                n += 1; checks += 1
                try:
                    obj = json.loads(s)
                except json.JSONDecodeError:
                    bad += 1; continue
                if not required.issubset(obj.keys()):
                    bad += 1
                ctx = obj.get('context', {})
                if isinstance(ctx, dict) and not CONTEXT_REQUIRED.issubset(ctx.keys()):
                    ctx_bad += 1
                out = obj.get('outcome', {})
                if isinstance(out, dict) and not OUTCOME_REQUIRED.issubset(out.keys()):
                    out_bad += 1
        status = 'PASS' if bad == 0 and ctx_bad == 0 and out_bad == 0 else 'FAIL'
        print(f'\n[{fname}] {n} lines  {status}')
        if bad: _fail(f'{bad} lines missing top-level fields {required}')
        if ctx_bad: _fail(f'{ctx_bad} lines missing context fields {CONTEXT_REQUIRED}')
        if out_bad: _fail(f'{out_bad} lines missing outcome fields {OUTCOME_REQUIRED}')
        if bad == 0 and ctx_bad == 0 and out_bad == 0 and n:
            _ok(f'all {n} enriched triplets have context+outcome shape')
        if bad or ctx_bad or out_bad:
            failures += 1

    print('\n' + '=' * 50)
    print(f'Schema: {checks} lines checked, {"PASS" if failures == 0 else "FAIL"} ({failures} source(s) with issues)')
    return 1 if failures else 0


# --- pipeline mode -------------------------------------------------------

def _synthetic_events():
    """One synthetic event per source, with a unique marker timestamp."""
    base = '2026-10-27T23:59:'
    return [
        {'timestamp': base + '01.000Z', 'type': 'shell_command', '_source': 'shell',
         'command': 'git status', 'cwd': '/tmp', 'exit_code': 0, 'duration_ms': 50,
         'shell': 'zsh', 'session_id': 'verify', 'hostname': 'verify'},
        {'timestamp': base + '02.000Z', 'type': 'navigation', '_source': 'chrome',
         'url': 'https://example.com/verify', 'title': 'Verify'},
        {'timestamp': base + '02.500Z', 'type': 'tab_focus', '_source': 'chrome',
         'url': 'https://example.com/verify', 'title': 'Verify'},
        {'timestamp': base + '02.700Z', 'type': 'tab_blur', '_source': 'chrome',
         'url': 'https://example.com/verify', 'title': 'Verify', 'duration_ms': 200},
        {'timestamp': base + '03.000Z', 'type': 'tab_focus', '_source': 'safari',
         'url': 'https://example.com/verify-safari', 'title': 'Verify Safari'},
        {'timestamp': base + '04.000Z', 'type': 'doc_save', '_source': 'office',
         'app': 'word', 'bundle_name': 'Microsoft Word', 'doc_name': 'verify.docx', 'doc_path': '/tmp/verify.docx'},
        {'timestamp': base + '05.000Z', 'type': 'app_focus', '_source': 'appfocus',
         'app': 'Sublime Text', 'bundle_id': 'com.sublimetext.4', 'window_title': 'verify.py - /tmp'},
        # a second appfocus to create a blur with duration
        {'timestamp': base + '06.000Z', 'type': 'app_focus', '_source': 'appfocus',
         'app': 'Terminal', 'bundle_id': 'com.apple.Terminal', 'window_title': 'verify — bash'},
        {'timestamp': base + '07.000Z', 'type': 'meeting_upcoming', '_source': 'calendar',
         'title': 'standup', 'start_time': base + '08.000Z', 'end_time': base + '15.000Z',
         'event_id': 'verify-evt-1', 'calendar_name': 'Work', 'minutes_until_start': 1.0},
    ]


def verify_pipeline():
    """Run enrich+refine against synthetic fixtures in a temp log dir.

    This is the regression test that would have caught both the
    browser-action-type-collapse and the workflow-id-space-join bugs.
    """
    print('Pipeline round-trip (synthetic events)\n' + '=' * 50)
    failures = 0

    # Build a temp LOG_DIR with only synthetic events so we can reason exactly.
    with tempfile.TemporaryDirectory() as td:
        tmp_log = Path(td)
        events = _synthetic_events()
        # Write each source's file.
        by_source = {}
        for e in events:
            by_source.setdefault(e['_source'], []).append(e)
        for src, evs in by_source.items():
            fname = RAW_FILES[src]
            with open(tmp_log / fname, 'w') as f:
                for e in evs:
                    out = {k: v for k, v in e.items() if k != '_source'}
                    f.write(json.dumps(out) + '\n')

        # Monkeypatch LOG_DIR for the pipeline modules by running them in-process
        # with a patched Path.home() is hard; instead run enrich + refine via
        # subprocess with HOME set to a dir whose ~/.applogs/logs is our temp.
        # Simpler: copy temp files into a fake home and call the functions
        # directly with patched module-level LOG_DIR.
        env_home = tmp_log.parent  # we want ~/.applogs/logs -> tmp_log
        fake_home = td  # use the temp dir itself as HOME
        fake_applogs = Path(fake_home) / '.applogs' / 'logs'
        fake_applogs.mkdir(parents=True)
        for p in tmp_log.glob('*.jsonl'):
            p.replace(fake_applogs / p.name)

        # Run the pipeline in a subprocess with HOME overridden.
        py = (
            "import sys; sys.path.insert(0, %r); "
            "from enrichment.pipeline import enrich_logs; "
            "from refinement.pipeline import refine_logs; "
            "n = enrich_logs(); "
            "refine_logs(); "
            "print('ENRICHED', n)"
        ) % str(Path(__file__).parent)
        r = subprocess.run(
            ['python3', '-c', py],
            env={'HOME': str(fake_home), 'PATH': '/usr/bin:/bin:/usr/local/bin'},
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            _fail('pipeline subprocess failed')
            print(r.stderr)
            return 1
        _ok(f'enrich+refine ran on synthetic fixtures ({r.stdout.strip()})')

        enriched_path = fake_applogs / 'enriched.jsonl'
        training_path = fake_applogs / 'training-ready.jsonl'
        enriched = [json.loads(l) for l in enriched_path.read_text().splitlines() if l.strip()]
        _ok(f'enriched.jsonl: {len(enriched)} events from {len(events)} synthetic inputs')

        # Assert every synthetic event surfaced in enriched with correct shape.
        seen_sources = {e['source'] for e in enriched}
        expected_sources = {e['_source'] for e in events}
        if not expected_sources.issubset(seen_sources):
            _fail(f'sources missing from enriched: {expected_sources - seen_sources}')
            failures += 1
        else:
            _ok(f'all sources present in enriched: {sorted(seen_sources)}')

        # Shape checks on enriched entries (context + outcome required;
        # action_type is only set by refine, so it is checked on training-ready below).
        shape_fail = 0
        for e in enriched:
            if not ENRICHED_REQUIRED.issubset(e.keys()):
                shape_fail += 1; continue
            ctx = e.get('context', {})
            out = e.get('outcome', {})
            if not isinstance(ctx, dict) or not CONTEXT_REQUIRED.issubset(ctx.keys()):
                shape_fail += 1
            if not isinstance(out, dict) or not OUTCOME_REQUIRED.issubset(out.keys()):
                shape_fail += 1
        if shape_fail:
            _fail(f'{shape_fail} enriched entries failed context/outcome shape checks')
            failures += 1
        else:
            _ok(f'all {len(enriched)} enriched entries have full context+outcome shape')

        # training-ready is the refine output: it must carry action_type.
        tr = []
        if training_path.exists():
            tr = [json.loads(l) for l in training_path.read_text().splitlines() if l.strip()]
        at_fail = 0
        for e in tr:
            if not e.get('action_type'):
                at_fail += 1
        if at_fail:
            _fail(f'{at_fail} training-ready entries missing action_type')
            failures += 1
        elif tr:
            _ok(f'all {len(tr)} training-ready entries have action_type')

        # Regression: chrome tab_focus/tab_blur must map to web_focus/web_blur,
        # NOT collapse to 'web_browse' (the July-Oct 2026 bug).
        chrome_types = {e.get('action_type') for e in tr if e.get('source') == 'chrome'}
        if {'web_focus', 'web_blur'} & chrome_types:
            _ok(f'chrome action_types granular: {chrome_types}')
        elif chrome_types <= {'web_browse'}:
            _fail(f'chrome action_type collapsed to {chrome_types} (regression: tab_focus/tab_blur should be web_focus/web_blur)')
            failures += 1
        else:
            _ok(f'chrome action_types: {chrome_types}')

        # Regression: appfocus events must appear and carry app + window_title.
        af = [e for e in enriched if e.get('source') == 'appfocus']
        if not af:
            _fail('no appfocus events in enriched (source not plumbed through)')
            failures += 1
        else:
            _ok(f'appfocus events present in enriched: {len(af)}')
            if not any(e.get('window_title') for e in af):
                _fail('appfocus window_title dropped during enrichment')
                failures += 1
            else:
                _ok('appfocus window_title preserved through enrichment')

        # Regression: calendar events must appear and carry title + event_id.
        cal = [e for e in enriched if e.get('source') == 'calendar']
        if not cal:
            _fail('no calendar events in enriched (source not plumbed through)')
            failures += 1
        else:
            _ok(f'calendar events present in enriched: {len(cal)}')
            if not any(e.get('title') and e.get('event_id') for e in cal):
                _fail('calendar title or event_id dropped during enrichment')
                failures += 1
            else:
                _ok('calendar title + event_id preserved through enrichment')

        if tr:
            _ok(f'training-ready.jsonl: {len(tr)} events (workflow join works)')
        else:
            _fail('training-ready.jsonl empty (workflow membership join may be broken)')
            failures += 1

    print('\n' + '=' * 50)
    print(f'Pipeline: {"PASS" if failures == 0 else "FAIL"} ({failures} issue(s))')
    return 1 if failures else 0


# --- live mode -----------------------------------------------------------

def verify_live(timeout_s=30):
    """Watch raw logs for a new event, then confirm it reaches enriched.jsonl."""
    print(f'Live end-to-end check (waiting up to {timeout_s}s for a new event)\n' + '=' * 50)

    # Snapshot current line counts and last timestamps per source.
    before = {}
    for src, fname in RAW_FILES.items():
        fpath = LOG_DIR / fname
        if not fpath.exists():
            before[src] = (0, '')
            continue
        lines = [l for l in fpath.read_text().splitlines() if l.strip()]
        n = len(lines)
        last_ts = ''
        if lines:
            try:
                last_ts = json.loads(lines[-1]).get('timestamp', '')
            except json.JSONDecodeError:
                pass
        before[src] = (n, last_ts)
    print('Snapshot taken. Generate activity (switch apps, run a command, browse) to trigger events.')

    deadline = time.time() + timeout_s
    new_event = None
    while time.time() < deadline:
        for src, fname in RAW_FILES.items():
            fpath = LOG_DIR / fname
            if not fpath.exists():
                continue
            lines = [l for l in fpath.read_text().splitlines() if l.strip()]
            n, last_ts = before[src]
            if len(lines) > n:
                # find the first new line after our snapshot
                for l in lines[n:]:
                    s = l.strip()
                    if not s:
                        continue
                    try:
                        obj = json.loads(s)
                    except json.JSONDecodeError:
                        continue
                    if obj.get('timestamp', '') > last_ts:
                        new_event = (src, obj)
                        break
            if new_event:
                break
        if new_event:
            break
        time.sleep(1)

    if not new_event:
        _fail(f'no new raw event observed within {timeout_s}s')
        print('\nLive: FAIL (no activity detected)')
        return 1

    src, ev = new_event
    _ok(f'new raw event from {src}: type={ev.get("type")} ts={ev.get("timestamp","")[:19]}')

    # Run enrich and confirm an enriched entry with this timestamp exists.
    print('Running ./applogs enrich...')
    r = subprocess.run(
        ['python3', str(Path(__file__).parent / 'app.py'), 'enrich'],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        _fail(f'enrich failed: {r.stderr.strip()}')
        return 1
    enriched_path = LOG_DIR / 'enriched.jsonl'
    target_ts = ev.get('timestamp', '')
    found = False
    if enriched_path.exists():
        for l in enriched_path.read_text().splitlines():
            s = l.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except json.JSONDecodeError:
                continue
            if obj.get('timestamp') == target_ts and obj.get('source') == src:
                found = True
                if ENRICHED_REQUIRED.issubset(obj.keys()) and isinstance(obj.get('context'), dict):
                    _ok(f'event reached enriched.jsonl with full shape (action_type={obj.get("action_type")})')
                else:
                    _fail('event reached enriched.jsonl but missing context/shape')
                    return 1
                break
    if not found:
        _fail(f'raw event (ts={target_ts}) did NOT appear in enriched.jsonl after enrich')
        print('\nLive: FAIL')
        return 1

    print('\nLive: PASS')
    return 0


def run_verify(mode='schema'):
    if mode == 'schema':
        return verify_schema()
    elif mode == 'pipeline':
        return verify_pipeline()
    elif mode == 'live':
        return verify_live()
    print(f'Unknown verify mode: {mode}')
    print('Usage: applogs verify [schema|pipeline|live]')
    return 1


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'schema'
    sys.exit(run_verify(mode))