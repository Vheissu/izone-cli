# Use Cases

Creative and practical ways to use the iZone CLI and MCP server.

## Terminal One-Liners

### Quick temperature check across the house

```bash
izone zones
```

### Cool down the hottest room

```bash
# Find the hottest zone and cool it
hottest=$(izone json | python3 -c "
import json, sys
data = json.load(sys.stdin)
z = max(data['zones'], key=lambda x: x['Temp'])
print(z['Index'])
")
izone on && izone zone $hottest --mode auto --temp 22
```

### Morning routine — cool the kitchen and study before you start work

```bash
izone on && izone mode cool && izone fan auto && izone temp 23 \
  && izone zone 0 --mode auto && izone zone 5 --mode auto
```

### Shut everything down at bedtime

```bash
izone sleep 60  # Auto-off in 1 hour
```

### Check air quality before opening windows

```bash
izone airquality
```

## Shell Aliases

Add these to your `~/.zshrc` or `~/.bashrc`:

```bash
alias ac="izone status"
alias acon="izone on"
alias acoff="izone off"
alias cool="izone on && izone mode cool && izone fan auto"
alias temps="izone zones"
alias aq="izone airquality"
```

## Scripting with JSON Output

### Log temperatures to CSV

```bash
#!/bin/bash
# log-temps.sh — append current zone temps to a CSV
timestamp=$(date +"%Y-%m-%d %H:%M")
izone json | python3 -c "
import json, sys
data = json.load(sys.stdin)
zones = data['zones']
temps = ','.join(f'{z[\"Temp\"]/100:.1f}' for z in zones)
names = ','.join(z['Name'] for z in zones)
print(f'$timestamp,{temps}')
" >> ~/temps.csv
```

Run it every 15 minutes with cron:

```
*/15 * * * * /path/to/log-temps.sh
```

### Alert when a room gets too hot

```bash
#!/bin/bash
# hot-alert.sh
threshold=28
izone json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for z in data['zones']:
    temp = z['Temp'] / 100
    if temp > $threshold:
        print(f\"WARNING: {z['Name']} is {temp}C (threshold: $threshold C)\")
" | while read -r line; do
    osascript -e "display notification \"$line\" with title \"iZone Alert\""
done
```

### Auto-cool based on temperature

```bash
#!/bin/bash
# auto-cool.sh — turn on AC if any zone exceeds threshold
threshold=26
needs_cooling=$(izone json | python3 -c "
import json, sys
data = json.load(sys.stdin)
hot = [z for z in data['zones'] if z['Temp'] / 100 > $threshold]
if hot:
    print(','.join(str(z['Index']) for z in hot))
")

if [ -n "$needs_cooling" ]; then
    izone on
    izone mode cool
    izone temp 23
    for idx in $(echo $needs_cooling | tr ',' ' '); do
        izone zone $idx --mode auto
    done
fi
```

## Schedule / Scene Workflows

### Set up a "Movie Night" scene

```bash
# Configure schedule slot 6 for movie night
izone schedule 6 --name "Movie Night"
izone schedule 6 --mode cool --fan low
# Then run it whenever you want
izone run 6
```

### Weekday morning pre-cool

```bash
# Cool the house before you wake up on weekdays
izone schedule 1 --name "Morning"
izone schedule 1 --mode cool --fan auto
izone schedule 1 --start 06:00 --stop 08:30
izone schedule 1 --days weekdays
izone schedule 1 --enable yes
```

### Weekend sleep schedule

```bash
izone schedule 2 --name "Weekend Night"
izone schedule 2 --mode cool --fan low
izone schedule 2 --start 22:00 --stop 07:00
izone schedule 2 --days weekends
izone schedule 2 --enable yes
```

## MCP / AI Assistant Prompts

With the MCP server configured, you can control your AC through natural conversation in Claude Code, Codex, or any MCP-compatible client.

### Status queries

- "What's the temperature in my house?"
- "Which room is the hottest right now?"
- "Is the AC on?"
- "What's the air quality like?"
- "Show me all my schedules"

### Simple commands

- "Turn on the AC"
- "Set the fan to low"
- "Cool the study to 22 degrees"
- "Close all zones except the master bedroom"
- "Set a 30 minute sleep timer"

### Smart multi-step requests

- "It's bedtime — cool just the master bedroom to 23, close everything else, set fan to low, and set a 2 hour sleep timer"
- "I'm working from home today — cool the study and kitchen to 23"
- "The house is hot — turn on the AC, find the hottest rooms, and cool them down"
- "Set up a weekday morning schedule that pre-cools the kitchen and study from 6am to 8:30am"

### Energy-conscious requests

- "What's the most efficient way to cool down the upstairs?"
- "Only cool the rooms that are above 25 degrees"
- "Turn off zones that are already at their setpoint"

## Integration Ideas

### Home Dashboard

Use `izone json` to feed data into a dashboard tool like Grafana, or build a simple web page that polls the CLI.

### macOS Shortcuts

Create a Shortcut that runs `izone on && izone mode cool && izone temp 22` via the terminal, then trigger it from your iPhone/Apple Watch.

### Stream Deck

Map Stream Deck buttons to common commands:

- Button 1: `izone on`
- Button 2: `izone off`
- Button 3: `izone run 0` (favourite scene)
- Button 4: `izone run 2` (night mode)

### Hammerspoon (macOS automation)

```lua
-- Cool the study when you connect to your work WiFi
hs.wifi.watcher.new(function()
    if hs.wifi.currentNetwork() == "HomeNetwork" then
        hs.execute("izone on && izone zone 5 --mode auto --temp 23")
    end
end):start()
```
