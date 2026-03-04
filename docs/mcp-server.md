# MCP Server

The iZone MCP server exposes your air conditioning system as tools that any MCP-compatible AI assistant can call through natural language.

## How It Works

```
┌──────────────┐   stdio (JSON-RPC)   ┌──────────────────┐   HTTP   ┌─────────┐
│  MCP Client  │ ◄──────────────────► │  izone_mcp_server │ ───────► │  iZone  │
│  (AI Agent)  │                      │  (Python process) │ ◄─────── │  Bridge │
└──────────────┘                      └──────────────────┘          └─────────┘
```

1. The MCP client spawns `izone_mcp_server.py` as a child process
2. They communicate over stdin/stdout using the MCP protocol (JSON-RPC over stdio)
3. When you ask your AI assistant about the AC, it calls the appropriate iZone MCP tool
4. The tool makes HTTP requests to your iZone bridge on the local network
5. Results are returned to the assistant, which interprets them in natural language

## Tools

### `izone_status`
Returns a formatted overview of the entire system: power state, mode, fan, temperatures, humidity, air quality, and every zone with its current temperature, setpoint, mode, and airflow.

### `izone_power`
Turns the system on or off.
- `state`: `"on"` or `"off"`

### `izone_mode`
Sets the operating mode.
- `mode`: `"cool"`, `"heat"`, `"vent"`, `"dry"`, or `"auto"`

### `izone_fan`
Sets the fan speed.
- `speed`: `"low"`, `"medium"`, `"high"`, `"auto"`, or `"top"`

### `izone_temperature`
Sets the system target temperature.
- `temperature`: Float between 15.0 and 30.0 (Celsius)

### `izone_zone_control`
Controls an individual zone. Only pass the parameters you want to change.
- `zone_index`: 0-based (run `izone_status` to see available zones)
- `mode`: `"open"`, `"close"`, or `"auto"` (optional)
- `temperature`: Zone setpoint, 15.0–30.0 (optional)
- `max_airflow`: Max airflow percentage, 0–100 (optional)
- `min_airflow`: Min airflow percentage, 0–100 (optional)

### `izone_comfort_setup`
One-shot comfort command. Turns on the AC, sets mode/fan/temp, opens specified zones in auto mode, and closes all others.
- `zones`: Comma-separated zone indexes (e.g., `"2,5"`)
- `temperature`: Target temperature
- `mode`: AC mode (default: `"cool"`)
- `fan`: Fan speed (default: `"auto"`)

### `izone_defaults_save`
Snapshots the current system and zone settings to disk. The MCP server is instructed to call this automatically before making temporary changes (bedtime mode, etc.) so settings can be restored later.

### `izone_defaults_restore`
Restores previously saved default settings — mode, fan, temperature, and all zone configurations.

### `izone_schedules`
Lists all 9 schedule slots with name, enabled status, timing, mode, fan, and active days.

### `izone_schedule_detail`
Shows full details of a schedule slot including per-zone mode and setpoint.
- `slot`: Schedule index (0–8)

### `izone_schedule_edit`
Modify a schedule's settings. Only pass the parameters you want to change.
- `slot`: Schedule index (0–8)
- `name`: Schedule name, max 15 chars (optional)
- `mode`: AC mode (optional)
- `fan`: Fan speed (optional)
- `start`: Start time as `"HH:MM"` or `"off"` (optional)
- `stop`: Stop time as `"HH:MM"` or `"off"` (optional)
- `days`: Comma-separated days or `"weekdays"`, `"weekends"`, `"all"` (optional)
- `enabled`: `true`/`false` (optional)

### `izone_run_schedule`
Runs a schedule immediately as a scene/favourite without enabling its timer.
- `slot`: Schedule index (0–8)

### `izone_profiles`
Lists all saved profiles with a summary of each: mode, fan, temperature, and zone count.

### `izone_save_profile`
Saves the current live AC settings as a named profile.
- `name`: Profile name (e.g., `"summer-day"`, `"bedtime"`)

### `izone_apply_profile`
Applies a saved profile. Turns on the AC and sets mode, fan, temperature, and per-zone configurations. Zones not in the profile are closed by default.
- `name`: Profile name to apply

### `izone_create_profile`
Creates or updates a profile from parameters without changing the AC. Useful for defining optimal settings to apply later.
- `name`: Profile name
- `mode`: AC mode (default: `"cool"`)
- `fan`: Fan speed (default: `"auto"`)
- `temperature`: System setpoint, 15.0–30.0 (default: 23.0)
- `zones`: Zone configs as `"index:temp,index:temp"` (e.g., `"2:22,5:23"`) — listed zones are set to auto mode (optional)
- `close_others`: Close zones not listed (default: true)

## Zone Discovery

Zone indexes and names are specific to your iZone installation. Use `izone_status` (or `izone status` from the CLI) to see your available zones. The MCP server dynamically queries zone count and names from your bridge.

## Configuration

### Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "izone": {
      "command": "python3",
      "args": ["/path/to/izone-cli/izone_mcp_server.py"],
      "env": {}
    }
  }
}
```

### OpenAI Codex

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.izone]
command = "python3"
args = ["/path/to/izone-cli/izone_mcp_server.py"]
```

Or via CLI: `codex mcp add izone -- python3 /path/to/izone-cli/izone_mcp_server.py`

### OpenClaw

Add to `~/.openclaw/openclaw.json`:

```json
{
  "mcpServers": {
    "izone": {
      "command": "python3",
      "args": ["/path/to/izone-cli/izone_mcp_server.py"],
      "env": {}
    }
  }
}
```

OpenClaw's heartbeat scheduler can periodically check temperatures and take action autonomously — see [use-cases.md](use-cases.md) for examples.

### Other MCP Clients

Any MCP-compatible client that supports stdio servers can use the iZone MCP server. The configuration typically requires:
- **Command**: `python3`
- **Args**: `["/path/to/izone-cli/izone_mcp_server.py"]`

Restart your MCP client after any configuration change.

## Dependencies

- Python 3.8+
- `mcp` package (`pip3 install mcp`)
- Network access to the iZone bridge (same LAN)
