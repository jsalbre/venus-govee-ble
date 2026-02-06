# Installation Guide

**Version:** 1.4.0

This guide covers installing the Govee BLE Venus OS Bridge on your Victron device.

**Note:** v1.2.0+ uses a `sensors` array configuration format. v1.3.0+ adds support for H5100 and H5105 sensors. v1.4.0+ adds humidity control and DeviceName path. See [README.md](../README.md) for current config examples and the [CHANGELOG](../CHANGELOG.md) for version details.

## Quick Installation

For most users, follow these steps:

1. **Download** the latest `govee-ble-deploy.tar.gz` from [Releases](../../../releases)
2. **Transfer** to your Venus OS device
3. **Extract** and follow the included `INSTALL.txt`

The deployment tarball includes comprehensive installation instructions.

## Prerequisites

### Hardware
- Victron Venus OS device (Cerbo GX, Venus GX, MultiPlus GX, etc.)
- Bluetooth adapter (most Victron devices have built-in Bluetooth)
- Govee H5101, H5102, or H5104 temperature/humidity sensors

### Software
- Venus OS v2.80 or newer (Python 3.12+)
- Root SSH access enabled
- `btmon` utility (included in Venus OS)

### Network
- SSH access to Venus OS device (ethernet or Wi-Fi)
- Sensors within Bluetooth range (typically 10-30 meters)

## Detailed Installation Steps

### 1. Enable SSH Access

If not already enabled:

1. Connect to your Venus OS device (local display or Remote Console)
2. Navigate to **Settings → General**
3. Scroll down to **SSH on LAN**
4. Enable SSH access

### 2. Find Your Sensor MAC Addresses

**IMPORTANT:** Govee H510x sensors do NOT display MAC addresses on the device or in the Govee mobile app.

You must use one of these methods:

**Method A (Recommended): Use Service Discovery**

The service automatically discovers and logs Govee sensors:

```bash
# SSH to Venus OS
ssh root@venus.local

# Start the service
svc -u /service/govee-ble

# Monitor logs for discovered sensors
tail -f /data/govee-ble/logs/govee_ble.log

# Look for lines like:
# Discovered Govee sensor not in allowlist: A4:C1:38:XX:XX:XX (GVH5101_XXXX)
```

**Method B: Manual btmon Scanning**
```bash
# SSH to Venus OS
ssh root@venus.local

# Scan for Govee devices
btmon -T | grep -i -A 5 gvh

# Look for lines like:
# Address: A4:C1:38:8E:0D:AF (OUI A4-C1-38)
# Complete Local Name: GVH5101_0DAF
```

Make note of the MAC addresses (the `A4:C1:38:...` part).

### 3. Transfer Deployment Package

From your computer:

```bash
# Download govee-ble-deploy.tar.gz from GitHub releases
# Then transfer to Venus OS:
scp govee-ble-deploy.tar.gz root@venus.local:/tmp/
```

### 4. Install on Venus OS

SSH to Venus OS and extract:

```bash
ssh root@venus.local

# Extract to system directories
cd /
tar xzf /tmp/govee-ble-deploy.tar.gz

# This creates:
#   /data/govee-ble/     - Application files and config
#   /service/govee-ble/  - Runit service (auto-starts)
```

### 5. Configure Your Sensors

Edit the configuration file:

```bash
vi /data/govee-ble/config.json
```

Update with your sensor MAC addresses:

```json
{
  "allowlist": [
    "A4:C1:38:8E:0D:AF",
    "A4:C1:38:B8:DF:A1"
  ],
  "names": {
    "A4:C1:38:8E:0D:AF": "Freezer",
    "A4:C1:38:B8:DF:A1": "Fridge"
  ],
  "temperature_type": {
    "A4:C1:38:8E:0D:AF": 6,
    "A4:C1:38:B8:DF:A1": 1
  },
  "temperature_type_default": 2,
  "log_level": "INFO"
}
```

