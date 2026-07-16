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
from enrichment.pipeline import enrich_logs
from daemon_manager import start_daemons, stop_daemons, start_daemon, stop_daemon
from workflows.detector import detect_workflows, workflows_to_json
from workflows.labeler import label_workflow
from workflows.annotator import check_ollama, annotate_workflow, annotate_action
from workflows.assembler import load_enriched, assemble_training_data, write_training_data, write_workflows
from refinement.pipeline import refine_logs


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
    timeline_parser.add_argument('--workflows', action='store_true', help='Show workflow labels and boundaries')
    
    # analyze
    analyze_parser = subparsers.add_parser('analyze', help='Show behavioral insights')
    analyze_parser.add_argument('--today', action='store_true', help='Only today')
    analyze_parser.add_argument('--since', help='Logs since (YYYY-MM-DD)')
    analyze_parser.add_argument('--source', choices=['chrome', 'safari', 'shell', 'office', 'all'], default='all', help='Filter by source')
    
    # enrich
    subparsers.add_parser('enrich', help='Run enrichment pipeline on raw logs')
    
    # annotate
    annotate_parser = subparsers.add_parser('annotate', help='Detect workflows and annotate with labels')
    annotate_parser.add_argument('--llm', action='store_true', help='Use Ollama LLM for richer annotation')
    annotate_parser.add_argument('--model', default='llama3.2', help='Ollama model to use (default: llama3.2)')
    annotate_parser.add_argument('--actions', action='store_true', help='Also annotate individual actions (slower)')
    annotate_parser.add_argument('--gap', type=int, default=300, help='Workflow gap in seconds (default: 300)')
    
    # refine
    refine_parser = subparsers.add_parser('refine', help='Run full refinement pipeline (dedup + filter + quality score)')
    refine_parser.add_argument('--llm', action='store_true', help='Use Ollama LLM during refinement')
    
    # export
    export_parser = subparsers.add_parser('export', help='Export refined training-ready data (not raw logs)')
    export_parser.add_argument('--output', default=None, help='Output file path (default: ~/applogs-export.jsonl)')
    export_parser.add_argument('--report', action='store_true', help='Include refinement report in output')
    
    # start
    start_parser = subparsers.add_parser('start', help='Start daemons for integrations')
    start_parser.add_argument('integration', choices=['chrome', 'safari', 'shell', 'office', 'all'], nargs='?', default='all', help='Which daemon to start (default: all)')
    
    # stop
    stop_parser = subparsers.add_parser('stop', help='Stop daemons for integrations')
    stop_parser.add_argument('integration', choices=['chrome', 'safari', 'shell', 'office', 'all'], nargs='?', default='all', help='Which daemon to stop (default: all)')
    
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
        return show_timeline(today=args.today, since=args.since, limit=args.limit, show_workflows=args.workflows)
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
    elif args.command == 'enrich':
        count = enrich_logs()
        if count > 0:
            print(f'\nEnriched log: ~/.applogs/logs/enriched.jsonl')
            print(f'View with: tail -1 ~/.applogs/logs/enriched.jsonl | jq .')
        return 0
    elif args.command == 'annotate':
        # Load enriched logs
        enriched = load_enriched()
        if not enriched:
            print('No enriched logs found. Run ./applogs enrich first.')
            return 1
        
        print(f'Loaded {len(enriched)} enriched events')
        
        # Detect workflows
        print(f'Detecting workflows (gap={args.gap}s)...')
        workflows = detect_workflows(enriched, gap_seconds=args.gap)
        print(f'Found {len(workflows)} workflows')
        
        # Template-based labeling
        print('Applying template labels...')
        labeled = 0
        for wf in workflows:
            result = label_workflow(wf)
            if result:
                wf['label'] = result['label']
                wf['description'] = result['description']
                labeled += 1
            else:
                wf['label'] = 'unknown'
                wf['description'] = ''
        print(f'  {labeled}/{len(workflows)} matched templates')
        
        # LLM annotation (optional)
        if args.llm:
            if not check_ollama():
                print('Ollama not running. Skipping LLM annotation.')
                print('Start Ollama with: ollama serve')
            else:
                print(f'LLM annotation with {args.model}...')
                annotated = 0
                to_annotate = [wf for wf in workflows if wf.get('action_count', len(wf.get('actions', []))) >= 3]
                print(f'  Annotating {len(to_annotate)} workflows (3+ actions)...')
                for idx, wf in enumerate(to_annotate):
                    print(f'  [{idx+1}/{len(to_annotate)}] ', end='', flush=True)
                    wf_json = {
                        'action_summaries': workflows_to_json([wf])[0]['action_summaries'],
                        'keywords': wf.get('keywords', []),
                        'app_sequence': wf.get('app_sequence', []),
                    }
                    result = annotate_workflow(wf_json, model=args.model)
                    if result:
                        wf['annotation'] = result
                        if wf.get('label') == 'unknown':
                            wf['label'] = result.get('workflow_label', 'unknown')
                            wf['description'] = result.get('intent', '')
                        annotated += 1
                        print(f'{wf["label"]}')
                    else:
                        print('failed')
                print(f'  {annotated}/{len(to_annotate)} annotated by LLM')
        
        # Print workflow summary
        print('\nWorkflows:')
        for wf in workflows:
            ts = wf['start_ts'].strftime('%H:%M') if hasattr(wf['start_ts'], 'strftime') else '?'
            count = wf.get('action_count', len(wf.get('actions', [])))
            label = wf.get('label', '?')
            print(f'  [{ts}] {label:20s} ({count} actions)')
        
        # Assemble training data
        print('\nAssembling training data...')
        examples = assemble_training_data(workflows, enriched)
        write_training_data(examples)
        write_workflows(workflows)
        
        print(f'\nDone!')
        print(f'  Workflows:    ~/.applogs/logs/workflows.json')
        print(f'  Training:     ~/.applogs/logs/training.jsonl ({len(examples)} examples)')
        return 0
    elif args.command == 'refine':
        print('Running refinement pipeline...\n')
        report = refine_logs(use_llm=args.llm)
        
        print(f'Pipeline steps:')
        for step in report['steps']:
            print(f'  {step}')
        
        print(f'\nSummary:')
        print(f'  Raw events:       {report["raw_event_count"]}')
        print(f'  After dedup:      {report["deduped_event_count"]} (removed {report["deduped_removed"]})')
        print(f'  After noise:      {report["filtered_event_count"]} (removed {report["noise_removed"]})')
        print(f'  Workflows:        {report["workflow_count"]}')
        qd = report['quality_distribution']
        print(f'  Quality:          {qd["high"]} high, {qd["medium"]} medium, {qd["low"]} low')
        print(f'  Training-ready:   {report["training_ready_count"]} events from {report["training_ready_workflows"]} workflows')
        print(f'\n  Output: {report["output_file"]}')
        print(f'  Report: ~/.applogs/logs/refinement-report.json')
        return 0
    elif args.command == 'export':
        training_file = Path.home() / '.applogs' / 'logs' / 'training-ready.jsonl'
        if not training_file.exists():
            print('No training-ready data found. Run ./applogs refine first.')
            return 1
        
        output_path = args.output or str(Path.home() / 'applogs-export.jsonl')
        
        with open(training_file) as f:
            data = f.read()
        
        with open(output_path, 'w') as f:
            f.write(data)
        
        count = data.strip().count('\n') + 1
        print(f'Exported {count} training-ready events to {output_path}')
        print(f'\nThis file contains only refined, quality-filtered data.')
        print(f'Raw logs are NOT included (they stay local).')
        
        if args.report:
            report_file = Path.home() / '.applogs' / 'logs' / 'refinement-report.json'
            if report_file.exists():
                report_output = output_path.replace('.jsonl', '-report.json')
                with open(report_file) as f:
                    report = f.read()
                with open(report_output, 'w') as f:
                    f.write(report)
                print(f'Refinement report: {report_output}')
        
        return 0
    elif args.command == 'start':
        return start_daemons(args.integration, project_root)
    elif args.command == 'stop':
        return stop_daemons(args.integration)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())