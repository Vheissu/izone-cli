# iZone Protocol Reference

Complete reference for the iZone V2 local network API.

## Network Ports

| Port | Protocol | Purpose |
|---|---|---|
| 12107 | UDP | Bridge discovery (broadcast) |
| 7005 | UDP | State change notifications (listen) |
| 80 | TCP/HTTP | All API queries and commands |

## Discovery Protocol

Send the 4-byte ASCII string `IASD` as a UDP broadcast to `255.255.255.255:12107`.

```bash
echo -n "IASD" | socat - UDP-DATAGRAM:255.255.255.255:12107,broadcast
```

Or with Python:

```python
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.settimeout(3)
sock.sendto(b"IASD", ("255.255.255.255", 12107))
data, addr = sock.recvfrom(1024)
print(data.decode())
```

### Response Format

```
ASPort_12107,Mac_000000000,IP_192.168.1.100,iZoneV2,iLight,iDrate,iPower,Split
```

| Field | Description |
|---|---|
| `ASPort_12107` | Port identifier |
| `Mac_XXXXXXXXX` | Bridge MAC/device ID |
| `IP_x.x.x.x` | Bridge IP on LAN |
| `iZoneV2` | V2 API supported |
| `iLight` | Lighting support |
| `iDrate` | Irrigation support |
| `iPower` | Power monitoring |
| `Split` | Split-system AC support |

Unsupported features show as `X` or are omitted.

### State Change Notifications (UDP 7005)

The bridge broadcasts these messages when state changes:

| Message | Meaning |
|---|---|
| `iZoneChanged_System` | System config changed |
| `iZoneChanged_Zones` | Zone status changed |
| `iZoneChanged_Schedules` | Schedule modified |

## Query API

**Endpoint:** `POST http://<bridge_ip>/iZoneRequestV2`

### Request Body

```json
{
  "iZoneV2Request": {
    "Type": 1,
    "No": 0,
    "No1": 0
  }
}
```

### Type Values

| Type | Returns | `No` parameter |
|---|---|---|
| 1 | System settings | Ignored |
| 2 | Zone status | Zone index (0-based) |
| 3 | Schedule data | Schedule index |

### System Response (Type 1) — Key Fields

```json
{
  "AirStreamDeviceUId": "000000000",
  "DeviceType": "ASH",
  "SystemV2": {
    "SysOn": 0,
    "SysMode": 1,
    "SysFan": 3,
    "SleepTimer": 0,
    "Supply": 2357,
    "Setpoint": 2400,
    "Temp": 2409,
    "NoOfZones": 7,
    "InRh": 55,
    "InTVOC": 1279,
    "IneCO2": 678
  }
}
```

| Field | Description | Values |
|---|---|---|
| `SysOn` | Power state | 0=off, 1=on |
| `SysMode` | Operating mode | 1=cool, 2=heat, 3=vent, 4=dry, 5=auto |
| `SysFan` | Fan speed | 1=low, 2=medium, 3=high, 4=auto, 5=top |
| `Setpoint` | Target temp | Value × 100 (2400 = 24.0°C) |
| `Temp` | Return air temp | Value × 100 |
| `Supply` | Supply air temp | Value × 100 |
| `NoOfZones` | Zone count | Integer |
| `InRh` | Indoor humidity | Percentage |
| `InTVOC` | Total VOC | ppb |
| `IneCO2` | Estimated CO2 | ppm |

### Zone Response (Type 2)

```json
{
  "AirStreamDeviceUId": "000000000",
  "DeviceType": "ASH",
  "ZonesV2": {
    "Index": 5,
    "Name": "Bedroom",
    "ZoneType": 3,
    "Mode": 3,
    "Setpoint": 2400,
    "Temp": 2514,
    "MaxAir": 90,
    "MinAir": 0
  }
}
```

| Field | Description | Values |
|---|---|---|
| `Index` | Zone number | 0-based |
| `Name` | Zone name | Up to 15 chars |
| `ZoneType` | Zone capability | 1=open/close, 2=constant, 3=auto (temp control) |
| `Mode` | Current mode | 1=open, 2=close, 3=auto, 4=override, 5=constant |
| `Setpoint` | Target temp | Value × 100 |
| `Temp` | Current temp | Value × 100 |
| `MaxAir` | Max airflow | 0-100 (%) |
| `MinAir` | Min airflow | 0-100 (%) |

## Command API

**Endpoint:** `POST http://<bridge_ip>/iZoneCommandV2`

**Response:** Plain text `OK` on success.

### System Commands

#### Power

```json
{"SysOn": 1}
{"SysOn": 0}
```

