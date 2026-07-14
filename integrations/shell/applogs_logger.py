#!/usr/bin/env python3
import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

APPLOGS_DIR = os.environ.get('APPLOGS_DIR', str(Path.home() / 'AppLogs'))
LOG_FILE = Path(APPLOGS_DIR) / 'logs' / 'shell-commands.jsonl'

def log_command(command, cwd, exit_code, duration_ms):
    entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'type': 'shell_command',
        'command': command,
        'cwd': cwd,
        'exit_code': exit_code,
        'duration_ms': duration_ms,
        'shell': os.environ.get('SHELL', '/bin/bash').split('/')[-1],
        'session_id': os.environ.get('APPLOGS_SESSION_ID', 'unknown'),
        'hostname': os.uname().nodename
    }
    
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')

def log_git_operation(operation):
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=2
        )
        branch = result.stdout.strip() if result.returncode == 0 else 'unknown'
        
        result = subprocess.run(
            ['git', 'config', '--get', 'remote.origin.url'],
            capture_output=True,
            text=True,
            timeout=2
        )
        remote = result.stdout.strip() if result.returncode == 0 else ''
        
        entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'type': 'git_operation',
            'operation': operation,
            'branch': branch,
            'remote': remote,
            'cwd': os.getcwd(),
            'session_id': os.environ.get('APPLOGS_SESSION_ID', 'unknown'),
            'hostname': os.uname().nodename
        }
        
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        print(f'[AppLogs] Error logging git operation: {e}', file=sys.stderr)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: applogs-logger <command> | git <operation>', file=sys.stderr)
        sys.exit(1)
    
    if sys.argv[1] == 'git' and len(sys.argv) >= 3:
        log_git_operation(sys.argv[2])
    else:
        print('Unknown command', file=sys.stderr)
        sys.exit(1)