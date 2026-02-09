#!/bin/bash
# Govee BLE - Add Sensor to Allowlist
# Safely adds a MAC address to the allowlist in config.json

set -e

CONFIG_FILE="/data/govee-ble/config.json"

# Check if MAC was provided
if [ -z "$1" ]; then
    echo "Error: MAC address required"
    echo
    echo "Usage: $0 <MAC_ADDRESS> [CUSTOM_NAME] [TEMP_TYPE]"
    echo
    echo "Examples:"
    echo "  $0 A4:C1:38:XX:XX:XX"
    echo "  $0 A4:C1:38:XX:XX:XX Freezer 6"
    echo "  $0 A4:C1:38:YY:YY:YY \"Fridge\" 1"
    echo "  $0 D1:30:38:36:24:0C \"Living Room\" 3"
    echo
    echo "Temperature Types:"
    echo "  0=Battery, 1=Fridge, 2=Generic, 3=Room,"
    echo "  4=Outdoor, 5=Water heater, 6=Freezer"
    exit 1
fi

MAC="$1"
CUSTOM_NAME="${2:-}"
TEMP_TYPE="${3:-}"

# Validate MAC format (basic check)
if ! echo "$MAC" | grep -qE '^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$'; then
    echo "Error: Invalid MAC address format"
    echo "Expected format: AA:BB:CC:DD:EE:FF"
    exit 1
fi

# Convert to uppercase
MAC=$(echo "$MAC" | tr '[:lower:]' '[:upper:]')

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found: $CONFIG_FILE"
    echo "Is the Govee BLE service installed?"
    exit 1
fi

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

# Use Python to safely manipulate JSON
python3 << PYTHON_EOF
import json
import sys

config_file = "$CONFIG_FILE"
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

    # Write back
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"Configuration saved")

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