**Important:**
- MAC addresses must be **uppercase**
- Match the format exactly: `A4:C1:38:XX:XX:XX`
- Add all sensors you want to monitor to the `allowlist`

**Temperature Types:**
| Value | Type | Best For |
|-------|------|----------|
| 0 | Battery sensor | Battery compartments |
| 1 | Fridge | Refrigerators |
| 2 | Generic | General use (default) |
| 3 | Room | Indoor ambient temperature |
| 4 | Outdoor | Outdoor/external sensors |
| 5 | Water heater | Hot water tanks |
| 6 | Freezer | Freezers |

### 6. Test Before Enabling Service

It's recommended to test manually first:

```bash
# Run in foreground to see live output
python3 /data/govee-ble/govee_ble_service.py \
    /data/govee-ble/config.json

# Watch for:
# - "Govee BLE Service v2.0.0 initializing"
# - "Created service for [MAC]: [Name]"
# - "Registered D-Bus service: com.victronenergy.temperature.govee_XXXX"
# - Temperature/humidity readings

# Press Ctrl+C to stop when satisfied
```

### 7. Verify D-Bus Registration

While the service is running, in another SSH session:

```bash
# List all temperature services
dbus-send --system --print-reply \
  --dest=org.freedesktop.DBus \
  /org/freedesktop/DBus \
  org.freedesktop.DBus.ListNames | grep temperature

# You should see lines like:
# "com.victronenergy.temperature.govee_0daf"
# "com.victronenergy.temperature.govee_dfa1"

# Read a temperature value
dbus-send --system --print-reply \
  --dest=com.victronenergy.temperature.govee_0daf \
  /Temperature \
  com.victronenergy.BusItem.GetValue
```

### 8. Enable Automatic Startup

The service starts automatically via runit after installation. Check status:

```bash
# Check service status
svstat /service/govee-ble

# You should see:
# /service/govee-ble: up (pid XXXXX) X seconds

# If not running, start it:
svc -u /service/govee-ble
```

### 9. Verify in Venus OS GUI

1. Open **Remote Console** (or local display)
2. Navigate to **Settings → Temperature sensors**
3. Your sensors should appear with custom names
4. Navigate to **Device list**
5. Verify temperature readings are updating

### 10. Monitor Logs

```bash
# View recent logs
tail -n 100 /data/govee-ble/logs/govee_ble.log

# Follow logs in real-time
tail -f /data/govee-ble/logs/govee_ble.log

# Look for:
# - Successful startup messages
# - "Updated - Temp=X.XC, Humidity=X.X%, Battery=X%"
# - No error messages
```

## Post-Installation

### Check VRM Portal

If your Venus OS device is connected to VRM:

