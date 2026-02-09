#!/bin/bash
# Govee BLE - Add Sensor
# Adds a sensor to config.json interactively or via CLI arguments

set -e

CONFIG_FILE="/data/govee-ble/config.json"
DISCOVERED_FILE="/data/govee-ble/discovered_sensors.json"

# --- Help flag ---
case "${1:-}" in
    -h|--help)
        echo "Usage: $0 [MAC_ADDRESS] [CUSTOM_NAME] [TEMP_TYPE]"
        echo
        echo "With no arguments, shows an interactive menu."
        echo
        echo "Examples:"
        echo "  $0"
        echo "  $0 A4:C1:38:XX:XX:XX"
        echo "  $0 A4:C1:38:XX:XX:XX Freezer 6"
        echo "  $0 D1:30:38:36:24:0C \"Living Room\" 3"
        echo
        echo "Temperature Types:"
        echo "  0=Battery, 1=Fridge, 2=Generic, 3=Room,"
        echo "  4=Outdoor, 5=Water heater, 6=Freezer"
        exit 0
        ;;
esac

# --- Check config file ---
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found: $CONFIG_FILE"
    echo "Is the Govee BLE service installed?"
    exit 1
fi

# --- Interactive menu (no arguments) ---
if [ -z "$1" ]; then
    show_menu() {
        echo
        echo "========================================"
        echo "  Govee BLE - Add Sensor"
        echo "========================================"
        echo

        # Read discovered sensors
        SENSOR_COUNT=0
        if [ -f "$DISCOVERED_FILE" ]; then
            # Use Python to parse JSON into shell-friendly format
            SENSOR_LIST=$(python3 << 'LIST_EOF'
import json, sys
try:
    with open("/data/govee-ble/discovered_sensors.json", "r") as f:
        discovered = json.load(f)
    if discovered:
        for mac, name in discovered.items():
            print(f"{mac}\t{name}")
except Exception:
    pass
LIST_EOF
            )
            if [ -n "$SENSOR_LIST" ]; then
                echo "Discovered sensors not yet added:"
                INDEX=1
                OLDIFS="$IFS"
                IFS="
"
                for LINE in $SENSOR_LIST; do
                    SMAC=$(echo "$LINE" | cut -f1)
                    SNAME=$(echo "$LINE" | cut -f2)
                    printf "  %d) %s (%s)\n" "$INDEX" "$SMAC" "$SNAME"
                    INDEX=$((INDEX + 1))
                done
                IFS="$OLDIFS"
                SENSOR_COUNT=$((INDEX - 1))
                echo
            fi
        fi

        if [ "$SENSOR_COUNT" -eq 0 ]; then
            echo "No discovered sensors."
            echo
        fi

        echo "  M) Enter MAC address manually"
        echo "  S) Scan for new sensors"
        echo "  C) Clear discovered sensors list"
        echo "  Q) Quit"
        echo
        printf "Select option: "
        read CHOICE

        case "$CHOICE" in
            [qQ])
                exit 0
                ;;
            [cC])
                if [ -f "$DISCOVERED_FILE" ]; then
                    rm "$DISCOVERED_FILE"
                    echo "Discovered sensors list cleared."
                else
                    echo "No discovered sensors file to clear."
                fi
                exit 0
                ;;
            [sS])
                printf "Scan duration in seconds (default 60): "
                read SCAN_DURATION
                SCAN_DURATION="${SCAN_DURATION:-60}"
                echo "Scanning for $SCAN_DURATION seconds..."
                echo
                python3 << SCAN_EOF
import sys, json, subprocess, time

sys.path.insert(0, '/data/govee-ble/src')
from btmon_reader import AdvertisementAssembler

# Load already-configured MACs
configured = set()
try:
    with open("$CONFIG_FILE", "r") as f:
        config = json.load(f)
    for s in config.get("sensors", []):
        if s.get("mac"):
            configured.add(s["mac"].upper())
except Exception:
    pass

# Load already-discovered sensors
discovered = {}
try:
    with open("$DISCOVERED_FILE", "r") as f:
        discovered = json.load(f)
except Exception:
    pass

# Scan with btmon
assembler = AdvertisementAssembler()
found = {}
duration = int("$SCAN_DURATION")

proc = subprocess.Popen(
    ["btmon", "-T"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    bufsize=1,
    universal_newlines=True,
)

start = time.time()
try:
    while time.time() - start < duration:
        line = proc.stdout.readline()
        if not line:
            break
        adv = assembler.process_line(line.rstrip())
        if adv and adv.get("mac") and adv.get("name"):
            mac = adv["mac"].upper()
            if mac not in configured and mac not in found and mac not in discovered:
                found[mac] = adv["name"]
                print(f"  Found: {mac} ({adv['name']})")
finally:
    proc.terminate()
    proc.wait()

# Merge into discovered file
discovered.update(found)
with open("$DISCOVERED_FILE", "w") as f:
    json.dump(discovered, f, indent=2)

print(f"\nFound {len(found)} new sensor(s), {len(discovered)} total discovered.")
SCAN_EOF
                # Redisplay menu after scan
                show_menu
                return
                ;;
            [mM])
                printf "MAC address: "
                read MAC
                if [ -z "$MAC" ]; then
                    echo "Error: MAC address required"
                    exit 1
                fi
                # Fall through to prompts below
                CUSTOM_NAME=""
                TEMP_TYPE=""
                ;;
            *)
                # Check if it's a number selecting a discovered sensor
                if [ -n "$SENSOR_LIST" ] && echo "$CHOICE" | grep -qE '^[0-9]+$'; then
                    SELECTED_LINE=$(echo "$SENSOR_LIST" | sed -n "${CHOICE}p")
                    if [ -z "$SELECTED_LINE" ]; then
                        echo "Invalid selection."
                        exit 1
                    fi
                    MAC=$(echo "$SELECTED_LINE" | cut -f1)
                    DEVICE_NAME=$(echo "$SELECTED_LINE" | cut -f2)

                    printf "Custom name (default: %s): " "$DEVICE_NAME"
                    read CUSTOM_NAME
                    CUSTOM_NAME="${CUSTOM_NAME:-$DEVICE_NAME}"

                    echo "Temperature Types:"
                    echo "  0=Battery, 1=Fridge, 2=Generic, 3=Room,"
                    echo "  4=Outdoor, 5=Water heater, 6=Freezer"
                    printf "Temperature type (0-6, default 2=Generic): "
                    read TEMP_TYPE
                    TEMP_TYPE="${TEMP_TYPE:-2}"
                else
                    echo "Invalid selection."
                    exit 1
                fi
                ;;
        esac
    }

    show_menu

