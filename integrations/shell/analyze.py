#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter

LOG_FILE = Path.home() / 'AppLogs' / 'logs' / 'shell-commands.jsonl'

def analyze():
    if not LOG_FILE.exists():
        print(f'No logs found at {LOG_FILE}')
        print('Start collecting logs first!')
        return
    
    logs = []
    with open(LOG_FILE) as f:
        for line in f:
            logs.append(json.loads(line.strip()))
    
    if not logs:
        print('No logs found')
        return
    
    print(f'Total commands: {len(logs)}')
    print(f'Date range: {logs[0]["timestamp"][:10]} to {logs[-1]["timestamp"][:10]}')
    print()
    
    commands = [log['command'] for log in logs if log['type'] == 'shell_command']
    
    print('Top 10 commands:')
    cmd_counter = Counter(commands)
    for cmd, count in cmd_counter.most_common(10):
        print(f'  {count:4d}  {cmd[:80]}')
    print()
    
    print('Top 10 directories:')
    cwd_counter = Counter(log['cwd'] for log in logs if log['type'] == 'shell_command')
    for cwd, count in cwd_counter.most_common(10):
        print(f'  {count:4d}  {cwd}')
    print()
    
    failures = [log for log in logs if log['type'] == 'shell_command' and log['exit_code'] != 0]
    print(f'Failed commands: {len(failures)} ({len(failures)/len(logs)*100:.1f}%)')
    
    if failures:
        print('Recent failures:')
        for log in failures[-5:]:
            print(f'  [{log["exit_code"]}] {log["command"][:80]}')

if __name__ == '__main__':
    analyze()