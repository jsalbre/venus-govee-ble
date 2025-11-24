#!/bin/bash
# Govee BLE - Add Sensor to Allowlist
# Safely adds a MAC address to the allowlist in config.json

set -e

# Color output
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    GREEN=''
    YELLOW=''
    RED=''
    BLUE=''
    NC=''
fi

CONFIG_FILE="/data/govee-ble/config.json"

# Check if MAC was provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: MAC address required${NC}"
    echo
    echo "Usage: $0 <MAC_ADDRESS> [CUSTOM_NAME] [TEMP_TYPE]"
    echo
    echo "Examples:"
    echo "  $0 A4:C1:38:XX:XX:XX"
    echo "  $0 A4:C1:38:XX:XX:XX Freezer 6"
    echo "  $0 A4:C1:38:YY:YY:YY \"Fridge\" 1"
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
    echo -e "${RED}Error: Invalid MAC address format${NC}"
    echo "Expected format: AA:BB:CC:DD:EE:FF"
    exit 1
fi

# Convert to uppercase
MAC=$(echo "$MAC" | tr '[:lower:]' '[:upper:]')

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Config file not found: $CONFIG_FILE${NC}"
    echo "Is the Govee BLE service installed?"
    exit 1
fi

echo
echo "========================================"
echo "  Adding Sensor to Allowlist"
echo "========================================"
echo
echo "MAC Address:  ${BLUE}$MAC${NC}"
[ -n "$CUSTOM_NAME" ] && echo "Custom Name:  ${BLUE}$CUSTOM_NAME${NC}"
[ -n "$TEMP_TYPE" ] && echo "Temp Type:    ${BLUE}$TEMP_TYPE${NC}"
echo

# Use Python to safely manipulate JSON
python3 << PYTHON_EOF
import json
import sys

config_file = "$CONFIG_FILE"
mac = "$MAC"
custom_name = "$CUSTOM_NAME"
temp_type = "$TEMP_TYPE"

try:
    # Read config
    with open(config_file, 'r') as f:
        config = json.load(f)

    # Ensure allowlist exists
    if 'allowlist' not in config:
        config['allowlist'] = []

    # Check if already in allowlist
    if mac in config['allowlist']:
        print(f"MAC address already in allowlist")
        sys.exit(0)

    # Add to allowlist
    config['allowlist'].append(mac)
    print(f"Added {mac} to allowlist")

    # Add custom name if provided
    if custom_name:
        if 'names' not in config:
            config['names'] = {}
        config['names'][mac] = custom_name
        print(f"Set custom name: {custom_name}")

    # Add temperature type if provided
    if temp_type:
        if 'temperature_type' not in config:
            config['temperature_type'] = {}
        try:
            temp_type_int = int(temp_type)
            if 0 <= temp_type_int <= 6:
                config['temperature_type'][mac] = temp_type_int
                print(f"Set temperature type: {temp_type}")
            else:
                print(f"Warning: Temperature type must be 0-6, skipping")
        except ValueError:
            print(f"Warning: Invalid temperature type, skipping")

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
    echo "Restart the service to activate:"
    echo "  svc -t /service/govee-ble"
    echo
    echo "View current config:"
    echo "  cat $CONFIG_FILE"
    echo
    echo "Monitor logs:"
    echo "  tail -f /data/govee-ble/logs/govee_ble.log"
    echo
else
    echo
    echo -e "${RED}Failed to add sensor${NC}"
    exit 1
fi
