# AppLogs Usage Guide

This guide shows you how to use AppLogs to understand your behavior on your computer.

## The Core Commands

### See What You Did Today

```bash
./applogs timeline --today
```

Shows a chronological merge of your terminal commands, browser activity, and Office events. You'll see something like:

```
--- 2026-07-14 ---

  09:15:03  [>] github.com
  09:15:30  [~] GitHub Dashboard                    (27s)
  09:15:30  [>] chatgpt.com
  09:22:14  [.] git status
  09:22:18  [.] npm test
  09:22:45  [.] code .
  10:30:00  [L] word launched
  10:30:05  [W] word: Report.docx
  10:45:00  [S] word: Report.docx
  10:50:00  [-] word: Report.docx
```

**Legend:**
- `[.]` — shell command (exit code 0)
- `[x]` — shell command (failed)
- `[>]` — navigated to a site
- `[~]` — left a site (with time spent)
- `[L]` — Office app launched
- `[Q]` — Office app quit
- `[W]` — Office app or document focused
- `[ ]` — Office app lost focus (with duration)
- `[+]` — Office document opened
- `[-]` — Office document closed
- `[S]` — Office document saved

### Get Behavioral Insights

```bash
./applogs analyze --today
```

Shows:
- Total events and date range
- Activity by hour (when you're most productive)
- Top shell commands (what you run most)
- Top working directories (where you spend time)
- Most visited sites (where you browse)
- Time spent per site (how long you stay)
- Failed commands (what errors you hit)
- Office app activity (which apps you use most)
- Most active documents (which docs you work on)
- Document saves (when you saved)

### Check Status

```bash
./applogs status
```

Shows which integrations are active and how many logs each has collected.

### Start/Stop Daemons

```bash
# Start all daemons (safari, office)
./applogs start all

# Stop all
./applogs stop all

# Start/stop individual
./applogs start safari
./applogs stop office
```

### Enrich Logs

Run the enrichment pipeline to add context, outcomes, and workflow clustering to raw logs:

```bash
./applogs enrich
```

This creates `~/.applogs/logs/enriched.jsonl` with each event as a state-action-outcome triplet including:
- Recent actions (sliding window of 10)
- Focused app inference
- Time features (hour, day of week, etc.)
- Cross-source correlation
- Screen state snapshot
- Page category classification
- Outcome tracking (retry, undo, next-action delay)

### Detect and Annotate Workflows

```bash
# Template-based workflow detection and labeling
./applogs annotate

# With LLM annotation (requires Ollama running locally)
./applogs annotate --llm

# With specific Ollama model
./applogs annotate --llm --model llama3

# Adjust workflow gap (default 300s = 5 min)
./applogs annotate --gap 600
```

This creates:
- `~/.applogs/logs/workflows.json` — detected workflows with labels and annotations
- `~/.applogs/logs/training.jsonl` — ML-ready training data

### Refine and Export Training Data

```bash
# Run full refinement (dedup, filter, quality score, training-ready output)
./applogs refine

# With LLM annotation during refinement
./applogs refine --llm

# Export only refined data (raw logs never leave your machine)
./applogs export --output ~/applogs-export.jsonl

# Include refinement report in export
./applogs export --report
```

The refinement pipeline:
1. Deduplicates events (same source+type within 5s)
2. Filters noise (internal commands, empty events)
3. Normalizes actions (git push → vcs_deploy, etc.)
4. Scores workflow quality (high/medium/low)
5. Outputs only high+medium quality workflows

### Automated Weekly Refinement

```bash
# Install weekly job (runs Sunday 3 AM)
~/AppLogs/cli/refinement/install_weekly.sh

# Check it's scheduled
launchctl list | grep applogs

# Uninstall
~/AppLogs/cli/refinement/uninstall_weekly.sh
```

### View Timeline with Workflows

```bash
./applogs timeline --today --workflows
```

Shows workflow labels and boundaries in the timeline:
```
--- 2026-07-14 ---

  ┌── [fix_bug] (7 actions) ──
  10:15:03  [.] git checkout -b fix/42
  10:16:00  [>] github.com
  10:22:14  [.] git push
  └── end workflow ──
```

## Useful Queries

### Search Your Commands

Find all git commands you ran today:

```bash
./applogs query --source shell --grep "git" --today
```

### Find Failed Commands

See every command that failed (non-zero exit code):

```bash
./applogs query --source shell --today
```

Then look for `exit=x` where x is not 0. Or use the analyze command which lists failures at the bottom.

### See Where You Spent Time

```bash
./applogs analyze --today
```

The "Time Spent per Site" section shows how long you stayed on each website. This is calculated from tab focus/blur events.

### Filter by Date Range

Look at the past few days:

```bash
./applogs timeline --since 2026-07-10
./applogs analyze --since 2026-07-10
```

### Search Browser History

Find all visits to a specific site:

```bash
./applogs query --source chrome --grep "github" --today
```

### Search Office Activity

Find all events for a specific Office app:

```bash
./applogs query --source office --today
./applogs query --source office --type doc_save --today
```

Find activity for a specific document:

```bash
./applogs query --source office --grep "Report" --today
```

### Limit Results

```bash
./applogs query --limit 10 --today
./applogs timeline --limit 50
```

## Understanding Your Patterns

### Daily Routine

Run `./applogs analyze --today` at the end of each day. Over time you'll notice:

- **When you're most active** — the activity-by-hour heatmap shows your peak hours
- **Your most-used tools** — top commands reveal your workflow
- **Where your attention goes** — most visited sites show your priorities (or distractions)
- **Your error patterns** — failed commands reveal recurring issues
- **Your Office habits** — which apps and documents you spend time on, and how often you save

### Weekly Review

Every few days, run:

```bash
./applogs analyze --since 2026-07-08
```

This gives you a broader view. Look for:
- Command frequency changes (new tools adopted?)
- Site patterns shifted (new research rabbit holes?)
- Error rates (improving or getting stuck?)
- Office app usage shifts (different documents or apps over time?)
- Save frequency (are you saving more or less often?)

### Workflow Discovery

The timeline reveals workflows you didn't know you had. For example, you might see:

```
  10:15  [.] git checkout -b feature/x
  10:16  [>] github.com/repo/issues/42
  10:18  [>] chatgpt.com
  10:22  [.] code .
  10:45  [.] git add -A
  10:45  [.] git commit -m "fix issue #42"
```

This shows: issue review → research → implementation → commit. That's a workflow pattern that could be automated or optimized.

Or you might see how you work across Office and the browser:

```
  14:00  [L] excel launched
  14:01  [+] excel: Budget.xlsx
  14:15  [>] chatgpt.com
  14:20  [W] excel: Budget.xlsx
  14:25  [S] excel: Budget.xlsx
```

This shows: spreadsheet work → quick research question → back to spreadsheet → save. The gap between focus and blur reveals how long you context-switched.

## Log Files

All logs are stored as JSONL in `~/.applogs/logs/`:

| File | Contents |
|------|----------|
| `shell-commands.jsonl` | Every terminal command with cwd, exit code, duration |
| `chrome-events.jsonl` | Chrome tab focus/blur, navigation, page loads |
| `safari-events.jsonl` | Safari navigation, tab focus, app focus/blur |
| `office-events.jsonl` | Office app launch/quit, doc open/close/focus, saves |
| `enriched.jsonl` | Enriched events with context, outcomes, workflow IDs |
| `workflows.json` | Detected workflows with labels and annotations |
| `training.jsonl` | ML-ready training data (all workflows) |
| `training-ready.jsonl` | Quality-filtered training data (high+medium only) |
| `refinement-report.json` | Last refinement run report |

You can inspect them directly:

```bash
# View raw shell logs
cat ~/.applogs/logs/shell-commands.jsonl | jq .

# Count events
wc -l ~/.applogs/logs/*.jsonl

# Search with grep
grep "git" ~/.applogs/logs/shell-commands.jsonl | jq .
```

## Privacy

- All data stays on your machine
- Nothing is sent to any server
- You can delete logs at any time:

```bash
rm ~/.applogs/logs/*.jsonl
```

## Tips

1. **Make it a habit** — run `./applogs analyze --today` at the end of each day
2. **Don't over-analyze** — the value is in patterns over time, not individual events
3. **Watch for surprises** — the data often reveals things you didn't realize about your habits
4. **Share insights** — if you find interesting patterns, the raw data is easy to export and share

## Uninstall

If you want to stop collecting logs:

```bash
./applogs uninstall shell
./applogs uninstall chrome
./applogs uninstall safari
./applogs uninstall office
rm -rf ~/.applogs
```