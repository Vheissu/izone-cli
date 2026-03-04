#!/usr/bin/env python3
"""iZone MCP Server - Control your iZone AC through any MCP-compatible AI assistant."""

import http.client
import json
import os
import socket
import time

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("izone", instructions="""You control an iZone ducted air conditioning system.
The system has 7 zones: Dining(0), Lounge(1), Master(2), Lavinia(3), Daedalus(4), Study(5), Upstairs(6).
Temperature values from the API are multiplied by 100 (e.g., 2400 = 24.0C).
When setting temperatures, accept normal values like 22.5 and convert to API format internally.
Always check current status before making changes. Be energy-conscious.""")

# --- iZone protocol constants ---
DISCOVERY_PORT = 12107
BRIDGE_IP_CACHE = os.path.expanduser("~/.config/izone/bridge_ip")
HTTP_TIMEOUT = 5

MODES = {"cool": 1, "heat": 2, "vent": 3, "dry": 4, "auto": 5}
MODES_REV = {v: k for k, v in MODES.items()}
FAN_SPEEDS = {"low": 1, "medium": 2, "high": 3, "auto": 4, "top": 5}
FAN_REV = {v: k for k, v in FAN_SPEEDS.items()}
ZONE_MODES = {"open": 1, "close": 2, "auto": 3, "override": 4, "constant": 5}
ZONE_MODES_REV = {v: k for k, v in ZONE_MODES.items()}


def _get_bridge_ip() -> str:
    """Get bridge IP from cache or discovery."""
    if os.path.exists(BRIDGE_IP_CACHE):
        if time.time() - os.path.getmtime(BRIDGE_IP_CACHE) < 3600:
            with open(BRIDGE_IP_CACHE) as f:
                ip = f.read().strip()
                if ip:
                    return ip
    # Discover
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(3)
    sock.sendto(b"IASD", ("255.255.255.255", DISCOVERY_PORT))
    try:
        data, addr = sock.recvfrom(1024)
        text = data.decode("utf-8", errors="replace")
        parts = dict(p.split("_", 1) for p in text.split(",") if "_" in p)
        ip = parts.get("IP", addr[0])
    except socket.timeout:
        raise RuntimeError("No iZone bridge found on the network")
    finally:
        sock.close()
    os.makedirs(os.path.dirname(BRIDGE_IP_CACHE), exist_ok=True)
    with open(BRIDGE_IP_CACHE, "w") as f:
        f.write(ip)
    time.sleep(0.5)
    return ip


