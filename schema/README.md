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

### Safari Events (`safari-events.jsonl`)

#### `app_launch` / `app_quit`

No additional fields.

#### `app_focus`

No additional fields.

#### `app_blur`

| Field | Type | Description |
|-------|------|-------------|
| `duration_s` | float | Seconds Safari was focused before blur |

#### `tab_focus`

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | URL of the focused tab |
| `title` | string | Page title |

#### `navigation`

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Navigated URL |
| `title` | string | Page title |
| `from_url` | string | Previous URL |

#### `tab_open` / `tab_close`

| Field | Type | Description |
|-------|------|-------------|
| `tab_count` | int | Total open tabs after change |

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

### AppFocus Events (`appfocus-events.jsonl`)

Captures focus/blur with duration for **every** application (the cross-app
state layer). Replaces the primitive `track_apps.py` "Opened: <app>" records
with real state transitions.

#### `app_focus`

| Field | Type | Description |
|-------|------|-------------|
| `app` | string | Process name (e.g. `Sublime Text`, `Spotify`) |
| `bundle_id` | string | macOS bundle identifier (e.g. `com.sublimetext.4`) |
| `window_title` | string | Front window title via AX (best-effort; empty if unavailable) |

#### `app_blur`

| Field | Type | Description |
|-------|------|-------------|
| `app` | string | Process name |
| `bundle_id` | string | macOS bundle identifier |
| `duration_s` | float | Seconds the app was focused before blur (≥2s) |

### Calendar Events (`calendar-events.jsonl`)

Captures meeting transitions from macOS Calendar — the contextual
force-multiplier that lets the model learn *when* preloads should fire.
Join `meeting_upcoming` against app-focus transitions to learn patterns
like "5 min before a 'standup' meeting, the user opens Teams."

#### `meeting_start`

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Event title/summary |
| `start_time` | string | ISO 8601 UTC start time |
| `end_time` | string | ISO 8601 UTC end time |
| `event_id` | string | Calendar event UID (or `title:start_time` fallback) |
| `calendar_name` | string | Calendar the event belongs to |
| `location` | string | Event location (optional, omitted if empty) |
| `all_day` | bool | Present and true for all-day events |
| `attendees_count` | int | Number of attendees (optional, omitted if 0) |

#### `meeting_end`

Same fields as `meeting_start`.

#### `meeting_upcoming`

Same fields as `meeting_start`, plus:

| Field | Type | Description |
|-------|------|-------------|
| `minutes_until_start` | float | Minutes until the event begins (the preload trigger) |