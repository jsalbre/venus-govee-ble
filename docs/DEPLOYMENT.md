# Govee BLE Service - Deployment Guide

**Target:** Venus OS (Cerbo GX)
**Version:** Phase 2 - D-Bus Integration

## Prerequisites

- Root SSH access to Venus OS device
- Govee H5101 sensors
- Bluetooth adapter (built-in or USB)

## Installation Steps

### 1. Prepare Directories on Venus OS

```bash
# SSH to Venus OS
ssh root@venus.local

# Create directories
mkdir -p /data/govee-ble/logs
mkdir -p /data/govee-ble/ext
```

### 2. Transfer Files to Venus OS

From your local machine:

```bash
# Transfer main source files
scp src/parser_adapter.py root@venus.local:/data/govee-ble/
scp src/btmon_reader.py root@venus.local:/data/govee-ble/
scp src/config_manager.py root@venus.local:/data/govee-ble/
scp src/govee_temperature_service.py root@venus.local:/data/govee-ble/
scp src/govee_ble_service.py root@venus.local:/data/govee-ble/

# Make main service executable
ssh root@venus.local "chmod +x /data/govee-ble/govee_ble_service.py"

# Transfer velib_python dependency
scp -r ext/velib_python root@venus.local:/data/govee-ble/ext/

# Transfer example config (customize first!)
scp config.example.json root@venus.local:/data/govee-ble/config.json
```

### 3. Configure Your Sensors

SSH to Venus OS and edit the config:

```bash
ssh root@venus.local
vi /data/govee-ble/config.json
```

Update the configuration with your sensor MAC addresses and names:

```json
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
    "A4:C1:38:8E:0D:AF": 1,
    "A4:C1:38:B8:DF:A1": 1
  }
}
```

**Temperature Type Values:**
- `0` = Battery sensor
- `1` = Fridge/Freezer
- `2` = Generic (default)

### 4. Test Manually (Recommended)

Before installing as a service, test manually:

```bash
# Run the service in foreground
python3 /data/govee-ble/govee_ble_service.py /data/govee-ble/config.json
```

Watch the output for:
- Service registration messages
- Sensor readings being published
- Any errors

Press Ctrl+C to stop.

### 5. Check D-Bus Registration

In another SSH session:

```bash
# List all temperature services
dbus-send --system --print-reply \
  --dest=org.freedesktop.DBus \
  /org/freedesktop/DBus \
  org.freedesktop.DBus.ListNames | grep temperature

# You should see:
# com.victronenergy.temperature.govee_0daf
# com.victronenergy.temperature.govee_dfa1

# Read a temperature value
dbus-send --system --print-reply \
  --dest=com.victronenergy.temperature.govee_0daf \
  /Temperature \
  com.victronenergy.BusItem.GetValue
```

### 6. Install Runit Service

Once manual testing works:

```bash
# Transfer service script
scp -r service/govee-ble root@venus.local:/service/

# Make script executable
ssh root@venus.local "chmod +x /service/govee-ble/run"

# The service will start automatically
# Check status:
ssh root@venus.local "svstat /service/govee-ble"
```

### 7. Verify in Venus OS GUI

1. Open Remote Console (or local display)
2. Navigate to: **Settings → Temperature sensors**
3. You should see your sensors listed with custom names
4. Navigate to: **Device list**
5. Verify temperature readings are updating

### 8. Monitor Logs

```bash
# View recent logs
ssh root@venus.local "tail -n 100 /data/govee-ble/logs/govee_ble.log"

# Follow logs in real-time
ssh root@venus.local "tail -f /data/govee-ble/logs/govee_ble.log"
```

## Updating the Service

To update after code changes:

```bash
# Stop the service
ssh root@venus.local "svc -d /service/govee-ble"

# Transfer updated files
scp src/govee_ble_service.py root@venus.local:/data/govee-ble/
# ... transfer other updated files

# Start the service
ssh root@venus.local "svc -u /service/govee-ble"

# Check status
ssh root@venus.local "svstat /service/govee-ble"
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
tail -n 50 /data/govee-ble/logs/govee_ble.log

# Check btmon is working
btmon -T | head -n 20

# Verify Python can import modules
python3 -c "import sys; sys.path.insert(1, '/data/govee-ble/ext/velib_python'); from vedbus import VeDbusService; print('OK')"
```

### Sensors Not Appearing

1. Verify sensors are in allowlist: `cat /data/govee-ble/config.json`
2. Check MAC addresses are correct (uppercase)
3. Verify sensors are advertising: `btmon -T | grep -i gvh`
4. Check logs for errors

### D-Bus Errors

```bash
# Check system D-Bus is running
ps | grep dbus

# Verify service registration
dbus-send --system --print-reply \
  --dest=org.freedesktop.DBus \
  /org/freedesktop/DBus \
  org.freedesktop.DBus.ListNames
```

### Restart Service

```bash
# Restart via runit
svc -t /service/govee-ble

# Or kill and let runit restart it
killall python3
```

## Uninstallation

```bash
# Stop and remove service
ssh root@venus.local "svc -d /service/govee-ble && rm -rf /service/govee-ble"

# Remove files (optional - keeps data)
ssh root@venus.local "rm -rf /data/govee-ble"
```

## Service Management Commands

```bash
# Check service status
svstat /service/govee-ble

# Stop service
svc -d /service/govee-ble

# Start service
svc -u /service/govee-ble

# Restart service
svc -t /service/govee-ble

# View service output
tail -f /data/govee-ble/logs/govee_ble.log
```

## Configuration Changes

After editing `/data/govee-ble/config.json`, restart the service:

```bash
svc -t /service/govee-ble
```

The service will automatically reload the configuration.

## Performance

Expected resource usage:
- **CPU:** <1% (idle), ~3-5% (active)
- **Memory:** ~15-20 MB
- **Disk:** ~70 MB max (logs rotate)
- **Network:** Minimal (D-Bus local only)

## VRM Portal Integration

Once sensors appear in Venus OS GUI, they will automatically:
- Show in device list
- Publish to VRM Portal (if configured)
- Be available for monitoring and alerts
- Appear in historical data graphs

No additional VRM configuration needed.
