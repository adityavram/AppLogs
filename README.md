# AppLogs

Understand your behavior on your computer.

AppLogs is a tool that logs meaningful actions you take on your laptop — primarily in the terminal and browser — for the purpose of understanding your own behavior and collecting an action data corpus for downstream training.

## Documentation

- **[Setup Guide](docs/SETUP.md)** — Step-by-step installation instructions
- **[Usage Guide](docs/USAGE.md)** — How to get value from your logs
- **[Schema](schema/README.md)** — Log format documentation

## Quick Start

```bash
# Install all integrations
./applogs install all

# Or install individually
./applogs install shell
./applogs install chrome

# Check what's active
./applogs status

# See your activity
./applogs timeline --today

# Get insights
./applogs analyze --today
```

For full setup instructions (including Chrome native messaging), see the [Setup Guide](docs/SETUP.md).

## Architecture

```
applogs/
├── applogs                  # Main CLI entry point
├── cli/                     # Central CLI (Python, stdlib only)
│   ├── app.py               # Command dispatcher
│   ├── install.py           # Install/uninstall integrations
│   ├── query.py             # Query/filter logs
│   ├── status.py            # Show active integrations
│   ├── timeline.py          # Chronological activity view
│   └── analyze.py           # Behavioral insights
├── integrations/            # Each integration is independently maintainable
│   ├── chrome/              # Chrome extension + native messaging host
│   │   ├── manifest.json
│   │   ├── background.js
│   │   ├── content.js
│   │   ├── popup.html
│   │   ├── popup.js
│   │   ├── native_host.py
│   │   ├── native_host_wrapper.sh
│   │   ├── setup_native_host.sh
│   │   ├── install.sh
│   │   └── README.md
│   └── shell/               # Shell hooks (bash/zsh)
│       ├── applogs.sh
│       ├── install.sh
│       └── README.md
│   └── office/              # Office daemon (Word, PowerPoint, Excel)
│       ├── daemon.py
│       ├── install.sh
│       ├── uninstall.sh
│       └── README.md
├── schema/                  # Shared log schema documentation
│   └── README.md
├── logs/                    # Default log location (also ~/.applogs/logs/)
└── README.md
```

## Integrations

### Shell (`integrations/shell/`)

Logs terminal commands with working directory, exit codes, and duration.

Supports bash and zsh. See `integrations/shell/README.md` for details.

### Chrome (`integrations/chrome/`)

Logs browser activity: tab focus/blur with duration, navigation, page loads. Uses native messaging to write logs directly to disk — no manual export needed.

See `integrations/chrome/README.md` for details.

### Office (`integrations/office/`)

Logs Microsoft Word, PowerPoint, and Excel: app launch/quit, document open/close/focus, and saves. Runs as a macOS LaunchAgent daemon using AppleScript.

See `integrations/office/README.md` for details.

## CLI Commands

| Command | Description |
|---------|-------------|
| `applogs install <chrome\|shell\|all>` | Install an integration |
| `applogs uninstall <chrome\|shell\|all>` | Uninstall an integration |
| `applogs status` | Show active integrations and log stats |
| `applogs query [options]` | Query/filter logs |
| `applogs timeline [options]` | Chronological activity view |
| `applogs analyze [options]` | Behavioral insights |
| `applogs import-chrome [--file PATH]` | Import Chrome logs from a JSONL file (fallback) |

### Query Options

- `--source <chrome\|shell\|all>` - Filter by source
- `--type <type>` - Filter by event type
- `--today` - Only today's logs
- `--since YYYY-MM-DD` - Logs since date
- `--limit N` - Max results
- `--grep "text"` - Search in log content

## Logs

All logs are stored as JSONL in `~/.applogs/logs/`:

- `shell-commands.jsonl` - Shell command logs
- `chrome-events.jsonl` - Chrome activity logs

See `schema/README.md` for the full schema.

## Design Principles

1. **Each integration is independent** — own directory, README, install script
2. **Privacy first** — all data stays local, nothing leaves your machine
3. **Stdlib only** — no external dependencies for the CLI
4. **JSONL format** — easy to process, grep, and pipe to other tools

## Future

- Desktop app with local UI for visualizing behavior
- Additional integrations (IDE, email, calendar)
- Pattern detection and workflow analysis
- Optional sync/export for cross-device analysis

## License

MIT