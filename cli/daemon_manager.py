"""Manage AppLogs daemons (Safari, Office). Shell and Chrome don't need daemons."""

import subprocess
from pathlib import Path

LAUNCH_AGENTS = {
    'safari': 'com.applogs.safari',
    'office': 'com.applogs.office',
}

PLIST_PATHS = {
    'safari': Path.home() / 'Library' / 'LaunchAgents' / 'com.applogs.safari.plist',
    'office': Path.home() / 'Library' / 'LaunchAgents' / 'com.applogs.office.plist',
}

DAEMON_SCRIPTS = {
    'safari': 'integrations/safari/daemon.py',
    'office': 'integrations/office/daemon.py',
}


def start_daemon(name, project_root):
    """Start a single daemon."""
    if name in ('shell', 'chrome'):
        print(f'  {name.capitalize()}: no daemon needed (runs via shell hooks / browser extension)')
        return 0
    
    if name not in LAUNCH_AGENTS:
        print(f'Unknown integration: {name}')
        return 1
    
    label = LAUNCH_AGENTS[name]
    plist = PLIST_PATHS[name]
    
    # Check if already running
    result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
    if label in result.stdout:
        print(f'  {name.capitalize()}: already running')
        return 0
    
    # Try via LaunchAgent plist if installed
    if plist.exists():
        subprocess.run(['launchctl', 'load', str(plist)], capture_output=True)
        print(f'  {name.capitalize()}: started via LaunchAgent')
        return 0
    
    # Fall back to running directly in background
    daemon_path = project_root / DAEMON_SCRIPTS[name]
    if not daemon_path.exists():
        print(f'  {name.capitalize()}: daemon not found at {daemon_path}')
        return 1
    
    log_file = f'/tmp/applogs-{name}.log'
    error_file = f'/tmp/applogs-{name}.error.log'
    
    proc = subprocess.Popen(
        ['python3', str(daemon_path)],
        stdout=open(log_file, 'a'),
        stderr=open(error_file, 'a'),
        start_new_session=True,
    )
    print(f'  {name.capitalize()}: started (PID {proc.pid}, background)')
    return 0


def stop_daemon(name):
    """Stop a single daemon."""
    if name in ('shell', 'chrome'):
        print(f'  {name.capitalize()}: no daemon to stop (runs via shell hooks / browser extension)')
        return 0
    
    if name not in LAUNCH_AGENTS:
        print(f'Unknown integration: {name}')
        return 1
    
    label = LAUNCH_AGENTS[name]
    plist = PLIST_PATHS[name]
    
    # Try via LaunchAgent
    if plist.exists():
        subprocess.run(['launchctl', 'unload', str(plist)], capture_output=True)
    
    # Kill any running instances
    subprocess.run(['pkill', '-f', DAEMON_SCRIPTS[name]], capture_output=True)
    print(f'  {name.capitalize()}: stopped')
    return 0


def start_daemons(name, project_root):
    """Start one or all daemons."""
    if name == 'all':
        print('Starting AppLogs daemons...\n')
        for n in ['shell', 'chrome', 'safari', 'office']:
            start_daemon(n, project_root)
        print('\nRun ./applogs status to verify')
        return 0
    else:
        print(f'Starting {name}...\n')
        return start_daemon(name, project_root)


def stop_daemons(name):
    """Stop one or all daemons."""
    if name == 'all':
        print('Stopping AppLogs daemons...\n')
        for n in ['shell', 'chrome', 'safari', 'office']:
            stop_daemon(n)
        print('\nAll daemons stopped')
        return 0
    else:
        print(f'Stopping {name}...\n')
        return stop_daemon(name)