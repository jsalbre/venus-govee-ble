#!/bin/bash
# Govee BLE Venus OS - Release Build Script
# Creates deployment tarball for distribution

set -e  # Exit on error

VERSION=$(grep -oP '(?<=__version__ = ").*(?=")' src/_version.py)
RELEASE_NAME="govee-ble-deploy"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build/${RELEASE_NAME}"
DIST_DIR="${SCRIPT_DIR}/dist"
TARBALL_NAME="${RELEASE_NAME}.tar.gz"
TARBALL_PATH="${DIST_DIR}/${TARBALL_NAME}"

echo "========================================"
echo "Building Govee BLE Venus OS v${VERSION}"
echo "========================================"
echo

# Clean previous build
if [ -d "$BUILD_DIR" ]; then
    echo "Cleaning previous build..."
    rm -rf "$BUILD_DIR"
fi

# Create build and dist directories
echo "Creating build directory structure..."
mkdir -p "$BUILD_DIR/data/govee-ble"
mkdir -p "$BUILD_DIR/service/govee-ble"
mkdir -p "$DIST_DIR"

# Copy source files
echo "Copying source files..."
cp src/_version.py "$BUILD_DIR/data/govee-ble/"
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
cp add-sensor.sh "$BUILD_DIR/data/govee-ble/"
chmod +x "$BUILD_DIR/install.sh"
chmod +x "$BUILD_DIR/data/govee-ble/add-sensor.sh"

# Copy example config as default config
echo "Copying configuration template..."
cp config.example.json "$BUILD_DIR/data/govee-ble/config.json"

# Copy documentation files
echo "Copying documentation..."
cp README.md "$BUILD_DIR/"
cp CHANGELOG.md "$BUILD_DIR/"

# Create INSTALL.txt
echo "Creating installation instructions..."
cat > "$BUILD_DIR/INSTALL.txt" << 'EOF'
=========================================================
Govee BLE Venus OS Bridge - Installation Instructions
Version: 1.4.0
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
   - Automatically backup existing installation (if present)
   - Install all files to proper locations
   - Create default configuration
   - Prompt you to configure sensors
   - Optionally start the service

   IMPORTANT: If updating, your previous installation is automatically
   backed up to /data/govee-ble.backup.YYYYMMDD_HHMMSS for safety.

5. Find your Govee sensor MAC addresses:

   The service automatically logs discovered Govee sensors.
   Start the service and monitor the logs:

   svc -u /service/govee-ble
   tail -f /data/govee-ble/logs/govee_ble.log

   Look for lines like:
   "Discovered Govee sensor not in sensors: A4:C1:38:XX:XX:XX (GVH5101_XXXX)"

   NOTE: Govee H510x sensors do NOT display MAC addresses on
   the device itself or in the Govee mobile app.

6. Add sensors to configuration:

   Use the add-sensor.sh helper script:
   /data/govee-ble/add-sensor.sh A4:C1:38:XX:XX:XX "Sensor Name" [type]

   Or edit manually:
   vi /data/govee-ble/config.json

7. Start the service (if not already started):

   svc -u /service/govee-ble

8. Verify in Venus OS GUI:

   Remote Console → Settings → Temperature sensors

   Your sensors should appear within 1-2 minutes.

=========================================================

WHAT IT DOES
------------

This service integrates Govee H5100/H5101/H5102/H5104/H5105 Bluetooth
temperature/humidity sensors with Venus OS. Sensors appear as
native temperature devices in:

- Remote Console / Local display
- VRM Portal
- Device list
- Historical graphs

REQUIREMENTS
------------

- Venus OS v2.80+ (Python 3.12+)
- Govee H5100, H5101, H5102, H5104, or H5105 sensors
- Bluetooth adapter (built-in on most Victron devices)
- Sensors within Bluetooth range (10-30 meters)

=========================================================

IMPORTANT: FINDING SENSOR MAC ADDRESSES
----------------------------------------

Govee H510x sensors do NOT show their MAC addresses anywhere
on the physical device or in the Govee mobile app.

You MUST use one of these methods to find them:

Method 1 (RECOMMENDED): Monitor service logs

   The service automatically discovers and logs Govee sensors.
   Start the service and watch the logs:

   svc -u /service/govee-ble
   tail -f /data/govee-ble/logs/govee_ble.log

   Look for: "Discovered Govee sensor not in sensors:"

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
  1. Check logs for discovered sensors: tail -f /data/govee-ble/logs/govee_ble.log
  2. Verify MACs are in config.json sensors array
  3. Ensure sensors have fresh batteries and are in range

Service won't start?
  1. Check logs: tail -n 50 /data/govee-ble/logs/govee_ble.log
  2. Verify btmon works: btmon -T | head -n 20
  3. Re-run installer: ./install.sh

Configuration not saving from GUI?
  Fixed in v1.0.0 - GUI changes now persist automatically

UPDATING
--------

1. Download new release tarball
2. Transfer to Venus OS and extract:
   scp govee-ble-deploy.tar.gz root@venus.local:/tmp/
   cd /tmp && tar xzf govee-ble-deploy.tar.gz
3. Run installer: cd govee-ble-deploy && ./install.sh

The installer automatically:
- Backs up your current installation
- Preserves your configuration
- Stops/restarts the service

To restore a backup if needed:
   svc -d /service/govee-ble
   rm -rf /data/govee-ble
   mv /data/govee-ble.backup.YYYYMMDD_HHMMSS /data/govee-ble
   svc -u /service/govee-ble

UNINSTALLING
------------

svc -d /service/govee-ble
rm -rf /service/govee-ble /data/govee-ble

SUPPORT
-------

Documentation: https://github.com/jsalbre/govee-ble-venus-py
Issues:        https://github.com/jsalbre/govee-ble-venus-py/issues

Include when reporting issues:
- Venus OS version (cat /opt/victronenergy/version)
- Sensor model (H5100/H5101/H5102/H5104/H5105)
- Logs (/data/govee-ble/logs/govee_ble.log)

=========================================================
EOF

# Create tarball
echo "Creating tarball..."
cd "${SCRIPT_DIR}/build"
tar czf "$TARBALL_PATH" "$RELEASE_NAME"

echo
echo "========================================"
echo "Build complete!"
echo "========================================"
echo
echo "Output: ${TARBALL_PATH}"
echo "Size:   $(du -h "$TARBALL_PATH" | cut -f1)"
echo
echo "Contents:"
tar tzf "$TARBALL_PATH" | head -20
echo "..."
echo "($(tar tzf "$TARBALL_PATH" | wc -l) files total)"
echo
echo "To test:"
echo "  tar tzf \"$TARBALL_PATH\" | grep -E '(dev-notes|samples|\.git)' || echo 'No meta files found - OK!'"
echo
echo "Deploy to Venus OS:"
echo "  scp \"$TARBALL_PATH\" root@venus.local:/tmp/"
echo
