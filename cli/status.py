"""Show integration status and log statistics."""

import subprocess
from pathlib import Path
from query import load_logs, SOURCE_FILES
import json


def show_status():
    log_dir = Path.home() / '.applogs' / 'logs'
    
    print('AppLogs Status')
    print('=' * 50)
    print()
    
    # Check shell integration
    shell_rc = _find_shell_rc()
    shell_active = False
    if shell_rc and shell_rc.exists():
        shell_active = 'applogs.sh' in shell_rc.read_text()
    
    shell_logs = load_logs(source='shell')
    print(f'  Shell Integration: {"ACTIVE" if shell_active else "NOT INSTALLED"}')
    print(f'    Logs: {len(shell_logs)} entries')
    if shell_logs:
        last = shell_logs[-1]
        print(f'    Last: {last.get("timestamp", "?")[:19]}  {last.get("command", "?")[:40]}')
    print()
    
    # Check chrome integration
    chrome_logs = load_logs(source='chrome')
    print(f'  Chrome Integration: {"ACTIVE (logs present)" if chrome_logs else "CHECK BROWSER"}')
    print(f'    Logs: {len(chrome_logs)} entries')
    if chrome_logs:
        last = chrome_logs[-1]
        print(f'    Last: {last.get("timestamp", "?")[:19]}  {last.get("type", "?")}  {last.get("url", "?")[:40]}')
    print()
    
    # Check office integration
    office_logs = load_logs(source='office')
    launchctl = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
    office_daemon = 'com.applogs.office' in launchctl.stdout if launchctl.returncode == 0 else False
    print(f'  Office Integration: {"ACTIVE" if office_daemon else "NOT INSTALLED"}')
    print(f'    Logs: {len(office_logs)} entries')
    if office_logs:
        last = office_logs[-1]
        print(f'    Last: {last.get("timestamp", "?")[:19]}  {last.get("type", "?")}  {last.get("app", "?")}')
    print()
    
    # Log directory
    print(f'  Log directory: {log_dir}')
    if log_dir.exists():
        for f in log_dir.glob('*.jsonl'):
            size = f.stat().st_size
            print(f'    {f.name}: {size:,} bytes')
    else:
        print('    (not created yet)')
    print()
    
    if not shell_active and not chrome_logs:
        print('No integrations active. Run: applogs install all')
    
    return 0


def _find_shell_rc():
    import os
    shell = os.environ.get('SHELL', '/bin/bash')
    shell_name = os.path.basename(shell)
    
    if 'zsh' in shell_name:
        return Path.home() / '.zshrc'
    elif 'bash' in shell_name:
        return Path.home() / '.bashrc'
    else:
        return Path.home() / '.profile'