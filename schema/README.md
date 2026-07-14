# AppLogs Log Schema

All AppLogs integrations write to JSONL files in `~/.applogs/logs/`. Each line is a valid JSON object.

## Shared Fields

Every log entry has these fields:

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO 8601 UTC timestamp (e.g. `2024-07-13T22:34:56.123Z`) |
| `type` | string | Event type (see below) |

## Event Types

### Shell Events (`shell-commands.jsonl`)

#### `shell_command`

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | The command executed |
| `cwd` | string | Working directory |
| `exit_code` | int | Exit code (0 = success) |
| `duration_ms` | int | Duration in milliseconds |
| `shell` | string | Shell type (bash, zsh) |
| `session_id` | string | Unique session identifier |
| `hostname` | string | Machine hostname |

### Chrome Events (`chrome-events.jsonl`)

#### `tab_focus`

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | URL of the focused tab |
| `title` | string | Page title |
| `windowId` | int | Chrome window ID |

#### `tab_blur`

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | URL of the blurred tab |
| `title` | string | Page title |
| `duration_ms` | int | Time spent on tab before blur |

#### `navigation`

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Navigated URL |
| `title` | string | Page title |
| `favIconUrl` | string | Favicon URL |

#### `page_load`

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Loaded URL |
| `tabId` | int | Chrome tab ID |
| `processId` | int | Chrome process ID |

## Adding New Integrations

New integrations should:
1. Write to their own JSONL file in `~/.applogs/logs/`
2. Include `timestamp` and `type` fields
3. Document their event types here
4. Include a `README.md` in their integration directory

### Office Events (`office-events.jsonl`)

#### `app_launch` / `app_quit`

| Field | Type | Description |
|-------|------|-------------|
| `app` | string | App key: `word`, `powerpoint`, or `excel` |
| `bundle_name` | string | Full app name (e.g. `Microsoft Word`) |

#### `app_focus` / `app_blur`

| Field | Type | Description |
|-------|------|-------------|
| `app` | string | App key |
| `bundle_name` | string | Full app name |

#### `doc_open` / `doc_close`

| Field | Type | Description |
|-------|------|-------------|
| `app` | string | App key |
| `doc_name` | string | Document name |
| `doc_path` | string | Full file path (on open only) |

#### `doc_focus`

| Field | Type | Description |
|-------|------|-------------|
| `app` | string | App key |
| `doc_name` | string | Document name |

#### `doc_save`

| Field | Type | Description |
|-------|------|-------------|
| `app` | string | App key |
| `doc_name` | string | Document name |
| `doc_path` | string | Full file path |