#!/usr/bin/env python3
"""iZone MCP Server - Control your iZone AC through any MCP-compatible AI assistant."""

import http.client
import json
import os
import socket
import threading
import time

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("izone", instructions="""You control an iZone ducted air conditioning system.
Use the izone_status tool to discover the number of zones and their names before making changes.
Temperature values from the API are multiplied by 100 (e.g., 2400 = 24.0C).
When setting temperatures, accept normal values like 22.5 and convert to API format internally.
Always check current status before making changes. Be energy-conscious.

BE INTELLIGENT: For any open-ended request ("make it comfortable", "it's hot", "sort the AC out"),
prefer izone_recommend over manually composing commands — it weighs indoor readings, outdoor
weather, and the forecast, and can apply its own plan. Use izone_insights for a health/efficiency
review and izone_history to see how zones have tracked over time. Every status poll is logged
automatically, so history gets richer the more the system is used. If weather-aware features
report no location, offer to set one up once with izone_set_location.

IMPORTANT: When making temporary changes (bedtime mode, working from home, etc.), ALWAYS call
izone_defaults_save first to snapshot the current settings, then make your changes. This lets the
user restore their normal settings later with izone_defaults_restore. Only skip saving if the user
explicitly says they want permanent changes.

PROFILES: The user can define named profiles (e.g., "summer-day", "bedtime") that bundle mode, fan,
temp, and per-zone settings. Use izone_profiles to list them, izone_apply_profile to apply one,
izone_save_profile to capture current settings as a profile, or izone_create_profile to define one
from parameters. When the user asks to set up or save their preferred settings, suggest profiles.""")

# --- iZone protocol constants ---
DISCOVERY_PORT = 12107
BRIDGE_IP_CACHE = os.path.expanduser("~/.config/izone/bridge_ip")
HTTP_TIMEOUT = 5
HTTP_RETRIES = int(os.getenv("IZONE_HTTP_RETRIES", "4"))
HTTP_RETRY_DELAY = float(os.getenv("IZONE_HTTP_RETRY_DELAY", "0.25"))
HTTP_MIN_GAP = float(os.getenv("IZONE_HTTP_MIN_GAP", "0.25"))
TRANSIENT_RESPONSES = {"{ERROR}", "ERROR", "{BUSY}", "BUSY"}
REQUEST_ERRORS = (socket.timeout, TimeoutError, OSError, http.client.HTTPException)

MODES = {"cool": 1, "heat": 2, "vent": 3, "dry": 4, "auto": 5}
MODES_REV = {v: k for k, v in MODES.items()}
FAN_SPEEDS = {"low": 1, "medium": 2, "high": 3, "auto": 4, "top": 5}
FAN_REV = {v: k for k, v in FAN_SPEEDS.items()}
ZONE_MODES = {"open": 1, "close": 2, "auto": 3, "override": 4, "constant": 5}
ZONE_MODES_REV = {v: k for k, v in ZONE_MODES.items()}
_request_lock = threading.Lock()
_last_request_started = 0.0


def _retry_delay(attempt: int) -> float:
    return HTTP_RETRY_DELAY * (attempt + 1)


def _normalize_response(raw: str) -> str:
    return raw.strip().upper()