1. Log in to [vrm.victronenergy.com](https://vrm.victronenergy.com)
2. Select your installation
3. Navigate to **Device List**
4. Your Govee sensors should appear
5. Historical data will be available after ~15 minutes

### Customize Names and Types in GUI

You can change sensor names and temperature types directly in Venus OS:

1. **Settings → Temperature sensors**
2. Select a sensor
3. Edit **Custom name** or **Temperature type**
4. Changes are **automatically saved** to config.json

This is a v1.0 feature - GUI changes persist across restarts!

### Set Up Alarms (Optional)

Configure temperature alarms in Venus OS:

1. **Settings → Temperature sensors**
2. Select sensor
3. Set **Temperature alarm** thresholds
4. Configure notification preferences

## Troubleshooting

### Sensors Not Appearing

**Check 1: Verify sensors are in allowlist**
```bash
cat /data/govee-ble/config.json | grep -A 5 allowlist
```

**Check 2: Verify sensors are advertising**
```bash
btmon -T | grep -i gvh | head -20
# Should see your sensor MAC addresses
```

**Check 3: Check logs for errors**
```bash
tail -n 50 /data/govee-ble/logs/govee_ble.log | grep -i error
```

**Check 4: Verify MAC addresses are uppercase**
```bash
cat /data/govee-ble/config.json | grep -E 'a4:c1:38'
# Should return nothing (all lowercase is wrong)
```

### Service Won't Start

**Check service status**
```bash
svstat /service/govee-ble
# If "down", check logs for why
tail -n 50 /data/govee-ble/logs/govee_ble.log
```

**Verify Python environment**
```bash
python3 --version
# Should be 3.12.12 or newer

# Test imports
python3 -c "import sys; sys.path.insert(1, '/data/govee-ble/ext/velib_python'); from vedbus import VeDbusService; print('OK')"
# Should print "OK"
```

**Check btmon is working**
```bash
btmon -T | head -n 20
# Should show Bluetooth activity
```

### Readings Not Updating

**Check last update timestamp**
```bash
dbus-send --system --print-reply \
  --dest=com.victronenergy.temperature.govee_0daf \
  /Mgmt/LastUpdate \
  com.victronenergy.BusItem.GetValue
```

**Check sensor is not marked as disconnected**
```bash
dbus-send --system --print-reply \
  --dest=com.victronenergy.temperature.govee_0daf \
  /Status \
  com.victronenergy.BusItem.GetValue
# Should return 0 (OK), not 1 (Disconnected)
```

**Verify sensor battery**
- Replace batteries if below 20%
- Low battery affects transmission range and frequency

### Configuration Changes Not Saving

This was a known issue fixed in v1.0.0. If you're still experiencing this:

1. Verify you're running v1.0.0:
   ```bash
   grep __version__ /data/govee-ble/govee_ble_service.py
   # Should show "2.0.0"
   ```

2. Check logs for errors:
   ```bash
   grep -i "Failed to save" /data/govee-ble/logs/govee_ble.log
   ```

## Updating

To update to a newer version:

1. Stop the service:
   ```bash
   svc -d /service/govee-ble
   ```

2. **Backup your config** (optional but recommended):
   ```bash
   cp /data/govee-ble/config.json /tmp/config.json.backup
   ```

3. Extract new release:
   ```bash
   cd /
   tar xzf /tmp/govee-ble-deploy.tar.gz
   ```

4. Restore your config if overwritten:
   ```bash
   cp /tmp/config.json.backup /data/govee-ble/config.json
   ```

5. Start the service:
   ```bash
   svc -u /service/govee-ble
   ```

## Uninstalling

To completely remove the service:

```bash
# Stop and remove service
svc -d /service/govee-ble
rm -rf /service/govee-ble

# Remove application files
rm -rf /data/govee-ble
```

Configuration and logs will be removed as well.

## Advanced Configuration

### Change Log Level

For more detailed logging:

```bash
vi /data/govee-ble/config.json
# Change "log_level": "INFO" to "log_level": "DEBUG"

# Restart service
svc -t /service/govee-ble
```

**Warning:** DEBUG logging is verbose and will fill logs faster.

### Adjust Stale Threshold

Change how long before a sensor is marked as disconnected:

```json
{
  "stale_threshold_sec": 180
}
```

Default is 120 seconds (2 minutes). Increase if sensors are intermittently marked disconnected.

### Modify Restart Backoff

Adjust error recovery timing:

```json
{
  "restart_min_delay_sec": 30,
  "restart_max_delay_sec": 300
}
```

Service uses exponential backoff between these values after crashes.

## Getting Help

If you encounter issues not covered here:

1. Check the logs: `/data/govee-ble/logs/govee_ble.log`
2. Review [Deployment Guide](DEPLOYMENT.md) for advanced troubleshooting
3. Open an [Issue](../../../issues) on GitHub with:
   - Venus OS version (`cat /opt/victronenergy/version`)
   - Sensor model (H5101/H5102/H5104)
   - Relevant log excerpt
   - Configuration (with MAC addresses redacted if desired)

## Next Steps

- Configure temperature alarms in Venus OS
- Monitor sensors in VRM Portal
- Set up notifications for out-of-range temperatures
- Consider adding more sensors (just update config.json)
