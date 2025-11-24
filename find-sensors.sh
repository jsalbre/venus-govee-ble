#!/bin/bash
# Govee BLE Sensor Discovery Tool
# Scans for Govee H510x sensors and displays their MAC addresses

# Color output
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    NC='\033[0m'
else
    GREEN=''
    YELLOW=''
    BLUE=''
    CYAN=''
    NC=''
fi

SCAN_DURATION=30
TEMP_FILE="/tmp/govee_scan_$$.txt"

# Cleanup on exit
trap "rm -f $TEMP_FILE" EXIT

echo
echo "==========================================="
echo "  Govee Sensor Discovery"
echo "==========================================="
echo
echo "Scanning for Govee H510x sensors..."
echo -e "${YELLOW}This will take $SCAN_DURATION seconds...${NC}"
echo

# Check if btmon is available
if ! command -v btmon &> /dev/null; then
    echo -e "${RED}ERROR: btmon not found${NC}"
    echo "Please install bluez-utils:"
    echo "  opkg update && opkg install bluez-utils"
    exit 1
fi

# Start scanning in background (timeout doesn't exist on BusyBox)
btmon -T 2>/dev/null | grep -E '(Address: A4:C1:38|Complete Local Name: GVH)' > "$TEMP_FILE" &
BTMON_PID=$!

# Progress indicator with countdown
for i in $(seq 1 $SCAN_DURATION); do
    echo -ne "\rScanning... $i/$SCAN_DURATION seconds "
    sleep 1
done
echo

# Kill btmon process
kill $BTMON_PID 2>/dev/null || true
wait $BTMON_PID 2>/dev/null || true
sleep 1

# Parse results
echo
echo "==========================================="
echo "  Detected Govee Sensors"
echo "==========================================="
echo

if [ ! -s "$TEMP_FILE" ]; then
    echo -e "${YELLOW}No Govee sensors detected.${NC}"
    echo
    echo "Troubleshooting:"
    echo "  1. Ensure sensors have batteries and are powered on"
    echo "  2. Check sensors are within Bluetooth range (10-30m)"
    echo "  3. Verify Bluetooth adapter is working:"
    echo "     hciconfig"
    echo "  4. Try a longer scan:"
    echo "     btmon -T | grep -i gvh"
    exit 0
fi

# Extract unique MAC addresses and their names
SENSOR_COUNT=0
declare -A SENSORS

while IFS= read -r line; do
    if echo "$line" | grep -q "Address: A4:C1:38"; then
        LAST_MAC=$(echo "$line" | grep -oE 'A4:C1:38:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}')
    elif echo "$line" | grep -q "Complete Local Name: GVH"; then
        NAME=$(echo "$line" | sed 's/.*Complete Local Name: //')
        if [ -n "$LAST_MAC" ]; then
            SENSORS["$LAST_MAC"]="$NAME"
            LAST_MAC=""
        fi
    fi
done < "$TEMP_FILE"

# Display found sensors
if [ ${#SENSORS[@]} -eq 0 ]; then
    echo -e "${YELLOW}No Govee H510x sensors found.${NC}"
    echo
    echo "Found Govee advertisements but couldn't parse MAC addresses."
    echo "Raw output saved to: $TEMP_FILE"
else
    for mac in "${!SENSORS[@]}"; do
        ((SENSOR_COUNT++))
        name="${SENSORS[$mac]}"
        echo -e "${GREEN}Sensor $SENSOR_COUNT:${NC}"
        echo -e "  MAC:  ${CYAN}$mac${NC}"
        echo -e "  Name: ${BLUE}$name${NC}"
        echo
    done

    echo "==========================================="
    echo "  Configuration"
    echo "==========================================="
    echo
    echo "Add these MAC addresses to your config.json:"
    echo
    echo '{'
    echo '  "allowlist": ['

    first=true
    for mac in "${!SENSORS[@]}"; do
        if [ "$first" = true ]; then
            echo "    \"$mac\""
            first=false
        else
            echo "    \"$mac\""
        fi
    done

    echo '  ],'
    echo '  "names": {'

    first=true
    for mac in "${!SENSORS[@]}"; do
        name="${SENSORS[$mac]}"
        # Extract last 4 chars of name (e.g., GVH5101_0DAF -> 0DAF)
        suffix=$(echo "$name" | grep -oE '_[0-9A-F]{4}$' | tr -d '_' || echo "Sensor")

        if [ "$first" = true ]; then
            echo "    \"$mac\": \"Govee_$suffix\""
            first=false
        else
            echo "    \"$mac\": \"Govee_$suffix\""
        fi
    done

    echo '  },'
    echo '  "temperature_type": {'

    first=true
    for mac in "${!SENSORS[@]}"; do
        if [ "$first" = true ]; then
            echo "    \"$mac\": 2"
            first=false
        else
            echo "    \"$mac\": 2"
        fi
    done

    echo '  }'
    echo '}'
    echo
    echo "Temperature types:"
    echo "  0=Battery, 1=Fridge, 2=Generic, 3=Room,"
    echo "  4=Outdoor, 5=Water heater, 6=Freezer"
    echo
    echo "Edit configuration:"
    echo "  vi /data/govee-ble/config.json"
    echo
    echo "After editing, restart the service:"
    echo "  svc -t /service/govee-ble"
fi

echo