#### Mode

```json
{"SysMode": "cool"}
```

| Value | Mode |
|---|---|
| `"cool"` / `1` | Cool |
| `"heat"` / `2` | Heat |
| `"vent"` / `3` | Vent (fan only) |
| `"dry"` / `4` | Dry |
| `"auto"` / `5` | Auto |

#### Fan Speed

```json
{"SysFan": "medium"}
```

| Value | Speed |
|---|---|
| `"low"` / `1` | Low |
| `"medium"` / `2` | Medium |
| `"high"` / `3` | High |
| `"auto"` / `4` | Auto |
| `5` | Top |

#### System Temperature

```json
{"SysSetpoint": 2200}
```

Value is temperature × 100. Range: 1500–3000 (15.0°C–30.0°C).

#### Sleep Timer

```json
{"SysSleepTimer": 60}
```

Value in minutes. `0` disables the timer.

### Zone Commands

#### Zone Mode

```json
{"ZoneMode": {"Index": 0, "Mode": 3}}
```

| Mode | Meaning |
|---|---|
| 1 | Open |
| 2 | Close |
| 3 | Auto (temperature control) |
| 4 | Override |
| 5 | Constant |

#### Zone Temperature

```json
{"ZoneSetpoint": {"Index": 0, "Setpoint": 2200}}
```

Range: 1500–3000, in steps of 50 (0.5°C increments).

#### Zone Max Airflow

```json
{"ZoneMaxAir": {"Index": 0, "MaxAir": 80}}
```

Range: 0–100, in steps of 5 (percentage).

#### Zone Min Airflow

```json
{"ZoneMinAir": {"Index": 0, "MinAir": 20}}
```

Range: 0–100, in steps of 5 (percentage).

#### Zone Name

```json
{"ZoneName": {"Index": 0, "Name": "Bedroom"}}
```

Maximum 15 characters.

### Schedule Commands

9 schedule slots are available (index 0–8). Schedules store a full AC configuration (mode, fan, per-zone settings) that can be triggered on a timer or run on demand as a scene/favourite.

#### Schedule Name

```json
{"SchedName": {"Index": 0, "Name": "Night Mode"}}
```

Maximum 15 characters.

#### Schedule AC Mode

```json
{"SchedAcMode": {"Index": 0, "Mode": 1}}
```

Uses the same mode values as system mode (1=cool, 2=heat, etc.).

#### Schedule Fan Speed

```json
{"SchedAcFan": {"Index": 0, "Fan": "medium"}}
```

Accepts string values: `"low"`, `"medium"`, `"high"`, `"auto"`, `"top"`.

#### Schedule Timing and Days

```json
{"SchedSettings": {"Index": 0, "StartH": 7, "StartM": 30, "StopH": 22, "StopM": 0, "DaysEnabled": {"M": 1, "Tu": 1, "W": 1, "Th": 1, "F": 1, "Sa": 0, "Su": 0}}}
```

- `StartH`/`StopH`: 0–23, or 31 to disable
- `StartM`/`StopM`: 0–59, or 63 to disable
- `DaysEnabled`: 0 or 1 for each day
- `DaysEnabled` is optional — omit to leave days unchanged

#### Schedule Zone Settings

```json
{"SchedZones": {"Index": 0, "Zones": [{"Mode": 3, "Setpoint": 2400}, ...]}}
```

Array length must match the actual number of zones on the system (not the 14-slot maximum in the spec).

#### Enable/Disable Schedule

```json
{"SchedEnable": {"Index": 0, "Enabled": 1}}
```

Values: `0` = disabled, `1` = enabled.

#### Run Schedule Immediately (Favourite)

```json
{"FavouriteSet": 1}
```

Value is **1-based** (schedule index + 1). Activates the schedule as a scene without enabling its timer.

## Response Parsing Notes

- Successful query responses may be suffixed with `{OK}` — strip this before JSON parsing.
- Some responses contain non-UTF-8 bytes (e.g., the `LockCode` field) — decode with `errors="replace"`.
- Command responses return plain text `OK`.
- Use a 5-second HTTP timeout.
- Wait 0.3 seconds between rapid sequential requests to the same bridge.
- Wait 5 seconds after a command before polling for updated state.

## External Resources

- [iZone Developer Portal](https://developer.izone.com.au/)
- [pizone Python Library](https://github.com/Swamp-Ig/pizone)
- [Home Assistant iZone Integration](https://www.home-assistant.io/integrations/izone/)
- [iZone Ethernet Interface Spec (PDF in pizone repo)](https://github.com/Swamp-Ig/pizone)
