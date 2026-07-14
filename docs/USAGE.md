# AppLogs Usage Guide

This guide shows you how to use AppLogs to understand your behavior on your computer.

## The Core Commands

### See What You Did Today

```bash
./applogs timeline --today
```

Shows a chronological merge of your terminal commands and browser activity. You'll see something like:

```
--- 2026-07-14 ---

  09:15:03  [>] github.com
  09:15:30  [~] GitHub Dashboard                    (27s)
  09:15:30  [>] chatgpt.com
  09:22:14  [.] git status
  09:22:18  [.] npm test
  09:22:45  [.] code .
```

**Legend:**
- `[.]` — shell command (exit code 0)
- `[x]` — shell command (failed)
- `[>]` — navigated to a site
- `[~] — left a site (with time spent)

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

### Check Status

```bash
./applogs status
```

Shows which integrations are active and how many logs each has collected.

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

### Weekly Review

Every few days, run:

```bash
./applogs analyze --since 2026-07-08
```

This gives you a broader view. Look for:
- Command frequency changes (new tools adopted?)
- Site patterns shifted (new research rabbit holes?)
- Error rates (improving or getting stuck?)

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

## Log Files

All logs are stored as JSONL in `~/.applogs/logs/`:

| File | Contents |
|------|----------|
| `shell-commands.jsonl` | Every terminal command with cwd, exit code, duration |
| `chrome-events.jsonl` | Tab focus/blur, navigation, page loads |

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
rm -rf ~/.applogs
```