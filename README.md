# AppLogs

Understand your behavior on your computer.

AppLogs is a tool that logs meaningful actions you take on your laptop for the purpose of understanding your own behavior and collecting an action data corpus for downstream training.

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
./applogs install safari
./applogs install office

# Start all daemons (safari, office)
./applogs start all

# Check what's active
./applogs status

# See your activity
./applogs timeline --today

# Get insights
./applogs analyze --today

# Enrich logs with context and outcomes
./applogs enrich

# Detect workflows and label them
./applogs annotate           # template-based
./applogs annotate --llm     # with local LLM annotation (requires Ollama)

# View timeline with workflow boundaries
./applogs timeline --today --workflows
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
│   ├── timeline.py          # Chronological activity view (with workflow support)
│   ├── analyze.py           # Behavioral insights
│   ├── daemon_manager.py    # Start/stop daemons
│   ├── importer.py          # Import Chrome logs (fallback)
│   ├── enrichment/          # Phase 1: context + outcome enrichment
│   │   └── pipeline.py      # Post-processes raw logs into enriched.jsonl
│   └── workflows/           # Phase 2: workflow detection + annotation
│       ├── detector.py      # Content continuity + app-transition clustering
│       ├── labeler.py       # Template-based workflow labeling
│       ├── annotator.py     # Ollama LLM annotation (local)
│       └── assembler.py     # Training data assembly
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
│   ├── safari/              # Safari daemon (AppleScript-based)
│   │   ├── daemon.py
│   │   ├── install.sh
│   │   ├── uninstall.sh
│   │   └── README.md
│   ├── shell/               # Shell hooks (bash/zsh)
│   │   ├── applogs.sh
│   │   ├── install.sh
│   │   └── README.md
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

### Safari (`integrations/safari/`)

Logs Safari browsing activity: navigation, tab focus, app focus/blur with duration. Runs as a macOS LaunchAgent daemon using AppleScript — no extension required.

See `integrations/safari/README.md` for details.

### Office (`integrations/office/`)

Logs Microsoft Word, PowerPoint, and Excel: app launch/quit, document open/close/focus, and saves. Runs as a macOS LaunchAgent daemon using AppleScript.

See `integrations/office/README.md` for details.

## CLI Commands

| Command | Description |
|---------|-------------|
| `applogs install <chrome\|safari\|shell\|office\|all>` | Install an integration |
| `applogs uninstall <chrome\|safari\|shell\|office\|all>` | Uninstall an integration |
| `applogs start <chrome\|safari\|shell\|office\|all>` | Start daemons (default: all) |
| `applogs stop <chrome\|safari\|shell\|office\|all>` | Stop daemons (default: all) |
| `applogs status` | Show active integrations and log stats |
| `applogs query [options]` | Query/filter logs |
| `applogs timeline [options]` | Chronological activity view |
| `applogs analyze [options]` | Behavioral insights |
| `applogs enrich` | Run enrichment pipeline on raw logs |
| `applogs annotate [--llm] [--model MODEL]` | Detect workflows and label them |
| `applogs import-chrome [--file PATH]` | Import Chrome logs from a JSONL file (fallback) |

### Query Options

- `--source <chrome\|safari\|shell\|office\|all>` - Filter by source
- `--type <type>` - Filter by event type
- `--today` - Only today's logs
- `--since YYYY-MM-DD` - Logs since date
- `--limit N` - Max results
- `--grep "text"` - Search in log content

## Logs

All logs are stored as JSONL in `~/.applogs/logs/`:

| File | Contents |
|------|----------|
| `shell-commands.jsonl` | Shell command logs (raw) |
| `chrome-events.jsonl` | Chrome activity logs (raw) |
| `safari-events.jsonl` | Safari activity logs (raw) |
| `office-events.jsonl` | Office app activity logs (raw) |
| `enriched.jsonl` | Enriched events with context, outcomes, workflow IDs |
| `workflows.json` | Detected workflows with labels and LLM annotations |
| `training.jsonl` | ML-ready training data (state-action-outcome triplets) |

See `schema/README.md` for the full schema.

## Workflow Detection & ML Enrichment

AppLogs goes beyond raw logging — it builds a pipeline for ML training data:

1. **Collect** — integrations log raw events to JSONL
2. **Enrich** (`./applogs enrich`) — adds context (recent actions, focused app, screen state, time features), outcomes (retry, undo, next-action delay), and workflow clustering
3. **Annotate** (`./applogs annotate`) — detects workflows using content continuity + app-transition patterns, labels them via templates or local LLM (Ollama)
4. **Assemble** — outputs ML-ready state-action-outcome triplets to `training.jsonl`

### Ollama Integration

For LLM-assisted annotation, install [Ollama](https://ollama.com) and pull a model:

```bash
ollama pull llama3.2
```

Then run:

```bash
./applogs annotate --llm
```

All LLM processing is local — no data leaves your machine.

1. **Each integration is independent** — own directory, README, install script
2. **Privacy first** — all data stays local, nothing leaves your machine
3. **Stdlib only** — no external dependencies for the CLI
4. **JSONL format** — easy to process, grep, and pipe to other tools

## Future

- Training data pipeline (Phase 3): feature engineering, train/test splits, evaluation
- Model training (Phase 4): behavioral cloning, sequence models, predictive/assistive/autonomous modes
- Desktop app with local UI for visualizing behavior
- Additional integrations (IDE, email, calendar, Slack)
- Optional sync/export for cross-device analysis

## License

MIT
