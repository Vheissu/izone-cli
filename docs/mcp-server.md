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

## Zone Discovery

Zone indexes and names are specific to your iZone installation. Use `izone_status` (or `izone status` from the CLI) to see your available zones. The MCP server dynamically queries zone count and names from your bridge.

## Configuration

In `~/.claude/settings.json`:

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

Restart your MCP client after any configuration change.

## Dependencies

- Python 3.8+
- `mcp` package (`pip3 install mcp`)
- Network access to the iZone bridge (same LAN)
