# AppLogs Shell Integration

Logs terminal commands to AppLogs.

## What it Captures

- Commands executed (full command string)
- Working directory
- Exit codes
- Duration (milliseconds)
- Shell type and session ID

## Install

```bash
./install.sh
```

Then restart your shell or run:

```bash
source ~/.config/applogs/applogs.sh
```

## Uninstall

Remove these lines from your `~/.bashrc` or `~/.zshrc`:

```
# AppLogs shell integration
source ~/.config/applogs/applogs.sh
```

## Logs

Logs are written to `~/.applogs/logs/shell-commands.jsonl`

```bash
# View recent commands
tail -5 ~/.applogs/logs/shell-commands.jsonl | jq .

# Search for specific commands
grep "git" ~/.applogs/logs/shell-commands.jsonl | jq .
```

## Log Format

```json
{"timestamp":"2024-07-13T22:34:56.123Z","type":"shell_command","command":"git status","cwd":"/Users/you/project","exit_code":0,"duration_ms":234,"shell":"bash","session_id":"abc-123","hostname":"my-machine"}
```

## Supported Shells

- Bash
- Zsh