# --- CLI arguments path ---
else
    MAC="$1"
    CUSTOM_NAME="${2:-}"
    TEMP_TYPE="${3:-}"
fi

# --- Shared path: validate MAC, prompt, save ---

# Validate MAC format
if ! echo "$MAC" | grep -qE '^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$'; then
    echo "Error: Invalid MAC address format"
    echo "Expected format: AA:BB:CC:DD:EE:FF"
    exit 1
fi

# Convert to uppercase
MAC=$(echo "$MAC" | tr '[:lower:]' '[:upper:]')

# Summary
echo
echo "========================================"
echo "  Adding Sensor to Config"
echo "========================================"
echo
echo "MAC Address:  $MAC"
[ -n "$CUSTOM_NAME" ] && echo "Custom Name:  $CUSTOM_NAME"
[ -n "$TEMP_TYPE" ] && echo "Temp Type:    $TEMP_TYPE"
echo

printf "Display humidity for this sensor? (Y/n): "
read HUMIDITY_CHOICE
case "$HUMIDITY_CHOICE" in
    [nN]) HUMIDITY_ENABLED="false" ;;
    *)    HUMIDITY_ENABLED="true" ;;
esac

echo "Humidity:     $HUMIDITY_ENABLED"
echo

# Use Python to safely manipulate JSON and clean up discovered list
python3 << PYTHON_EOF
import json
import sys

config_file = "$CONFIG_FILE"
discovered_file = "$DISCOVERED_FILE"
mac = "$MAC"
custom_name = "$CUSTOM_NAME"
temp_type = "$TEMP_TYPE"
humidity_enabled = "$HUMIDITY_ENABLED" == "true"

try:
    # Read config
    with open(config_file, 'r') as f:
        config = json.load(f)

    # Ensure sensors array exists
    if 'sensors' not in config:
        config['sensors'] = []

    # Check if MAC already exists in sensors array
    existing_sensor = None
    for sensor in config['sensors']:
        if sensor.get('mac', '').upper() == mac.upper():
            existing_sensor = sensor
            break

    if existing_sensor:
        print(f"MAC address already exists in sensors")
        # Update existing sensor
        existing_sensor['humidity_enabled'] = humidity_enabled
        if custom_name:
            existing_sensor['name'] = custom_name
            print(f"Updated name: {custom_name}")
        if temp_type:
            try:
                temp_type_int = int(temp_type)
                if 0 <= temp_type_int <= 6:
                    existing_sensor['temperature_type'] = temp_type_int
                    print(f"Updated temperature type: {temp_type}")
                else:
                    print(f"Warning: Temperature type must be 0-6, skipping")
            except ValueError:
                print(f"Warning: Invalid temperature type, skipping")
    else:
        # Create new sensor object
        sensor = {"mac": mac, "humidity_enabled": humidity_enabled}

        if custom_name:
            sensor['name'] = custom_name
            print(f"Set custom name: {custom_name}")

        if temp_type:
            try:
                temp_type_int = int(temp_type)
                if 0 <= temp_type_int <= 6:
                    sensor['temperature_type'] = temp_type_int
                    print(f"Set temperature type: {temp_type}")
                else:
                    print(f"Warning: Temperature type must be 0-6, skipping")
            except ValueError:
                print(f"Warning: Invalid temperature type, skipping")

        config['sensors'].append(sensor)
        print(f"Added {mac} to sensors")

    # Write config
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"Configuration saved")

    # Remove from discovered sensors if present
    try:
        with open(discovered_file, 'r') as f:
            discovered = json.load(f)
        # Remove case-insensitively
        to_remove = [k for k in discovered if k.upper() == mac.upper()]
        if to_remove:
            for k in to_remove:
                del discovered[k]
            with open(discovered_file, 'w') as f:
                json.dump(discovered, f, indent=2)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_EOF

if [ $? -eq 0 ]; then
    echo
    echo "========================================"
    echo "  Sensor Added Successfully!"
    echo "========================================"
    echo
    printf "Restart service now to activate? (Y/n): "
    read RESTART_CHOICE
    case "$RESTART_CHOICE" in
        [nN])
            echo
            echo "Restart the service manually to activate:"
            echo "  svc -t /service/govee-ble"
            ;;
        *)
            svc -t /service/govee-ble
            echo "Service restarted."
            ;;
    esac
    echo
    echo "View current config:"
    echo "  cat $CONFIG_FILE"
    echo
    echo "Monitor logs:"
    echo "  tail -f /data/govee-ble/logs/govee_ble.log"
    echo
else
    echo
    echo "Failed to add sensor"
    exit 1
fi
