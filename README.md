# iZone CLI & MCP Server

Control your iZone ducted air conditioning system from the terminal and through any MCP-compatible AI assistant.

## Setup

No dependencies required beyond Python 3. The CLI and MCP server use only the standard library for iZone communication. The MCP server additionally requires the `mcp` package.

```bash
# Install MCP SDK (for the MCP server only)
pip3 install mcp

# Make the CLI available globally
ln -sf /path/to/izone-cli/izone /opt/homebrew/bin/izone
```

## CLI Usage

```bash
# Full status (system + zones, default if no command given)
izone status

# System info only (no zones)
izone system

# List all zones
izone zones

# Power
izone on
izone off

# Mode: cool, heat, vent, dry, auto
izone mode cool

# Fan speed: low, medium, high, auto, top
izone fan auto

# System temperature (15.0 - 30.0 C)
izone temp 22

# Sleep timer
izone sleep 60                        # Auto-off in 60 minutes
izone sleep 0                         # Clear timer

# Zone control (by index)
izone zone 2                          # View zone info
izone zone 2 --mode auto             # Set zone to auto
izone zone 2 --temp 23               # Set zone temperature
izone zone 5 --max-air 80            # Set max airflow
izone zone 5 --mode auto --temp 22   # Combine options

# Air quality readings (humidity, eCO2, TVOC)
izone airquality

# JSON output (for scripting)
izone json

# Network discovery
izone discover

# Target a specific bridge IP (skips discovery)
izone --ip 192.168.1.100 status
```

## MCP Server

The MCP server lets any MCP-compatible AI assistant control your AC through natural language.

### Configuration

Add to your MCP client configuration (e.g. `~/.claude/settings.json` for Claude Code):

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

Restart your MCP client after adding the configuration.

### Available Tools

| Tool | Description |
|---|---|
| `izone_status` | Full system and zone readout |
| `izone_power` | Turn system on or off |
| `izone_mode` | Set operating mode |
| `izone_fan` | Set fan speed |
| `izone_temperature` | Set system target temperature |
| `izone_zone_control` | Control individual zones (mode, temp, airflow) |
| `izone_comfort_setup` | Quick setup: power on, set mode/fan/temp, open specific zones |

### Example Prompts

- "What's the temperature in my house?"
- "Turn on the AC and cool the study to 23 degrees"
- "Cool the master bedroom and lounge to 22, close everything else"
- "Turn off the AC"
- "Set the fan to low and drop the temp to 21"

## Bridge Discovery

The CLI auto-discovers your iZone bridge via UDP broadcast and caches the IP at `~/.config/izone/bridge_ip` for one hour. Use `--ip` to skip discovery and target a bridge directly.

## Docs

- [Architecture](docs/architecture.md) — system design and request flows
- [iZone Protocol](docs/izone-protocol.md) — full V2 API reference
- [MCP Server](docs/mcp-server.md) — MCP tools and configuration
