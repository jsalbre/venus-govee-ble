#!/bin/bash
# Govee BLE Venus OS - Release Build Script
# Creates deployment tarball for distribution

set -e  # Exit on error

VERSION="1.0.0"
RELEASE_NAME="govee-ble-deploy"
BUILD_DIR="/tmp/${RELEASE_NAME}"
TARBALL_NAME="${RELEASE_NAME}.tar.gz"

echo "========================================"
echo "Building Govee BLE Venus OS v${VERSION}"
echo "========================================"
echo

# Clean previous build
if [ -d "$BUILD_DIR" ]; then
    echo "Cleaning previous build..."
    rm -rf "$BUILD_DIR"
fi

# Create build structure
echo "Creating build directory structure..."
mkdir -p "$BUILD_DIR/data/govee-ble"
mkdir -p "$BUILD_DIR/service/govee-ble"

# Copy source files
echo "Copying source files..."
cp src/govee_ble_service.py "$BUILD_DIR/data/govee-ble/"
cp src/govee_temperature_service.py "$BUILD_DIR/data/govee-ble/"
cp src/parser_adapter.py "$BUILD_DIR/data/govee-ble/"
cp src/btmon_reader.py "$BUILD_DIR/data/govee-ble/"
cp src/config_manager.py "$BUILD_DIR/data/govee-ble/"
cp src/validate_parsing_v2.py "$BUILD_DIR/data/govee-ble/"

# Make main service executable
chmod +x "$BUILD_DIR/data/govee-ble/govee_ble_service.py"

# Copy velib_python dependency (excluding .git)
echo "Copying velib_python dependency..."
mkdir -p "$BUILD_DIR/data/govee-ble/ext"
rsync -a --exclude='.git' --exclude='.gitignore' --exclude='.travis.yml' \
    ext/velib_python/ "$BUILD_DIR/data/govee-ble/ext/velib_python/"

# Copy service files
echo "Copying service files..."
cp -r service/govee-ble "$BUILD_DIR/service/"
chmod +x "$BUILD_DIR/service/govee-ble/run"

# Copy helper scripts
echo "Copying helper scripts..."
cp install.sh "$BUILD_DIR/"
cp find-sensors.sh "$BUILD_DIR/data/govee-ble/"
chmod +x "$BUILD_DIR/install.sh"
chmod +x "$BUILD_DIR/data/govee-ble/find-sensors.sh"

# Copy example config as default config
echo "Copying configuration template..."
cp config.example.json "$BUILD_DIR/data/govee-ble/config.json"

# Create INSTALL.txt
echo "Creating installation instructions..."
cat > "$BUILD_DIR/INSTALL.txt" << 'EOF'
=========================================================
Govee BLE Venus OS Bridge - Installation Instructions
Version: 1.0.0
=========================================================

QUICK START
-----------

1. Transfer this tarball to your Venus OS device:

   scp govee-ble-deploy.tar.gz root@venus.local:/tmp/

2. SSH to Venus OS:

   ssh root@venus.local

3. Extract the tarball:

   cd /tmp
   tar xzf govee-ble-deploy.tar.gz
   cd govee-ble-deploy

4. Run the installation script:

   ./install.sh

   The script will:
   - Install all files to proper locations
   - Create default configuration
   - Prompt you to configure sensors
   - Optionally start the service

5. Find your Govee sensor MAC addresses:

   /data/govee-ble/find-sensors.sh

   This will scan for nearby Govee sensors and display their
   MAC addresses in the format needed for configuration.

   NOTE: Govee H510x sensors do NOT display MAC addresses on
   the device itself or in the Govee mobile app. You MUST use
   the find-sensors.sh script or btmon to discover them.

6. Edit configuration with your sensor MAC addresses:

   vi /data/govee-ble/config.json

   Add your sensor MAC addresses to the "allowlist" array.
   The find-sensors.sh script provides example configuration.

7. Start the service (if not already started):

   svc -u /service/govee-ble

8. Verify in Venus OS GUI:

   Remote Console → Settings → Temperature sensors

   Your sensors should appear within 1-2 minutes.

=========================================================

WHAT IT DOES
------------

This service integrates Govee H5101/H5102/H5104 Bluetooth
temperature/humidity sensors with Venus OS. Sensors appear as
native temperature devices in:

- Remote Console / Local display
- VRM Portal
- Device list
- Historical graphs

REQUIREMENTS
------------

- Venus OS v2.80+ (Python 3.12+)
- Govee H5101, H5102, or H5104 sensors
- Bluetooth adapter (built-in on most Victron devices)
- Sensors within Bluetooth range (10-30 meters)

=========================================================

IMPORTANT: FINDING SENSOR MAC ADDRESSES
----------------------------------------

Govee H510x sensors do NOT show their MAC addresses anywhere
on the physical device or in the Govee mobile app.

You MUST use one of these methods to find them:

Method 1: Use the provided helper script (RECOMMENDED):

   /data/govee-ble/find-sensors.sh

   This scans for 30 seconds and displays all found sensors
   with their MAC addresses and suggested configuration.

Method 2: Manual scanning with btmon:

   btmon -T | grep -i -A 3 gvh

   Look for lines showing:
   Address: A4:C1:38:XX:XX:XX (OUI A4-C1-38)
   Complete Local Name: GVH5101_XXXX

   The "Address" is what you need (uppercase format).

=========================================================

SERVICE MANAGEMENT
------------------

Check status:      svstat /service/govee-ble
Start:             svc -u /service/govee-ble
Stop:              svc -d /service/govee-ble
Restart:           svc -t /service/govee-ble
View logs:         tail -f /data/govee-ble/logs/govee_ble.log

TROUBLESHOOTING
---------------

Sensors not appearing?
  1. Run: /data/govee-ble/find-sensors.sh
  2. Verify MACs are in config.json allowlist
  3. Check logs: tail -f /data/govee-ble/logs/govee_ble.log

Service won't start?
  1. Check logs: tail -n 50 /data/govee-ble/logs/govee_ble.log
  2. Verify btmon works: btmon -T | head -n 20
  3. Re-run installer: ./install.sh

Configuration not saving from GUI?
  Fixed in v1.0.0 - GUI changes now persist automatically

UPDATING
--------

1. Stop service: svc -d /service/govee-ble
2. Extract new tarball to /tmp
3. Run: ./install.sh (preserves existing config)
4. Service will restart automatically

UNINSTALLING
------------

svc -d /service/govee-ble
rm -rf /service/govee-ble /data/govee-ble

SUPPORT
-------

Documentation: https://github.com/yourusername/govee-ble-venus-py
Issues:        https://github.com/yourusername/govee-ble-venus-py/issues

Include when reporting issues:
- Venus OS version (cat /opt/victronenergy/version)
- Sensor model (H5101/H5102/H5104)
- Logs (/data/govee-ble/logs/govee_ble.log)

=========================================================
EOF

# Create tarball
echo "Creating tarball..."
cd /tmp
tar czf "$TARBALL_NAME" "$RELEASE_NAME"

# Copy to project directory
cp "$TARBALL_NAME" "$OLDPWD/"

echo
echo "========================================"
echo "Build complete!"
echo "========================================"
echo
echo "Output: $TARBALL_NAME"
echo "Size:   $(du -h $TARBALL_NAME | cut -f1)"
echo
echo "Contents:"
tar tzf "$TARBALL_NAME" | head -20
echo "..."
echo "($(tar tzf $TARBALL_NAME | wc -l) files total)"
echo
echo "To test:"
echo "  tar tzf $TARBALL_NAME | grep -E '(dev-notes|samples|\.git)' || echo 'No meta files found - OK!'"
echo
