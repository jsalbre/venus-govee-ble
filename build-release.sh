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

OVERVIEW
--------
This package integrates Govee H5101/H5102/H5104 Bluetooth temperature/
humidity sensors with Victron Venus OS. Sensors appear natively in the
Venus OS GUI as standard temperature sensors.

PREREQUISITES
-------------
- Victron Venus OS device (Cerbo GX, Venus GX, etc.)
- Root SSH access enabled
- Govee H5101/H5102/H5104 sensors
- Bluetooth adapter (built-in or USB)

INSTALLATION STEPS
------------------

1. Transfer this tarball to your Venus OS device:

   scp govee-ble-deploy.tar.gz root@venus.local:/tmp/

2. SSH to Venus OS:

   ssh root@venus.local

3. Extract to system directories:

   cd /
   tar xzf /tmp/govee-ble-deploy.tar.gz

   This creates:
   - /data/govee-ble/           (application files)
   - /service/govee-ble/        (runit service)

4. Configure your sensors:

   vi /data/govee-ble/config.json

   Update with your sensor MAC addresses:

   {
     "allowlist": [
       "A4:C1:38:8E:0D:AF",
       "A4:C1:38:B8:DF:A1"
     ],
     "names": {
       "A4:C1:38:8E:0D:AF": "Freezer",
       "A4:C1:38:B8:DF:A1": "Fridge"
     },
     "temperature_type": {
       "A4:C1:38:8E:0D:AF": 6,
       "A4:C1:38:B8:DF:A1": 1
     }
   }

   Temperature types:
   0 = Battery, 1 = Fridge, 2 = Generic, 3 = Room,
   4 = Outdoor, 5 = Water heater, 6 = Freezer

5. Find your sensor MAC addresses:

   btmon -T | grep -i gvh

   Look for lines like:
   > HCI Event: LE Meta Event (0x3e)
       Address: A4:C1:38:8E:0D:AF (OUI A4-C1-38)
       ...
       Complete Local Name: GVH5101_0DAF

6. Test manually (recommended before enabling service):

   python3 /data/govee-ble/govee_ble_service.py \
       /data/govee-ble/config.json

   Watch for:
   - "Created service for [MAC]: [Name]"
   - "Registered D-Bus service: com.victronenergy.temperature.govee_XXXX"
   - Temperature readings being logged

   Press Ctrl+C to stop.

7. Verify D-Bus registration:

   In another terminal:

   dbus-send --system --print-reply \
     --dest=org.freedesktop.DBus \
     /org/freedesktop/DBus \
     org.freedesktop.DBus.ListNames | grep temperature

   You should see your govee_XXXX services listed.

8. Service will start automatically

   The service starts automatically via runit after extraction.
   Check status:

   svstat /service/govee-ble

9. Verify in Venus OS GUI:

   - Remote Console → Settings → Temperature sensors
   - Your sensors should appear with custom names
   - Device list should show live readings

10. Monitor logs:

    tail -f /data/govee-ble/logs/govee_ble.log

SERVICE MANAGEMENT
------------------

Check status:     svstat /service/govee-ble
Restart:          svc -t /service/govee-ble
Stop:             svc -d /service/govee-ble
Start:            svc -u /service/govee-ble
View logs:        tail -f /data/govee-ble/logs/govee_ble.log

TROUBLESHOOTING
---------------

Q: Sensors not appearing?
A: 1. Check allowlist in config.json
   2. Verify MAC addresses are uppercase
   3. Confirm sensors are advertising: btmon -T | grep -i gvh
   4. Check logs for errors

Q: Service won't start?
A: 1. Check logs: tail -n 50 /data/govee-ble/logs/govee_ble.log
   2. Verify btmon works: btmon -T | head -n 20
   3. Test Python imports (see step 6 in INSTALLATION STEPS)

Q: Configuration changes not saving?
A: This is now fixed in v1.0.0. GUI changes persist automatically.

UPDATING
--------

To update to a newer version:

1. Stop service:
   svc -d /service/govee-ble

2. Backup config (optional):
   cp /data/govee-ble/config.json /tmp/config.json.backup

3. Extract new tarball:
   cd /
   tar xzf /tmp/govee-ble-deploy.tar.gz

4. Restore config if needed:
   cp /tmp/config.json.backup /data/govee-ble/config.json

5. Start service:
   svc -u /service/govee-ble

UNINSTALLING
------------

svc -d /service/govee-ble
rm -rf /service/govee-ble
rm -rf /data/govee-ble

SUPPORT
-------

Documentation: https://github.com/yourusername/govee-ble-venus-py
Issues:        https://github.com/yourusername/govee-ble-venus-py/issues

When reporting issues, include:
- Venus OS version
- Sensor model
- Logs from /data/govee-ble/logs/govee_ble.log

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