def _post(endpoint: str, payload: dict) -> str:
    ip = _get_bridge_ip()
    conn = http.client.HTTPConnection(ip, 80, timeout=HTTP_TIMEOUT)
    body = json.dumps(payload)
    conn.request("POST", endpoint, body=body, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8", errors="replace").strip()
    conn.close()
    if raw.endswith("{OK}"):
        raw = raw[:-4]
    return raw


def _query_system() -> dict:
    raw = _post("/iZoneRequestV2", {"iZoneV2Request": {"Type": 1, "No": 0, "No1": 0}})
    return json.loads(raw)


def _query_zone(index: int) -> dict:
    raw = _post("/iZoneRequestV2", {"iZoneV2Request": {"Type": 2, "No": index, "No1": 0}})
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        time.sleep(0.3)
        raw = _post("/iZoneRequestV2", {"iZoneV2Request": {"Type": 2, "No": index, "No1": 0}})
        return json.loads(raw)


def _send_command(payload: dict) -> str:
    return _post("/iZoneCommandV2", payload)


def _fmt_temp(val) -> str:
    if isinstance(val, (int, float)):
        return f"{val / 100:.1f}"
    return str(val)


# --- MCP Tools ---

@mcp.tool()
def izone_status() -> str:
    """Get the full status of the iZone AC system including all zones.
    Returns system power state, mode, fan speed, temperatures, humidity, air quality, and all zone details."""
    data = _query_system()
    s = data["SystemV2"]
    on_off = "ON" if s["SysOn"] else "OFF"
    mode = MODES_REV.get(s["SysMode"], str(s["SysMode"]))
    fan = FAN_REV.get(s["SysFan"], str(s["SysFan"]))

    lines = [
        f"System: {on_off}",
        f"Mode: {mode}",
        f"Fan: {fan}",
        f"Setpoint: {_fmt_temp(s['Setpoint'])}C",
        f"Return Air: {_fmt_temp(s['Temp'])}C",
        f"Supply Air: {_fmt_temp(s['Supply'])}C",
    ]
    if s.get("InRh"):
        lines.append(f"Humidity: {s['InRh']}%")
    if s.get("IneCO2"):
        lines.append(f"eCO2: {s['IneCO2']} ppm")
    if s.get("InTVOC"):
        lines.append(f"TVOC: {s['InTVOC']} ppb")

    lines.append("")
    lines.append(f"{'#':<3} {'Name':<12} {'Temp':>6} {'Set':>6} {'Mode':<10} {'Air%':>5}")
    lines.append("-" * 48)

    num_zones = s["NoOfZones"]
    for i in range(num_zones):
        zdata = _query_zone(i)
        z = zdata.get("ZonesV2", zdata)
        zmode = ZONE_MODES_REV.get(z["Mode"], str(z["Mode"]))
        lines.append(f"{i:<3} {z['Name']:<12} {_fmt_temp(z['Temp']):>6} {_fmt_temp(z['Setpoint']):>6} {zmode:<10} {z['MaxAir']:>4}%")

    return "\n".join(lines)


@mcp.tool()
def izone_power(state: str) -> str:
    """Turn the AC system on or off.

    Args:
        state: "on" or "off"
    """
    if state.lower() not in ("on", "off"):
        return "Error: state must be 'on' or 'off'"
    val = 1 if state.lower() == "on" else 0
    result = _send_command({"SysOn": val})
    return f"System turned {state.upper()} ({result})"


@mcp.tool()
def izone_mode(mode: str) -> str:
    """Set the AC operating mode.

    Args:
        mode: One of "cool", "heat", "vent", "dry", "auto"
    """
    mode = mode.lower()
    if mode not in MODES:
        return f"Error: mode must be one of: {', '.join(MODES.keys())}"
    result = _send_command({"SysMode": mode})
    return f"Mode set to {mode} ({result})"


@mcp.tool()
def izone_fan(speed: str) -> str:
    """Set the fan speed.

    Args:
        speed: One of "low", "medium", "high", "auto", "top"
    """
    speed = speed.lower()
    if speed not in FAN_SPEEDS:
        return f"Error: speed must be one of: {', '.join(FAN_SPEEDS.keys())}"
    result = _send_command({"SysFan": speed})
    return f"Fan set to {speed} ({result})"


@mcp.tool()
def izone_temperature(temperature: float) -> str:
    """Set the system target temperature.

    Args:
        temperature: Target temperature in Celsius (15.0 to 30.0)
    """
    if temperature < 15 or temperature > 30:
        return "Error: temperature must be between 15.0 and 30.0"
    setpoint = int(temperature * 100)
    result = _send_command({"SysSetpoint": setpoint})
    return f"System temperature set to {temperature}C ({result})"


@mcp.tool()
def izone_zone_control(zone_index: int, mode: str = "", temperature: float = 0, max_airflow: int = -1, min_airflow: int = -1) -> str:
    """Control a specific zone. Pass only the parameters you want to change.

    Zone indexes: 0=Dining, 1=Lounge, 2=Master, 3=Lavinia, 4=Daedalus, 5=Study, 6=Upstairs

    Args:
        zone_index: Zone number (0-6)
        mode: Zone mode - "open", "close", or "auto" (empty string to leave unchanged)
        temperature: Zone temperature setpoint in Celsius, 15.0-30.0 (0 to leave unchanged)
        max_airflow: Max airflow percentage 0-100 (-1 to leave unchanged)
        min_airflow: Min airflow percentage 0-100 (-1 to leave unchanged)
    """
    if zone_index < 0 or zone_index > 6:
        return "Error: zone_index must be 0-6"

    results = []

    if mode:
        mode = mode.lower()
        if mode not in ZONE_MODES:
            return f"Error: mode must be one of: {', '.join(ZONE_MODES.keys())}"
        r = _send_command({"ZoneMode": {"Index": zone_index, "Mode": ZONE_MODES[mode]}})
        results.append(f"Mode set to {mode} ({r})")

    if temperature > 0:
        if temperature < 15 or temperature > 30:
            return "Error: temperature must be between 15.0 and 30.0"
        setpoint = round(int(temperature * 100) / 50) * 50
        r = _send_command({"ZoneSetpoint": {"Index": zone_index, "Setpoint": setpoint}})
        results.append(f"Temperature set to {setpoint / 100:.1f}C ({r})")

    if max_airflow >= 0:
        air = max(0, min(100, round(max_airflow / 5) * 5))
        r = _send_command({"ZoneMaxAir": {"Index": zone_index, "MaxAir": air}})
        results.append(f"Max airflow set to {air}% ({r})")

    if min_airflow >= 0:
        air = max(0, min(100, round(min_airflow / 5) * 5))
        r = _send_command({"ZoneMinAir": {"Index": zone_index, "MinAir": air}})
        results.append(f"Min airflow set to {air}% ({r})")

    if not results:
        # Just show zone info
        zdata = _query_zone(zone_index)
        z = zdata.get("ZonesV2", zdata)
        zmode = ZONE_MODES_REV.get(z["Mode"], str(z["Mode"]))
        return (
            f"Zone {zone_index}: {z['Name']}\n"
            f"  Temp: {_fmt_temp(z['Temp'])}C\n"
            f"  Setpoint: {_fmt_temp(z['Setpoint'])}C\n"
            f"  Mode: {zmode}\n"
            f"  Max Air: {z['MaxAir']}%\n"
            f"  Min Air: {z['MinAir']}%"
        )

    return f"Zone {zone_index}: " + "; ".join(results)


@mcp.tool()
def izone_comfort_setup(zones: str, temperature: float, mode: str = "cool", fan: str = "auto") -> str:
    """Quick comfort setup - turn on the AC, set mode/fan/temp, and open specified zones in auto mode. Closes all other zones.

    Args:
        zones: Comma-separated zone indexes to activate (e.g., "2,5" for Master and Study)
        temperature: Target temperature in Celsius (15.0 to 30.0)
        mode: AC mode - "cool", "heat", "vent", "dry", "auto" (default: cool)
        fan: Fan speed - "low", "medium", "high", "auto", "top" (default: auto)
    """
    active_zones = [int(z.strip()) for z in zones.split(",")]
    results = []

    # Turn on
    r = _send_command({"SysOn": 1})
    results.append(f"System ON ({r})")
    time.sleep(0.3)

    # Set mode
    r = _send_command({"SysMode": mode.lower()})
    results.append(f"Mode: {mode} ({r})")
    time.sleep(0.3)

    # Set fan
    r = _send_command({"SysFan": fan.lower()})
    results.append(f"Fan: {fan} ({r})")
    time.sleep(0.3)

    # Set system temp
    setpoint = int(temperature * 100)
    r = _send_command({"SysSetpoint": setpoint})
    results.append(f"Temp: {temperature}C ({r})")

    # Configure zones
    for i in range(7):
        time.sleep(0.2)
        if i in active_zones:
            _send_command({"ZoneMode": {"Index": i, "Mode": ZONE_MODES["auto"]}})
            _send_command({"ZoneSetpoint": {"Index": i, "Setpoint": setpoint}})
            results.append(f"Zone {i}: auto at {temperature}C")
        else:
            _send_command({"ZoneMode": {"Index": i, "Mode": ZONE_MODES["close"]}})
            results.append(f"Zone {i}: closed")

    return "\n".join(results)


if __name__ == "__main__":
    mcp.run()
