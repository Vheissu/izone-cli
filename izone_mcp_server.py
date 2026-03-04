#!/usr/bin/env python3
"""iZone MCP Server - Control your iZone AC through any MCP-compatible AI assistant."""

import http.client
import json
import os
import socket
import time

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("izone", instructions="""You control an iZone ducted air conditioning system.
Use the izone_status tool to discover the number of zones and their names before making changes.
Temperature values from the API are multiplied by 100 (e.g., 2400 = 24.0C).
When setting temperatures, accept normal values like 22.5 and convert to API format internally.
Always check current status before making changes. Be energy-conscious.

IMPORTANT: When making temporary changes (bedtime mode, working from home, etc.), ALWAYS call
izone_defaults_save first to snapshot the current settings, then make your changes. This lets the
user restore their normal settings later with izone_defaults_restore. Only skip saving if the user
explicitly says they want permanent changes.""")

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

    Use izone_status first to see available zone indexes and names.

    Args:
        zone_index: Zone number (0-based, run izone_status to see available zones)
        mode: Zone mode - "open", "close", or "auto" (empty string to leave unchanged)
        temperature: Zone temperature setpoint in Celsius, 15.0-30.0 (0 to leave unchanged)
        max_airflow: Max airflow percentage 0-100 (-1 to leave unchanged)
        min_airflow: Min airflow percentage 0-100 (-1 to leave unchanged)
    """
    sys_data = _query_system()
    num_zones = sys_data["SystemV2"]["NoOfZones"]
    if zone_index < 0 or zone_index >= num_zones:
        return f"Error: zone_index must be 0-{num_zones - 1}"

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
        zones: Comma-separated zone indexes to activate (e.g., "0,2" for the first and third zones)
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
    sys_data = _query_system()
    num_zones = sys_data["SystemV2"]["NoOfZones"]
    for i in range(num_zones):
        time.sleep(0.2)
        if i in active_zones:
            _send_command({"ZoneMode": {"Index": i, "Mode": ZONE_MODES["auto"]}})
            _send_command({"ZoneSetpoint": {"Index": i, "Setpoint": setpoint}})
            results.append(f"Zone {i}: auto at {temperature}C")
        else:
            _send_command({"ZoneMode": {"Index": i, "Mode": ZONE_MODES["close"]}})
            results.append(f"Zone {i}: closed")

    return "\n".join(results)


DEFAULTS_FILE = os.path.expanduser("~/.config/izone/defaults.json")


@mcp.tool()
def izone_defaults_save() -> str:
    """Save the current system and zone settings as defaults. Call this BEFORE making temporary changes
    (bedtime mode, working from home, etc.) so the user can restore their normal settings later."""
    data = _query_system()
    s = data["SystemV2"]
    num_zones = s["NoOfZones"]
    defaults = {
        "mode": s["SysMode"],
        "fan": s["SysFan"],
        "setpoint": s["Setpoint"],
        "zones": [],
    }
    for i in range(num_zones):
        zdata = _query_zone(i)
        z = zdata.get("ZonesV2", zdata)
        defaults["zones"].append({
            "index": i,
            "name": z["Name"],
            "mode": z["Mode"],
            "setpoint": z["Setpoint"],
            "max_air": z["MaxAir"],
            "min_air": z["MinAir"],
        })
    os.makedirs(os.path.dirname(DEFAULTS_FILE), exist_ok=True)
    with open(DEFAULTS_FILE, "w") as f:
        json.dump(defaults, f, indent=2)
    mode = MODES_REV.get(defaults["mode"], str(defaults["mode"]))
    fan = FAN_REV.get(defaults["fan"], str(defaults["fan"]))
    return f"Defaults saved: mode={mode}, fan={fan}, temp={_fmt_temp(defaults['setpoint'])}C, {len(defaults['zones'])} zones"


@mcp.tool()
def izone_defaults_restore() -> str:
    """Restore previously saved default settings. Use this to undo temporary changes and return
    the system to its normal configuration."""
    if not os.path.exists(DEFAULTS_FILE):
        return "No saved defaults found. Save defaults first with izone_defaults_save."
    with open(DEFAULTS_FILE) as f:
        defaults = json.load(f)
    _send_command({"SysMode": defaults["mode"]})
    time.sleep(0.2)
    _send_command({"SysFan": defaults["fan"]})
    time.sleep(0.2)
    _send_command({"SysSetpoint": defaults["setpoint"]})
    for z in defaults["zones"]:
        time.sleep(0.2)
        _send_command({"ZoneMode": {"Index": z["index"], "Mode": z["mode"]}})
        _send_command({"ZoneSetpoint": {"Index": z["index"], "Setpoint": z["setpoint"]}})
        _send_command({"ZoneMaxAir": {"Index": z["index"], "MaxAir": z["max_air"]}})
        _send_command({"ZoneMinAir": {"Index": z["index"], "MinAir": z["min_air"]}})
    mode = MODES_REV.get(defaults["mode"], str(defaults["mode"]))
    fan = FAN_REV.get(defaults["fan"], str(defaults["fan"]))
    return f"Defaults restored: mode={mode}, fan={fan}, temp={_fmt_temp(defaults['setpoint'])}C, {len(defaults['zones'])} zones"


NUM_SCHEDULE_SLOTS = 9


def _query_schedule(index: int) -> dict:
    raw = _post("/iZoneRequestV2", {"iZoneV2Request": {"Type": 3, "No": index, "No1": 0}})
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        time.sleep(0.3)
        raw = _post("/iZoneRequestV2", {"iZoneV2Request": {"Type": 3, "No": index, "No1": 0}})
        return json.loads(raw)


def _fmt_sched_time(h, m):
    if h >= 31 or m >= 63:
        return "--:--"
    return f"{h:02d}:{m:02d}"


def _fmt_days(days):
    day_map = [("M", "M"), ("Tu", "Tu"), ("W", "W"), ("Th", "Th"), ("F", "F"), ("Sa", "Sa"), ("Su", "Su")]
    active = [label for key, label in day_map if days.get(key)]
    return " ".join(active) if active else "none"


@mcp.tool()
def izone_schedules() -> str:
    """List all schedule slots with name, enabled status, timing, mode, fan, and active days."""
    lines = [f"{'#':<3} {'Name':<16} {'Enabled':<9} {'Start':>5} {'Stop':>5}  {'Mode':<6} {'Fan':<7} Days", "-" * 75]
    for i in range(NUM_SCHEDULE_SLOTS):
        try:
            data = _query_schedule(i)
            s = data.get("SchedulesV2", {})
            name = s.get("Name", "").strip() or "(empty)"
            enabled = "yes" if s.get("Enabled") else "no"
            start = _fmt_sched_time(s.get("StartH", 255), s.get("StartM", 255))
            stop = _fmt_sched_time(s.get("StopH", 255), s.get("StopM", 255))
            mode = MODES_REV.get(s.get("Mode"), str(s.get("Mode", "?")))
            fan = FAN_REV.get(s.get("Fan"), str(s.get("Fan", "?")))
            days = _fmt_days(s.get("DaysEnabled", {}))
            lines.append(f"{i:<3} {name:<16} {enabled:<9} {start:>5} {stop:>5}  {mode:<6} {fan:<7} {days}")
        except (json.JSONDecodeError, KeyError):
            lines.append(f"{i:<3} (unavailable)")
    return "\n".join(lines)


@mcp.tool()
def izone_schedule_detail(slot: int) -> str:
    """Show full details of a schedule slot including per-zone mode and setpoint.

    Args:
        slot: Schedule index (0-8)
    """
    if slot < 0 or slot >= NUM_SCHEDULE_SLOTS:
        return f"Error: slot must be 0-{NUM_SCHEDULE_SLOTS - 1}"
    try:
        data = _query_schedule(slot)
        s = data.get("SchedulesV2", {})
    except Exception:
        return f"Schedule {slot} is unavailable."
    sys_data = _query_system()
    num_zones = sys_data["SystemV2"]["NoOfZones"]
    name = s.get("Name", "").strip() or "(empty)"
    lines = [
        f"Schedule {slot}: {name}",
        f"  Enabled:  {'yes' if s.get('Enabled') else 'no'}",
        f"  Start:    {_fmt_sched_time(s.get('StartH', 255), s.get('StartM', 255))}",
        f"  Stop:     {_fmt_sched_time(s.get('StopH', 255), s.get('StopM', 255))}",
        f"  Mode:     {MODES_REV.get(s.get('Mode'), str(s.get('Mode', '?')))}",
        f"  Fan:      {FAN_REV.get(s.get('Fan'), str(s.get('Fan', '?')))}",
        f"  Days:     {_fmt_days(s.get('DaysEnabled', {}))}",
        "",
        f"  {'#':<3} {'Mode':<10} {'Setpoint':>8}",
        f"  {'-' * 24}",
    ]
    for zi, z in enumerate(s.get("Zones", [])[:num_zones]):
        zmode = ZONE_MODES_REV.get(z.get("Mode"), str(z.get("Mode", "?")))
        lines.append(f"  {zi:<3} {zmode:<10} {_fmt_temp(z.get('Setpoint', 0)):>7}C")
    return "\n".join(lines)


@mcp.tool()
def izone_schedule_edit(slot: int, name: str = "", mode: str = "", fan: str = "", start: str = "", stop: str = "", days: str = "", enabled: str = "") -> str:
    """Edit a schedule's settings. Only pass the parameters you want to change.

    Args:
        slot: Schedule index (0-8)
        name: Schedule name, max 15 chars (empty to leave unchanged)
        mode: AC mode - cool, heat, vent, dry, auto (empty to leave unchanged)
        fan: Fan speed - low, medium, high, auto, top (empty to leave unchanged)
        start: Start time as HH:MM or "off" to disable (empty to leave unchanged)
        stop: Stop time as HH:MM or "off" to disable (empty to leave unchanged)
        days: Comma-separated: M,Tu,W,Th,F,Sa,Su,weekdays,weekends,all (empty to leave unchanged)
        enabled: "true" or "false" (empty to leave unchanged)
    """
    if slot < 0 or slot >= NUM_SCHEDULE_SLOTS:
        return f"Error: slot must be 0-{NUM_SCHEDULE_SLOTS - 1}"
    results = []
    if name:
        _send_command({"SchedName": {"Index": slot, "Name": name[:15]}})
        results.append(f"Name set to \"{name[:15]}\"")
    if mode:
        if mode.lower() not in MODES:
            return f"Error: mode must be one of: {', '.join(MODES.keys())}"
        _send_command({"SchedAcMode": {"Index": slot, "Mode": MODES[mode.lower()]}})
        results.append(f"Mode set to {mode}")
    if fan:
        if fan.lower() not in FAN_SPEEDS:
            return f"Error: fan must be one of: {', '.join(FAN_SPEEDS.keys())}"
        _send_command({"SchedAcFan": {"Index": slot, "Fan": fan.lower()}})
        results.append(f"Fan set to {fan}")
    if start or stop or days:
        settings = {"Index": slot}
        if start:
            if start == "off":
                settings["StartH"] = 31
                settings["StartM"] = 63
            else:
                h, m = start.split(":")
                settings["StartH"] = int(h)
                settings["StartM"] = int(m)
        if stop:
            if stop == "off":
                settings["StopH"] = 31
                settings["StopM"] = 63
            else:
                h, m = stop.split(":")
                settings["StopH"] = int(h)
                settings["StopM"] = int(m)
        if days:
            day_keys = ["M", "Tu", "W", "Th", "F", "Sa", "Su"]
            day_labels = {"m": "M", "tu": "Tu", "w": "W", "th": "Th", "f": "F", "sa": "Sa", "su": "Su"}
            days_enabled = {k: 0 for k in day_keys}
            for d in days.lower().split(","):
                d = d.strip()
                if d == "weekdays":
                    for k in ["M", "Tu", "W", "Th", "F"]:
                        days_enabled[k] = 1
                elif d == "weekends":
                    for k in ["Sa", "Su"]:
                        days_enabled[k] = 1
                elif d == "all":
                    days_enabled = {k: 1 for k in day_keys}
                elif d in day_labels:
                    days_enabled[day_labels[d]] = 1
            settings["DaysEnabled"] = days_enabled
        _send_command({"SchedSettings": settings})
        results.append("Timing updated")
    if enabled:
        val = 1 if enabled.lower() in ("true", "1", "yes", "on") else 0
        _send_command({"SchedEnable": {"Index": slot, "Enabled": val}})
        results.append("Enabled" if val else "Disabled")
    if not results:
        return "No changes specified."
    return f"Schedule {slot}: " + "; ".join(results)


@mcp.tool()
def izone_run_schedule(slot: int) -> str:
    """Run a schedule immediately as a scene/favourite without enabling its timer.

    Args:
        slot: Schedule index (0-8)
    """
    if slot < 0 or slot >= NUM_SCHEDULE_SLOTS:
        return f"Error: slot must be 0-{NUM_SCHEDULE_SLOTS - 1}"
    result = _send_command({"FavouriteSet": slot + 1})
    return f"Schedule {slot} activated ({result})"


if __name__ == "__main__":
    mcp.run()
