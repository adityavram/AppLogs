"""Import Chrome logs from Downloads into AppLogs log directory."""

import json
from pathlib import Path


def import_chrome_logs(filepath=None):
    if filepath:
        src = Path(filepath)
    else:
        src = Path.home() / 'Downloads' / 'chrome-events.jsonl'
    
    if not src.exists():
        print(f'No Chrome logs found at {src}')
        print('Export from the Chrome extension popup first:')
        print('  1. Click the AppLogs extension icon')
        print('  2. Click Export')
        print('  3. Run: ./applogs import-chrome')
        return 1
    
    log_dir = Path.home() / '.applogs' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    dest = log_dir / 'chrome-events.jsonl'
    
    existing_count = 0
    existing_keys = set()
    
    if dest.exists():
        with open(dest) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    key = (entry.get('timestamp', ''), entry.get('type', ''), entry.get('url', ''))
                    existing_keys.add(key)
                    existing_count += 1
                except json.JSONDecodeError:
                    continue
    
    new_count = 0
    with open(src) as f:
        with open(dest, 'a') as out:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    key = (entry.get('timestamp', ''), entry.get('type', ''), entry.get('url', ''))
                    if key not in existing_keys:
                        out.write(json.dumps(entry) + '\n')
                        existing_keys.add(key)
                        new_count += 1
                except json.JSONDecodeError:
                    continue
    
    print(f'Imported {new_count} new Chrome logs')
    print(f'Total Chrome logs: {existing_count + new_count}')
    print(f'Destination: {dest}')
    
    return 0