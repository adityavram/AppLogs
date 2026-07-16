#!/usr/bin/env python3
"""Weekly refinement job for AppLogs.

Runs the full refinement pipeline automatically:
raw logs → enrich → annotate → quality filter → training-ready

Scheduled via launchd to run weekly. Outputs:
- ~/.applogs/logs/training-ready.jsonl
- ~/.applogs/logs/refinement-report.json
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'cli'))

from refinement.pipeline import refine_logs


def main():
    print(f'[AppLogs Refinement] Starting weekly refinement...')
    
    report = refine_logs(use_llm=False)
    
    print(f'[AppLogs Refinement] Complete!')
    print(f'  Raw events: {report["raw_event_count"]}')
    print(f'  After dedup: {report["deduped_event_count"]} (removed {report["deduped_removed"]})')
    print(f'  After noise filter: {report["filtered_event_count"]} (removed {report["noise_removed"]})')
    print(f'  Workflows: {report["workflow_count"]}')
    qd = report["quality_distribution"]
    print(f'  Quality: {qd["high"]} high, {qd["medium"]} medium, {qd["low"]} low')
    print(f'  Training-ready: {report["training_ready_count"]} events from {report["training_ready_workflows"]} workflows')
    print(f'  Report: {report["output_file"]}')


if __name__ == '__main__':
    main()