def _pace_requests():
    global _last_request_started
    now = time.monotonic()
    wait_for = HTTP_MIN_GAP - (now - _last_request_started)
    if wait_for > 0:
        time.sleep(wait_for)
    _last_request_started = time.monotonic()


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
    body = json.dumps(payload)
    with _request_lock:
        _pace_requests()
        conn = http.client.HTTPConnection(ip, 80, timeout=HTTP_TIMEOUT)
        try:
            conn.request("POST", endpoint, body=body, headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8", errors="replace").strip()
        finally:
            conn.close()
    if raw.endswith("{OK}"):
        raw = raw[:-4]
    return raw


def _json_request(endpoint: str, payload: dict, retries: int = HTTP_RETRIES) -> dict:
    """POST JSON request and retry transient transport or bridge-side errors."""
    attempts = max(1, int(retries))
    last_raw = ""
    last_error = None

    for attempt in range(attempts):
        try:
            raw = _post(endpoint, payload)
        except REQUEST_ERRORS as e:
            last_error = e
            if attempt < attempts - 1:
                time.sleep(_retry_delay(attempt))
                continue
            raise

        last_raw = raw
        if _normalize_response(raw) in TRANSIENT_RESPONSES and attempt < attempts - 1:
            time.sleep(_retry_delay(attempt))
            continue

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            last_error = e
            if attempt < attempts - 1:
                time.sleep(_retry_delay(attempt))
                continue
            snippet = raw if len(raw) <= 120 else raw[:117] + "..."
            raise RuntimeError(f"Bridge returned non-JSON response: {snippet!r}") from e

    snippet = last_raw if len(last_raw) <= 120 else last_raw[:117] + "..."
    raise RuntimeError(f"Bridge returned non-JSON response: {snippet!r}") from last_error


def _query_system() -> dict:
    return _json_request("/iZoneRequestV2", {"iZoneV2Request": {"Type": 1, "No": 0, "No1": 0}}, retries=max(4, HTTP_RETRIES))


def _query_zone(index: int) -> dict:
    return _json_request("/iZoneRequestV2", {"iZoneV2Request": {"Type": 2, "No": index, "No1": 0}}, retries=max(3, HTTP_RETRIES))


def _send_command(payload: dict, retries: int = HTTP_RETRIES) -> str:
    attempts = max(1, int(retries))
    last_raw = ""
    for attempt in range(attempts):
        try:
            raw = _post("/iZoneCommandV2", payload)
        except REQUEST_ERRORS:
            if attempt < attempts - 1:
                time.sleep(_retry_delay(attempt))
                continue
            raise

        last_raw = raw
        normalized = _normalize_response(raw)
        if normalized in ("", "OK"):
            return raw
        if normalized in TRANSIENT_RESPONSES and attempt < attempts - 1:
            time.sleep(_retry_delay(attempt))
            continue
        return raw
    return last_raw


def _mode_to_value(mode) -> int:
    """Normalize mode input (name or number) to protocol integer."""
    if isinstance(mode, str):
        key = mode.strip().lower()
        if key in MODES:
            return MODES[key]
        if key.isdigit():
            mode = int(key)
        else:
            raise ValueError(f"Invalid mode: {mode}")
    if isinstance(mode, (int, float)):
        mode = int(mode)
        if mode in MODES_REV:
            return mode
    raise ValueError(f"Invalid mode: {mode}")


def _fan_to_value(fan) -> int:
    """Normalize fan input (name or number) to protocol integer."""
    if isinstance(fan, str):
        key = fan.strip().lower()
        if key in FAN_SPEEDS:
            return FAN_SPEEDS[key]
        if key.isdigit():
            fan = int(key)
        else:
            raise ValueError(f"Invalid fan speed: {fan}")
    if isinstance(fan, (int, float)):
        fan = int(fan)
        if fan in FAN_REV:
            return fan
    raise ValueError(f"Invalid fan speed: {fan}")


def _mode_label(mode) -> str:
    if isinstance(mode, str):
        key = mode.strip().lower()
        if key in MODES:
            return key
        if key.isdigit():
            mode = int(key)
        else:
            return mode
    if isinstance(mode, (int, float)):
        return MODES_REV.get(int(mode), str(mode))
    return str(mode)


def _fan_label(fan) -> str:
    if isinstance(fan, str):
        key = fan.strip().lower()
        if key in FAN_SPEEDS:
            return key
        if key.isdigit():
            fan = int(key)
        else:
            return fan
    if isinstance(fan, (int, float)):
        return FAN_REV.get(int(fan), str(fan))
    return str(fan)


def _fmt_temp(val) -> str:
    if isinstance(val, (int, float)):
        return f"{val / 100:.1f}"
    return str(val)


# --- Config (location etc.) ---

CONFIG_FILE = os.path.expanduser("~/.config/izone/config.json")


def _load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_config(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# --- Outdoor weather (Open-Meteo, no API key; skipped when no location is configured) ---

WEATHER_CACHE_TTL = 900
WEATHER_FAIL_TTL = 60
_weather_cache = {"ts": 0.0, "data": None, "fail_ts": 0.0}


def _http_get_json(url: str, timeout: int = 6) -> dict:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "izone-mcp"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def _get_weather() -> dict | None:
    """Current outdoor conditions + 12h forecast, or None if no location / lookup fails."""
    loc = _load_config().get("location")
    if not loc:
        return None
    if _weather_cache["data"] and time.time() - _weather_cache["ts"] < WEATHER_CACHE_TTL:
        return _weather_cache["data"]
    if time.time() - _weather_cache["fail_ts"] < WEATHER_FAIL_TTL:
        return None  # recent lookup failed; don't stall every poll retrying
    import urllib.parse
    params = urllib.parse.urlencode({
        "latitude": loc["lat"],
        "longitude": loc["lon"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature",
        "hourly": "temperature_2m",
        "forecast_hours": 12,
        "timezone": "auto",
    })
    try:
        data = _http_get_json("https://api.open-meteo.com/v1/forecast?" + params)
        cur = data.get("current", {})
        hourly_temps = data.get("hourly", {}).get("temperature_2m", []) or []
        weather = {
            "place": loc.get("name", ""),
            "temp": cur.get("temperature_2m"),
            "feels_like": cur.get("apparent_temperature"),
            "humidity": cur.get("relative_humidity_2m"),
            "forecast_12h": hourly_temps,
            "forecast_max": max(hourly_temps) if hourly_temps else None,
            "forecast_min": min(hourly_temps) if hourly_temps else None,
        }
        _weather_cache["ts"] = time.time()
        _weather_cache["data"] = weather
        return weather
    except Exception:
        _weather_cache["fail_ts"] = time.time()
        return None


# --- History (auto-logged snapshots of every full status poll) ---

HISTORY_FILE = os.path.expanduser("~/.config/izone/history.jsonl")
HISTORY_MAX_BYTES = 4_000_000
HISTORY_KEEP_BYTES = 2_000_000


def _full_state() -> tuple:
    """Query system + all zones, log a history snapshot, and return (system, zones)."""
    data = _query_system()
    s = data["SystemV2"]
    zones = []
    for i in range(s["NoOfZones"]):
        zdata = _query_zone(i)
        z = zdata.get("ZonesV2", zdata)
        zones.append(z)
    _log_snapshot(s, zones)
    return s, zones


def _log_snapshot(s: dict, zones: list):
    try:
        rec = {
            "ts": int(time.time()),
            "on": int(bool(s.get("SysOn"))),
            "mode": s.get("SysMode"),
            "fan": s.get("SysFan"),
            "set": s.get("Setpoint"),
            "temp": s.get("Temp"),
            "supply": s.get("Supply"),
            "rh": s.get("InRh"),
            "eco2": s.get("IneCO2"),
            "tvoc": s.get("InTVOC"),
            "zones": [
                {"n": z.get("Name", ""), "t": z.get("Temp"), "s": z.get("Setpoint"), "m": z.get("Mode")}
                for z in zones
            ],
        }
        w = _get_weather()
        if w and w.get("temp") is not None:
            rec["out"] = w["temp"]
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "a") as f:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
        if os.path.getsize(HISTORY_FILE) > HISTORY_MAX_BYTES:
            with open(HISTORY_FILE, "rb") as f:
                f.seek(-HISTORY_KEEP_BYTES, os.SEEK_END)
                tail = f.read()
            tail = tail[tail.index(b"\n") + 1:] if b"\n" in tail else tail
            with open(HISTORY_FILE, "wb") as f:
                f.write(tail)
    except Exception:
        pass  # history is best-effort; never let logging break a live command


def _read_history(hours: float) -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    cutoff = time.time() - hours * 3600
    out = []
    with open(HISTORY_FILE) as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("ts", 0) >= cutoff:
                out.append(rec)
    return out


SPARK_CHARS = "▁▂▃▄▅▆▇█"


def _sparkline(values: list, buckets: int = 24) -> str:
    vals = [v for v in values if isinstance(v, (int, float))]
    if not vals:
        return ""
    if len(vals) > buckets:
        step = len(vals) / buckets
        vals = [vals[int(i * step)] for i in range(buckets)]
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        return SPARK_CHARS[3] * len(vals)
    return "".join(SPARK_CHARS[int((v - lo) / (hi - lo) * (len(SPARK_CHARS) - 1))] for v in vals)


# --- MCP Tools ---

@mcp.tool()
def izone_status() -> str:
    """Get the full status of the iZone AC system including all zones.
    Returns system power state, mode, fan speed, temperatures, humidity, air quality, outdoor
    weather (when a location is configured), and all zone details. Each call also logs a
    history snapshot used by izone_history and izone_insights."""
    s, zones = _full_state()
    on_off = "ON" if s["SysOn"] else "OFF"
    mode = _mode_label(s["SysMode"])
    fan = _fan_label(s["SysFan"])

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

    w = _get_weather()
    if w and w.get("temp") is not None:
        outdoor = f"Outdoor: {w['temp']:.1f}C"
        if w.get("feels_like") is not None:
            outdoor += f" (feels like {w['feels_like']:.1f}C)"
        if w.get("forecast_max") is not None:
            outdoor += f", next 12h {w['forecast_min']:.0f}-{w['forecast_max']:.0f}C"
        lines.append(outdoor)

    lines.append("")
    lines.append(f"{'#':<3} {'Name':<12} {'Temp':>6} {'Set':>6} {'Mode':<10} {'Air%':>5}")
    lines.append("-" * 48)

    for i, z in enumerate(zones):
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
    result = _send_command({"SysMode": MODES[mode]})
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
    result = _send_command({"SysFan": FAN_SPEEDS[speed]})
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


def _schedule_restore(minutes: int):
    """Spawn a background process that restores defaults after the given minutes."""
    import subprocess, sys
    restore_marker = DEFAULTS_FILE.replace("defaults.json", "restore_pending")
    os.makedirs(os.path.dirname(restore_marker), exist_ok=True)
    with open(restore_marker, "w") as f:
        f.write(str(os.getpid()))
    izone_cli = os.path.join(os.path.dirname(os.path.realpath(__file__)), "izone")
    subprocess.Popen(
        ["bash", "-c", f'sleep {minutes * 60} && [ -f "{restore_marker}" ] && "{sys.executable}" "{izone_cli}" defaults restore && rm -f "{restore_marker}"'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _cancel_pending_restore():
    restore_marker = DEFAULTS_FILE.replace("defaults.json", "restore_pending")
    if os.path.exists(restore_marker):
        os.remove(restore_marker)


@mcp.tool()
def izone_comfort_setup(zones: str, temperature: float, mode: str = "cool", fan: str = "auto", sleep_timer: int = 0) -> str:
    """Quick comfort setup - turn on the AC, set mode/fan/temp, and open specified zones in auto mode.
    Closes all other zones. Automatically saves defaults before making changes.

    If sleep_timer is set, the AC will turn off after that many minutes AND defaults will be
    automatically restored — so temporary settings like bedtime mode don't become permanent.

    Args:
        zones: Comma-separated zone indexes to activate (e.g., "0,2" for the first and third zones)
        temperature: Target temperature in Celsius (15.0 to 30.0)
        mode: AC mode - "cool", "heat", "vent", "dry", "auto" (default: cool)
        fan: Fan speed - "low", "medium", "high", "auto", "top" (default: auto)
        sleep_timer: Minutes until auto-off with auto-restore of defaults (0 to disable)
    """
    results = []

    # Save defaults before making temporary changes
    izone_defaults_save()
    results.append("Defaults saved")

    active_zones = [int(z.strip()) for z in zones.split(",")]

    # Turn on
    r = _send_command({"SysOn": 1})
    results.append(f"System ON ({r})")
    time.sleep(0.3)

    # Set mode
    mode_key = mode.lower()
    if mode_key not in MODES:
        return f"Error: mode must be one of: {', '.join(MODES.keys())}"
    r = _send_command({"SysMode": MODES[mode_key]})
    results.append(f"Mode: {mode} ({r})")
    time.sleep(0.3)

    # Set fan
    fan_key = fan.lower()
    if fan_key not in FAN_SPEEDS:
        return f"Error: fan must be one of: {', '.join(FAN_SPEEDS.keys())}"
    r = _send_command({"SysFan": FAN_SPEEDS[fan_key]})
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
            z = _query_zone(i).get("ZonesV2", {})
            if _zone_is_constant(z):
                results.append(f"Zone {i}: left open (constant zone — must stay open)")
            else:
                _send_command({"ZoneMode": {"Index": i, "Mode": ZONE_MODES["close"]}})
                results.append(f"Zone {i}: closed")

    # Set sleep timer and schedule auto-restore
    if sleep_timer > 0:
        _send_command({"SysSleepTimer": sleep_timer})
        _schedule_restore(sleep_timer)
        results.append(f"Sleep timer: {sleep_timer} min (defaults will auto-restore)")

    return "\n".join(results)


DEFAULTS_FILE = os.path.expanduser("~/.config/izone/defaults.json")


@mcp.tool()
def izone_defaults_save() -> str:
    """Save the current system and zone settings as defaults. Call this BEFORE making temporary changes
    (bedtime mode, working from home, etc.) so the user can restore their normal settings later."""
    s, zones = _full_state()
    defaults = {
        "mode": s["SysMode"],
        "fan": s["SysFan"],
        "setpoint": s["Setpoint"],
        "zones": [],
    }
    for i, z in enumerate(zones):
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
    try:
        mode_value = _mode_to_value(defaults["mode"])
        fan_value = _fan_to_value(defaults["fan"])
    except ValueError as e:
        return f"Error: saved defaults are invalid: {e}"

    _send_command({"SysMode": mode_value})
    time.sleep(0.2)
    _send_command({"SysFan": fan_value})
    time.sleep(0.2)
    _send_command({"SysSetpoint": defaults["setpoint"]})
    for z in defaults["zones"]:
        time.sleep(0.2)
        _send_command({"ZoneMode": {"Index": z["index"], "Mode": z["mode"]}})
        if z["mode"] != ZONE_MODES["close"]:
            _send_command({"ZoneSetpoint": {"Index": z["index"], "Setpoint": z["setpoint"]}})
        _send_command({"ZoneMaxAir": {"Index": z["index"], "MaxAir": z["max_air"]}})
        _send_command({"ZoneMinAir": {"Index": z["index"], "MinAir": z["min_air"]}})
    mode = _mode_label(defaults["mode"])
    fan = _fan_label(defaults["fan"])
    return f"Defaults restored: mode={mode}, fan={fan}, temp={_fmt_temp(defaults['setpoint'])}C, {len(defaults['zones'])} zones"


NUM_SCHEDULE_SLOTS = 9


def _query_schedule(index: int) -> dict:
    return _json_request("/iZoneRequestV2", {"iZoneV2Request": {"Type": 3, "No": index, "No1": 0}}, retries=max(3, HTTP_RETRIES))


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
        _send_command({"SchedAcFan": {"Index": slot, "Fan": FAN_SPEEDS[fan.lower()]}})
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


PROFILES_FILE = os.path.expanduser("~/.config/izone/profiles.json")


def _load_profiles() -> dict:
    if os.path.exists(PROFILES_FILE):
        with open(PROFILES_FILE) as f:
            return json.load(f)
    return {}


def _save_profiles(profiles: dict):
    os.makedirs(os.path.dirname(PROFILES_FILE), exist_ok=True)
    with open(PROFILES_FILE, "w") as f:
        json.dump(profiles, f, indent=2)


@mcp.tool()
def izone_profiles() -> str:
    """List all saved AC profiles with their settings summary."""
    profiles = _load_profiles()
    if not profiles:
        return "No profiles saved. Use izone_save_profile to create one from current settings, or izone_create_profile to define one manually."
    lines = [f"{'Name':<20} {'Mode':<8} {'Fan':<8} {'Temp':>6} {'Zones':>6}", "-" * 52]
    for name, p in sorted(profiles.items()):
        mode = p.get("mode", "?")
        fan = p.get("fan", "?")
        temp = _fmt_temp(p.get("temp", 0))
        zone_count = len(p.get("zones", {}))
        lines.append(f"{name:<20} {mode:<8} {fan:<8} {temp:>5}C {zone_count:>5}")
    return "\n".join(lines)


@mcp.tool()
def izone_save_profile(name: str) -> str:
    """Save the current live AC settings as a named profile. Use this to capture the current
    state so it can be re-applied later with izone_apply_profile.

    Args:
        name: Profile name (e.g., "summer-day", "bedtime", "working-from-home")
    """
    s, zones = _full_state()

    profile = {
        "mode": MODES_REV.get(s["SysMode"], str(s["SysMode"])),
        "fan": FAN_REV.get(s["SysFan"], str(s["SysFan"])),
        "temp": s["Setpoint"],
        "close_others": True,
        "zones": {},
    }
    for i, z in enumerate(zones):
        profile["zones"][str(i)] = {
            "mode": z["Mode"],
            "temp": z["Setpoint"],
        }

    profiles = _load_profiles()
    profiles[name] = profile
    _save_profiles(profiles)
    return f"Profile '{name}' saved (mode={profile['mode']}, fan={profile['fan']}, temp={_fmt_temp(profile['temp'])}C, {len(profile['zones'])} zones)"


@mcp.tool()
def izone_apply_profile(name: str) -> str:
    """Apply a saved profile. Turns on the AC and sets mode, fan, temperature, and zone
    configurations. Zones not listed in the profile are closed (unless close_others is false).

    Args:
        name: Profile name to apply
    """
    profiles = _load_profiles()
    if name not in profiles:
        available = ", ".join(sorted(profiles.keys())) if profiles else "none"
        return f"Profile '{name}' not found. Available profiles: {available}"

    profile = profiles[name]
    results = []

    # Turn on
    r = _send_command({"SysOn": 1})
    results.append(f"System ON ({r})")
    time.sleep(0.2)

    if "mode" in profile:
        try:
            mode_value = _mode_to_value(profile["mode"])
        except ValueError as e:
            return f"Error: profile '{name}' has invalid mode value: {e}"
        r = _send_command({"SysMode": mode_value})
        results.append(f"Mode: {_mode_label(profile['mode'])} ({r})")
        time.sleep(0.2)

    if "fan" in profile:
        try:
            fan_value = _fan_to_value(profile["fan"])
        except ValueError as e:
            return f"Error: profile '{name}' has invalid fan value: {e}"
        r = _send_command({"SysFan": fan_value})
        results.append(f"Fan: {_fan_label(profile['fan'])} ({r})")
        time.sleep(0.2)

    if "temp" in profile:
        r = _send_command({"SysSetpoint": profile["temp"]})
        results.append(f"Temp: {_fmt_temp(profile['temp'])}C ({r})")
        time.sleep(0.2)

    # Configure zones
    sys_data = _query_system()
    num_zones = sys_data["SystemV2"]["NoOfZones"]
    zone_configs = profile.get("zones", {})

    for i in range(num_zones):
        si = str(i)
        if si in zone_configs:
            zconf = zone_configs[si]
            _send_command({"ZoneMode": {"Index": i, "Mode": zconf["mode"]}})
            _send_command({"ZoneSetpoint": {"Index": i, "Setpoint": zconf["temp"]}})
            zmode = ZONE_MODES_REV.get(zconf["mode"], str(zconf["mode"]))
            results.append(f"Zone {i}: {zmode} at {_fmt_temp(zconf['temp'])}C")
        elif profile.get("close_others", True):
            z = _query_zone(i).get("ZonesV2", {})
            if _zone_is_constant(z):
                results.append(f"Zone {i}: left open (constant zone — must stay open)")
            else:
                _send_command({"ZoneMode": {"Index": i, "Mode": ZONE_MODES["close"]}})
                results.append(f"Zone {i}: closed")
        time.sleep(0.2)

    return f"Profile '{name}' applied:\n" + "\n".join(results)


@mcp.tool()
def izone_create_profile(name: str, mode: str = "cool", fan: str = "auto", temperature: float = 23.0, zones: str = "", close_others: bool = True) -> str:
    """Create or update a named profile from parameters WITHOUT changing the AC.
    Use this to define a profile manually, then apply it later with izone_apply_profile.

    Args:
        name: Profile name (e.g., "summer-day", "bedtime")
        mode: AC mode - "cool", "heat", "vent", "dry", "auto"
        fan: Fan speed - "low", "medium", "high", "auto", "top"
        temperature: System setpoint in Celsius (15.0-30.0)
        zones: Zone configs as "index:temp,index:temp" (e.g., "2:22,5:23"). Zones listed are set to auto mode at the given temp. Leave empty to include all zones at the system temp.
        close_others: If true, zones not listed are closed when applied (default: true)
    """
    if mode.lower() not in MODES:
        return f"Error: mode must be one of: {', '.join(MODES.keys())}"
    if fan.lower() not in FAN_SPEEDS:
        return f"Error: fan must be one of: {', '.join(FAN_SPEEDS.keys())}"
    if temperature < 15 or temperature > 30:
        return "Error: temperature must be between 15.0 and 30.0"

    sys_temp = int(temperature * 100)
    profile = {
        "mode": mode.lower(),
        "fan": fan.lower(),
        "temp": sys_temp,
        "close_others": close_others,
        "zones": {},
    }

    if zones:
        for pair in zones.split(","):
            pair = pair.strip()
            if ":" in pair:
                idx, temp = pair.split(":", 1)
                temp_val = float(temp)
                if temp_val < 15 or temp_val > 30:
                    return f"Error: zone temperature must be between 15.0 and 30.0 (got {temp_val})"
                setpoint = round(int(temp_val * 100) / 50) * 50
                profile["zones"][idx.strip()] = {"mode": ZONE_MODES["auto"], "temp": setpoint}
            else:
                profile["zones"][pair.strip()] = {"mode": ZONE_MODES["auto"], "temp": sys_temp}

    profiles = _load_profiles()
    profiles[name] = profile
    _save_profiles(profiles)

    zone_count = len(profile["zones"])
    zone_desc = f", {zone_count} zones" if zone_count else ", all zones at system temp"
    return f"Profile '{name}' created (mode={mode}, fan={fan}, temp={temperature}C{zone_desc})"


# --- Intelligence tools ---


@mcp.tool()
def izone_set_location(place: str) -> str:
    """Set the home location for outdoor-weather-aware features (insights, recommendations,
    outdoor line in status). One-time setup; geocoded via Open-Meteo (no API key).

    Args:
        place: Suburb/city, optionally qualified: "Perth", "Paddington, Brisbane",
               "Richmond, Victoria", "Springfield, USA"
    """
    import urllib.parse

    def _geocode(name: str, count: int = 10) -> list:
        params = urllib.parse.urlencode({"name": name, "count": count, "language": "en", "format": "json"})
        data = _http_get_json("https://geocoding-api.open-meteo.com/v1/search?" + params)
        return data.get("results") or []

    parts = [p.strip() for p in place.split(",") if p.strip()]
    if not parts:
        return "Error: empty place name"
    try:
        results = _geocode(parts[0])
    except Exception as e:
        return f"Error: geocoding lookup failed ({e})"
    if not results:
        return f"Error: no location found for {parts[0]!r}. Try the suburb name alone, or add a qualifier after a comma."

    r = results[0]
    if len(parts) > 1 and len(results) > 1:
        # Disambiguate with the qualifier: match it against each candidate's region fields,
        # else geocode the qualifier itself and pick the nearest candidate to it.
        qual = " ".join(parts[1:]).lower()
        def _fields(c):
            return [str(c.get(k, "")).lower() for k in ("name", "admin1", "admin2", "admin3", "admin4", "country")]
        matches = [c for c in results if any(qual in f or f and f in qual for f in _fields(c) if f)]
        if matches:
            r = matches[0]
        else:
            try:
                anchors = _geocode(parts[1], count=1)
            except Exception:
                anchors = []
            if anchors:
                a = anchors[0]
                r = min(results, key=lambda c: (c["latitude"] - a["latitude"]) ** 2 + (c["longitude"] - a["longitude"]) ** 2)
    name = ", ".join(str(p) for p in [r.get("name"), r.get("admin1"), r.get("country")] if p)
    cfg = _load_config()
    cfg["location"] = {"name": name, "lat": r["latitude"], "lon": r["longitude"]}
    _save_config(cfg)
    _weather_cache["data"] = None
    w = _get_weather()
    extra = f" Currently {w['temp']:.1f}C outside." if w and w.get("temp") is not None else ""
    return f"Location set to {name} ({r['latitude']:.3f}, {r['longitude']:.3f}).{extra}"


@mcp.tool()
def izone_sleep(minutes: int) -> str:
    """Set the sleep timer: the AC turns itself off after the given minutes.

    Args:
        minutes: Minutes until auto-off (0 to clear the timer)
    """
    if minutes < 0 or minutes > 720:
        return "Error: minutes must be 0-720"
    result = _send_command({"SysSleepTimer": minutes})
    if minutes == 0:
        return f"Sleep timer cleared ({result})"
    return f"Sleep timer set: AC will turn off in {minutes} minutes ({result})"


@mcp.tool()
def izone_history(hours: float = 24, zone: str = "") -> str:
    """Summarize logged temperature history: per-zone min/avg/max, trend direction, and a
    sparkline. History accumulates automatically every time the system is polled.

    Args:
        hours: Look-back window in hours (default 24)
        zone: Optional zone name (or part of one) to focus on; empty for all zones + system
    """
    hours = max(0.25, min(hours, 24 * 365))
    recs = _read_history(hours)
    if len(recs) < 2:
        return (f"Not enough history in the last {hours:g}h ({len(recs)} snapshots). "
                "History accumulates automatically each time izone_status, izone_insights, or "
                "izone_recommend runs — check back after the system has been polled a few times.")

    span_h = (recs[-1]["ts"] - recs[0]["ts"]) / 3600
    lines = [f"{len(recs)} snapshots over {span_h:.1f}h:"]

    def _series_summary(label: str, values: list, setpoints: list | None = None):
        vals = [(v or 0) / 100 for v in values if isinstance(v, (int, float))]
        if not vals:
            return
        trend = vals[-1] - vals[0]
        arrow = "→" if abs(trend) < 0.3 else ("↑" if trend > 0 else "↓")
        line = (f"  {label:<14} now {vals[-1]:.1f}C, range {min(vals):.1f}-{max(vals):.1f}C, "
                f"avg {sum(vals)/len(vals):.1f}C {arrow}{abs(trend):.1f}  {_sparkline(vals)}")
        if setpoints:
            sps = [(sp or 0) / 100 for sp in setpoints if isinstance(sp, (int, float))]
            if sps:
                line += f"  (set {sps[-1]:.1f}C)"
        lines.append(line)

    zone_filter = zone.strip().lower()
    if not zone_filter:
        _series_summary("Return air", [r.get("temp") for r in recs])
        outs = [r["out"] for r in recs if isinstance(r.get("out"), (int, float))]
        if len(outs) >= 2:
            trend = outs[-1] - outs[0]
            arrow = "→" if abs(trend) < 0.3 else ("↑" if trend > 0 else "↓")
            lines.append(f"  {'Outdoor':<14} now {outs[-1]:.1f}C, range {min(outs):.1f}-{max(outs):.1f}C "
                         f"{arrow}{abs(trend):.1f}  {_sparkline(outs)}")

    zone_names = []
    for r in recs:
        for z in r.get("zones", []):
            if z.get("n") and z["n"] not in zone_names:
                zone_names.append(z["n"])
    matched_any = False
    for name in zone_names:
        if zone_filter and zone_filter not in name.lower():
            continue
        matched_any = True
        temps = []
        sets = []
        for r in recs:
            for z in r.get("zones", []):
                if z.get("n") == name:
                    temps.append(z.get("t"))
                    sets.append(z.get("s"))
        _series_summary(name, temps, sets)
    if zone_filter and not matched_any:
        known = ", ".join(zone_names) if zone_names else "(none logged yet)"
        return f"No zone matching {zone!r} in the logged history. Zones seen: {known}"

    on_count = sum(1 for r in recs if r.get("on"))
    lines.append(f"  System ON in {on_count}/{len(recs)} snapshots ({on_count / len(recs) * 100:.0f}%)")
    return "\n".join(lines)


def _zone_open(z: dict) -> bool:
    return z.get("Mode") != ZONE_MODES["close"]


def _zone_is_constant(z: dict) -> bool:
    """Constant zones are pressure relief — they must never be closed."""
    return z.get("ZoneType") == 2 or z.get("Mode") == ZONE_MODES["constant"]


def _zone_temp_controlled(z: dict) -> bool:
    """ZoneType 1 zones are open/close only — they can't hold a setpoint in auto mode."""
    return z.get("ZoneType") != 1


def _temp_plausible(c: float) -> bool:
    """Reject readings from dead/faulty sensors (0.0C defaults, wild values)."""
    return 5.0 < c < 45.0


VENT_MIN_OUTDOOR = 14.0


def _fresh_air_configured() -> bool:
    """Vent mode only moves outdoor air in if the system has a fresh-air intake; most
    base ducted systems just recirculate, so free-cooling via vent is opt-in."""
    return bool(_load_config().get("fresh_air"))


def _is_night() -> bool:
    h = time.localtime().tm_hour
    return h >= 21 or h < 7


@mcp.tool()
def izone_insights() -> str:
    """Analyze the system's current health and efficiency: zones struggling to reach setpoint,
    the system working against itself, free-cooling opportunities, air quality and humidity
    warnings, and energy-saving suggestions. Combines live readings, outdoor weather, and
    logged history."""
    s, zones = _full_state()
    w = _get_weather()
    findings = []
    on = bool(s.get("SysOn"))
    mode = _mode_label(s.get("SysMode"))
    setpoint = (s.get("Setpoint") or 0) / 100
    return_air = (s.get("Temp") or 0) / 100

    open_zones = [(i, z) for i, z in enumerate(zones) if _zone_open(z)]

    # Zones struggling to reach setpoint (skip zones whose sensor reading is implausible)
    for _, z in open_zones:
        zt = (z.get("Temp") or 0) / 100
        zs = (z.get("Setpoint") or 0) / 100
        if not _temp_plausible(zt):
            findings.append(f"'{z['Name']}' is reporting {zt:.1f}C — that reads like a faulty or "
                            f"disconnected sensor; ignoring it for comfort decisions.")
            continue
        gap = zt - zs
        if on and abs(gap) >= 1.5:
            direction = "above" if gap > 0 else "below"
            findings.append(f"'{z['Name']}' is {abs(gap):.1f}C {direction} its {zs:.1f}C setpoint "
                            f"(now {zt:.1f}C) — check its airflow ({z.get('MaxAir', '?')}% max) or door/window.")

    # System fighting itself
    if on and mode == "cool" and return_air <= setpoint - 1.0:
        findings.append(f"Cooling but return air ({return_air:.1f}C) is already {setpoint - return_air:.1f}C "
                        f"below the {setpoint:.1f}C setpoint — raise the setpoint or switch off.")
    if on and mode == "heat" and return_air >= setpoint + 1.0:
        findings.append(f"Heating but return air ({return_air:.1f}C) is already above the "
                        f"{setpoint:.1f}C setpoint — lower the setpoint or switch off.")

    # Free cooling / outdoor-aware
    if w and w.get("temp") is not None:
        out = w["temp"]
        if on and mode == "cool" and out < return_air - 2 and out < setpoint + 1:
            if _fresh_air_configured() and out >= VENT_MIN_OUTDOOR:
                findings.append(f"It's only {out:.1f}C outside vs {return_air:.1f}C inside — vent mode "
                                f"(fresh-air intake) would cool for near-zero energy.")
            else:
                findings.append(f"It's only {out:.1f}C outside vs {return_air:.1f}C inside — opening "
                                f"windows would cool for free instead of running the compressor.")
        if not on and w.get("forecast_max") is not None and w["forecast_max"] >= 32 and return_air < 26:
            findings.append(f"Forecast peaks at {w['forecast_max']:.0f}C in the next 12h — pre-cooling "
                            f"now while it's mild is cheaper than fighting the peak later.")
        if not on and w.get("forecast_min") is not None and w["forecast_min"] <= 8 and return_air > 18:
            findings.append(f"Forecast drops to {w['forecast_min']:.0f}C in the next 12h — consider "
                            f"pre-heating before the cold arrives.")
    else:
        findings.append("(No outdoor weather — set a home location once with izone_set_location "
                        "to unlock free-cooling and pre-conditioning insights.)")

    # Air quality / humidity
    if s.get("IneCO2") and s["IneCO2"] > 1000:
        findings.append(f"eCO2 is {s['IneCO2']} ppm (fresh air is ~400) — the air is stale; "
                        f"run vent mode or open windows.")
    if s.get("InTVOC") and s["InTVOC"] > 500:
        findings.append(f"TVOC is {s['InTVOC']} ppb — elevated indoor pollutants; ventilate.")
    if s.get("InRh") and s["InRh"] > 65 and mode != "dry":
        findings.append(f"Humidity is {s['InRh']}% — dry mode would improve comfort at the same temp.")

    # Energy
    if on and len(open_zones) == len(zones) and len(zones) > 3:
        findings.append(f"All {len(zones)} zones are open — closing unoccupied rooms concentrates "
                        f"airflow and cuts runtime.")
    if on and mode == "cool" and setpoint < 22:
        findings.append(f"Cooling setpoint is {setpoint:.1f}C — every degree below 23-24C adds "
                        f"roughly 10% to running cost.")
    if on and mode == "heat" and setpoint > 22:
        findings.append(f"Heating setpoint is {setpoint:.1f}C — every degree above 20-21C adds "
                        f"roughly 10% to running cost.")

    # History-informed: zone that never reaches setpoint
    recs = _read_history(24)
    if len(recs) >= 6:
        for _, z in open_zones:
            name = z.get("Name", "")
            gaps = []
            for r in recs:
                for zr in r.get("zones", []):
                    if zr.get("n") == name and r.get("on") and zr.get("m") != ZONE_MODES["close"]:
                        if isinstance(zr.get("t"), (int, float)) and isinstance(zr.get("s"), (int, float)):
                            gaps.append((zr["t"] - zr["s"]) / 100)
            if len(gaps) >= 6 and min(abs(g) for g in gaps) >= 1.0:
                side = "above" if gaps[-1] > 0 else "below"
                findings.append(f"'{name}' has stayed at least 1C {side} setpoint across the last 24h "
                                f"of running — it may need a higher max-airflow or a duct/balance check.")

    header = (f"System {'ON' if on else 'OFF'}, mode {mode}, set {setpoint:.1f}C, "
              f"return air {return_air:.1f}C"
              + (f", outdoor {w['temp']:.1f}C" if w and w.get("temp") is not None else ""))
    if not findings:
        return header + "\n\nAll good: no comfort, efficiency, or air-quality issues detected."
    return header + "\n\n" + "\n".join(f"- {f}" for f in findings)


@mcp.tool()
def izone_recommend(target: float = 0, occupied_zones: str = "", apply: bool = False) -> str:
    """Recommend (and optionally apply) the smartest AC plan right now, weighing indoor readings,
    outdoor weather, and the 12h forecast. Prefer this over manually composing commands for
    open-ended requests like "make it comfortable" or "it's hot in here".

    Args:
        target: Desired indoor temperature in C (0 = pick automatically: 23 in warm weather, 21 in cold)
        occupied_zones: Comma-separated zone names or indexes that matter right now
                        (e.g. "study,lounge" or "0,2"); empty = currently open zones, or all if none open
        apply: If true, save defaults and execute the plan; if false, just report it
    """
    s, zones = _full_state()
    w = _get_weather()
    return_air = (s.get("Temp") or 0) / 100
    out = w.get("temp") if w else None

    # Resolve which zones matter
    wanted = []
    if occupied_zones.strip():
        for tok in occupied_zones.split(","):
            tok = tok.strip().lower()
            if not tok:
                continue
            if tok.isdigit() and int(tok) < len(zones):
                wanted.append(int(tok))
            else:
                for i, z in enumerate(zones):
                    if tok in z.get("Name", "").lower() and i not in wanted:
                        wanted.append(i)
        if not wanted:
            names = ", ".join(z.get("Name", str(i)) for i, z in enumerate(zones))
            return f"Error: no zones matched {occupied_zones!r}. Zones: {names}"
    else:
        wanted = [i for i, z in enumerate(zones) if _zone_open(z)] or list(range(len(zones)))

    occ_temps = [(zones[i].get("Temp") or 0) / 100 for i in wanted]
    occ_temps = [t for t in occ_temps if _temp_plausible(t)]  # drop faulty-sensor readings
    if occ_temps:
        indoor = sum(occ_temps) / len(occ_temps)
    elif _temp_plausible(return_air):
        indoor = return_air
    else:
        return (f"Error: no plausible temperature readings (zones and return air all look like "
                f"faulty sensors, return air {return_air:.1f}C) — not making changes. "
                f"Check izone_status and the sensors.")

    # Pick target
    if target <= 0:
        if out is not None:
            target = 23.0 if out >= 18 else 21.0
        else:
            target = 23.0 if indoor >= 22 else 21.0
    if target < 15 or target > 30:
        return "Error: target must be between 15.0 and 30.0"

    # Decide the plan
    reasons = []
    band = 0.8
    # Vent-based free cooling is only real with a fresh-air intake (most ducted systems
    # recirculate), and never with frigid outdoor air that would badly overshoot.
    vent_viable = (out is not None and out <= indoor - 2 and out <= target + 1
                   and out >= VENT_MIN_OUTDOOR)
    if indoor > target + band:
        if vent_viable and _fresh_air_configured():
            plan_mode = "vent"
            plan_fan = "medium" if _is_night() else "high"
            reasons.append(f"indoor {indoor:.1f}C is warm but it's only {out:.1f}C outside — "
                           f"vent mode (fresh-air intake) gives near-free cooling")
            if _is_night():
                reasons.append("fan capped at medium for night-time noise")
        else:
            plan_mode, plan_fan = "cool", "auto"
            reasons.append(f"indoor {indoor:.1f}C is {indoor - target:.1f}C above the {target:.1f}C target")
            if vent_viable and not _fresh_air_configured():
                reasons.append(f"it's only {out:.1f}C outside — opening windows would do this for free; "
                               f"if the system has a fresh-air intake, set \"fresh_air\": true in "
                               f"~/.config/izone/config.json and vent mode can be used automatically")
            if w and w.get("forecast_max") is not None and w["forecast_max"] >= indoor + 2:
                reasons.append(f"forecast peaks at {w['forecast_max']:.0f}C, so cooling now also pre-empts the peak")
    elif indoor < target - band:
        plan_mode, plan_fan = "heat", "auto"
        reasons.append(f"indoor {indoor:.1f}C is {target - indoor:.1f}C below the {target:.1f}C target")
    else:
        lines = [f"Indoor is {indoor:.1f}C in the zones that matter — already within "
                 f"{band:.1f}C of the {target:.1f}C target."]
        if bool(s.get("SysOn")):
            lines.append("Recommendation: turn the system OFF and coast." +
                         ("" if apply else " (run with apply=true to do it)"))
            if apply:
                _send_command({"SysOn": 0})
                lines.append("Done: system turned OFF.")
        else:
            lines.append("Recommendation: leave the system off.")
        if w and w.get("temp") is not None:
            lines.append(f"Outdoor: {w['temp']:.1f}C, next 12h {w['forecast_min']:.0f}-{w['forecast_max']:.0f}C.")
        return "\n".join(lines)

    zone_plan = []
    for i, z in enumerate(zones):
        name = z.get("Name", str(i))
        if i in wanted:
            if _zone_temp_controlled(z):
                zone_plan.append((i, name, "auto", target))
            else:
                zone_plan.append((i, name, "open", None))  # open/close-only zone: no setpoint
        elif _zone_is_constant(z):
            zone_plan.append((i, name, "keep", None))  # constant zone: never close
        else:
            zone_plan.append((i, name, "close", None))

    lines = [f"Plan: {plan_mode.upper()} to {target:.1f}C, fan {plan_fan}"]
    lines.append("Because: " + "; ".join(reasons) + ".")
    for i, name, zmode, ztemp in zone_plan:
        if zmode == "keep":
            lines.append(f"  Zone {i} {name}: left as-is (constant zone — must stay open)")
        else:
            lines.append(f"  Zone {i} {name}: {zmode}" + (f" at {ztemp:.1f}C" if ztemp else ""))
    if w and w.get("temp") is not None:
        lines.append(f"Outdoor: {w['temp']:.1f}C, next 12h {w['forecast_min']:.0f}-{w['forecast_max']:.0f}C.")

    if not apply:
        lines.append("(Run with apply=true to execute — defaults will be saved first.)")
        return "\n".join(lines)

    # Execute
    izone_defaults_save()
    lines.append("Defaults saved.")
    _send_command({"SysOn": 1})
    time.sleep(0.3)
    _send_command({"SysMode": MODES[plan_mode]})
    time.sleep(0.3)
    _send_command({"SysFan": FAN_SPEEDS[plan_fan]})
    time.sleep(0.3)
    setpoint = round(int(target * 100) / 50) * 50
    _send_command({"SysSetpoint": setpoint})
    for i, name, zmode, ztemp in zone_plan:
        if zmode == "keep":
            continue
        time.sleep(0.2)
        _send_command({"ZoneMode": {"Index": i, "Mode": ZONE_MODES[zmode]}})
        if zmode == "auto" and ztemp:
            _send_command({"ZoneSetpoint": {"Index": i, "Setpoint": setpoint}})
    lines.append("Done: plan applied.")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
