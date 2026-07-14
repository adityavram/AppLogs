"""AppLogs CLI - Understand your behavior on your computer."""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime, timedelta

from install import install_integration, uninstall_integration
from query import query_logs, print_logs
from analyze import analyze_logs, print_analysis
from status import show_status
from timeline import show_timeline
from importer import import_chrome_logs


def main():
    parser = argparse.ArgumentParser(
        prog='applogs',
        description='Understand your behavior on your computer.',
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # install
    install_parser = subparsers.add_parser('install', help='Install an integration')
    install_parser.add_argument('integration', choices=['chrome', 'safari', 'shell', 'office', 'all'], help='Which integration to install')
    
    # uninstall
    uninstall_parser = subparsers.add_parser('uninstall', help='Uninstall an integration')
    uninstall_parser.add_argument('integration', choices=['chrome', 'safari', 'shell', 'office', 'all'], help='Which integration to uninstall')
    
    # import-chrome
    import_parser = subparsers.add_parser('import-chrome', help='Import Chrome logs from Downloads')
    import_parser.add_argument('--file', default=None, help='Path to JSONL file (default: ~/Downloads/chrome-events.jsonl)')
    
    # status
    subparsers.add_parser('status', help='Show active integrations and log stats')
    
    # query
    query_parser = subparsers.add_parser('query', help='Query logs')
    query_parser.add_argument('--source', choices=['chrome', 'safari', 'shell', 'office', 'all'], default='all', help='Filter by source')
    query_parser.add_argument('--type', help='Filter by event type (e.g. shell_command, tab_focus)')
    query_parser.add_argument('--today', action='store_true', help='Only today\'s logs')
    query_parser.add_argument('--since', help='Logs since (YYYY-MM-DD)')
    query_parser.add_argument('--limit', type=int, default=50, help='Max results (default: 50)')
    query_parser.add_argument('--grep', help='Search in log content')
    
    # timeline
    timeline_parser = subparsers.add_parser('timeline', help='Show chronological activity timeline')
    timeline_parser.add_argument('--today', action='store_true', help='Only today')
    timeline_parser.add_argument('--since', help='Logs since (YYYY-MM-DD)')
    timeline_parser.add_argument('--limit', type=int, default=100, help='Max events (default: 100)')
    
    # analyze
    analyze_parser = subparsers.add_parser('analyze', help='Show behavioral insights')
    analyze_parser.add_argument('--today', action='store_true', help='Only today')
    analyze_parser.add_argument('--since', help='Logs since (YYYY-MM-DD)')
    analyze_parser.add_argument('--source', choices=['chrome', 'safari', 'shell', 'office', 'all'], default='all', help='Filter by source')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    project_root = Path(__file__).parent.parent
    
    if args.command == 'install':
        return install_integration(args.integration, project_root)
    elif args.command == 'uninstall':
        return uninstall_integration(args.integration)
    elif args.command == 'import-chrome':
        return import_chrome_logs(args.file)
    elif args.command == 'status':
        return show_status()
    elif args.command == 'query':
        logs = query_logs(
            source=args.source,
            event_type=args.type,
            today=args.today,
            since=args.since,
            grep=args.grep,
            limit=args.limit,
        )
        print_logs(logs)
        return 0
    elif args.command == 'timeline':
        return show_timeline(today=args.today, since=args.since, limit=args.limit)
    elif args.command == 'analyze':
        logs = query_logs(
            source=args.source,
            today=args.today,
            since=args.since,
            limit=100000,
        )
        analysis = analyze_logs(logs)
        print_analysis(analysis)
        return 0
    
    return 0


if __name__ == '__main__':
    sys.exit(main())