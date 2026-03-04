# Architecture

## Overview

```
┌──────────────┐     UDP broadcast      ┌──────────────────┐
│  CLI / MCP   │ ──────────────────────► │  iZone Bridge    │
│  (Python)    │     port 12107          │  (192.168.x.x)   │
│              │ ◄────────────────────── │                  │
│              │     bridge info         │  Manages dampers │
│              │                         │  and AC unit     │
│              │     HTTP POST           │                  │
│              │ ──────────────────────► │                  │
│              │     port 80             │                  │
│              │ ◄────────────────────── │                  │
│              │     JSON response       │                  │
└──────────────┘                         └──────────────────┘
       │                                          │
       │                                          │
  ┌────┴─────┐                            ┌───────┴────────┐
  │  ~/.config/izone/  │                  │  Zone Dampers  │
  │  bridge_ip (cache) │                  │  Temp Sensors  │
  └──────────┘                            │  AC Unit       │
                                          └────────────────┘
```

## Components

### CLI (`izone`)

A standalone Python 3 script with zero external dependencies. It communicates directly with the iZone bridge over the local network using:

1. **UDP broadcast** for discovery (port 12107)
2. **HTTP POST** for queries and commands (port 80)

The CLI is designed to be self-contained — no `pip install` needed. It uses only the Python standard library (`socket`, `http.client`, `json`, `argparse`).

### MCP Server (`izone_mcp_server.py`)

A Model Context Protocol server built on the `mcp` Python SDK (`FastMCP`). It wraps the same iZone protocol logic as the CLI and exposes it as MCP tools that any MCP-compatible AI assistant can invoke.

The server runs as a subprocess spawned by the MCP client, communicating over stdio using the MCP JSON-RPC protocol.

### IP Cache (`~/.config/izone/bridge_ip`)

A plain text file containing the bridge IP address. Created after the first successful UDP discovery and reused for one hour to avoid repeated broadcast scans. Deleted or refreshed automatically when stale.

## Request Flow

### Discovery

```
Client                          Network                       Bridge
  │                                │                            │
  │─── UDP "IASD" ────────────────►│ (broadcast 255.255.255.255:12107)
  │                                │                            │
  │                                │◄── UDP response ───────────│
  │◄───────────────────────────────│                            │
  │  "ASPort_12107,Mac_000000000,IP_192.168.1.100,iZoneV2,..." │
  │                                                             │
  │  Cache IP to ~/.config/izone/bridge_ip                      │
```

### Query

```
Client                                              Bridge (port 80)
  │                                                       │
  │── POST /iZoneRequestV2 ──────────────────────────────►│
  │   {"iZoneV2Request":{"Type":1,"No":0,"No1":0}}       │
  │                                                       │
  │◄──────────────────────────────────────────────────────│
  │   {"AirStreamDeviceUId":"...","SystemV2":{...}}       │
```

### Command

```
Client                                              Bridge (port 80)
  │                                                       │
  │── POST /iZoneCommandV2 ──────────────────────────────►│
  │   {"SysOn":1}                                         │
  │                                                       │
  │◄──────────────────────────────────────────────────────│
  │   "OK"                                                │
```

## Design Decisions

**Raw HTTP via `http.client`**: The iZone bridge HTTP server cannot handle chunked `Transfer-Encoding`. Libraries like `aiohttp` and `requests` may fragment POST bodies. Using `http.client` directly ensures the body is sent in a single write.

**No authentication**: The iZone local API has no auth mechanism. Security relies entirely on network-level access control (anyone on the LAN can control the system).

**Sequential zone queries**: The bridge handles one request at a time. Zone queries are made sequentially with a short delay between them to avoid dropped or garbled responses.

**Temperature scaling**: The V2 API uses integer values multiplied by 100 (e.g., 2200 = 22.0°C). The CLI and MCP server accept normal decimal values and convert internally.
