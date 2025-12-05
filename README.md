# Govee BLE Venus OS Bridge

**Version:** 1.2.0
**Status:** Production Ready

Python bridge for integrating Govee H510x Bluetooth temperature/humidity sensors with Victron Energy Venus OS.

## Overview

This project enables Victron Cerbo GX devices to monitor Govee H5101/H5102/H5104 temperature and humidity sensors via Bluetooth Low Energy (BLE). Sensor readings appear natively in Venus OS as `com.victronenergy.temperature` services, making them available in:

- Remote Console / Local display
- VRM Portal dashboards
- Node-RED flows
- Victron apps (VictronConnect, VRM)

## Features

- **Automatic Discovery** - Detects and monitors configured Govee sensors
- **Real-time Updates** - Temperature, humidity, battery, and RSSI
- **Native Integration** - Appears as standard Venus OS temperature sensors
- **Persistent Config** - GUI changes (names, types) saved automatically
- **Robust Operation** - Exponential backoff, watchdog, log rotation
- **Low Resource Usage** - <1% CPU idle, ~15-20 MB RAM

## Hardware Requirements

- **Venus OS Device** - Cerbo GX, Venus GX, or compatible
- **Bluetooth Adapter** - Built-in or USB
- **Sensors** - Govee H5101, H5102, or H5104

## Supported Sensors

| Model | Status | Notes |
|-------|--------|-------|
| **H5101** | ✓ Tested | Primary support, refrigerator/freezer monitoring |
| **H5102** | ✓ Compatible | Same protocol as H5101 |
| **H5104** | ✓ Compatible | Same protocol as H5101 |
| H5075, H5074 | ⚠ Untested | May work, parser not implemented |

## Sensor Accuracy

Based on validation against Govee mobile app:

| Metric | Accuracy | Notes |
|--------|----------|-------|
| **Temperature** | ±0.5°C | Excellent |
| **Battery** | Exact | 100% match |
| **Humidity** | ~15-20% error | Known limitation, usable |
| **RSSI** | Real-time | Signal strength |

## Quick Start

### 1. Download and Transfer

Download `govee-ble-deploy.tar.gz` from [Releases](../../releases) and transfer to Venus OS:

```bash
scp govee-ble-deploy.tar.gz root@venus.local:/tmp/
```

### 2. Run Installation Script

```bash
# SSH to Venus OS
ssh root@venus.local

# Extract and run installer
cd /tmp
tar xzf govee-ble-deploy.tar.gz
cd govee-ble-deploy
./install.sh
```

The installer automatically:
- Deploys files to proper locations
- Creates default configuration
- Sets up the runit service
- Prompts to start the service

### 3. Find Your Sensors

**Important:** Govee H510x sensors do NOT display MAC addresses on the device or in the Govee app.

The service automatically discovers and logs Govee sensors. Start the service and monitor the logs:

```bash
# Start service
svc -u /service/govee-ble

# Watch for discovered sensors
tail -f /data/govee-ble/logs/govee_ble.log
```

Look for log entries like:
```
Discovered Govee sensor not in sensors: A4:C1:38:XX:XX:XX (GVH5101_XXXX) - Add to config.json sensors array to monitor
```

### 4. Configure

Add discovered MAC addresses to config:

```bash
vi /data/govee-ble/config.json
```

Example configuration:

```json
{
  "sensors": [
    {
      "mac": "A4:C1:38:XX:XX:XX",
      "name": "Freezer",
      "temperature_type": 6
    },
    {
      "mac": "A4:C1:38:YY:YY:YY",
      "name": "Fridge",
      "temperature_type": 1
    }
  ]
}
```

Or use the helper script:
```bash
/data/govee-ble/add-sensor.sh A4:C1:38:XX:XX:XX Freezer 6
/data/govee-ble/add-sensor.sh A4:C1:38:YY:YY:YY Fridge 1
```

**Temperature Types:** 0=Battery, 1=Fridge, 2=Generic, 3=Room, 4=Outdoor, 5=Water heater, 6=Freezer

### 5. Start and Verify

```bash
# Start service (if not already running)
svc -u /service/govee-ble

# Check logs
tail -f /data/govee-ble/logs/govee_ble.log
```

Verify in Venus OS GUI:
- **Settings → Temperature sensors** - Sensors appear here
- **Device list** - Shows live readings
- **VRM Portal** - Historical data (after 15 minutes)

## Documentation

- **[Installation Guide](docs/INSTALL.md)** - Detailed installation steps
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Advanced deployment options
- **[Configuration](#configuration)** - Configuration file reference

## Configuration

The service is configured via `/data/govee-ble/config.json`:

```json
{
  "sensors": [
    {
      "mac": "A4:C1:38:XX:XX:XX",
      "name": "Custom Name",
      "temperature_type": 1,
      "device_instance": null
    }
  ],
  "temperature_type_default": 2,
  "log_level": "INFO",
  "log_path": "/data/govee-ble/logs/govee_ble.log",
  "stale_threshold_sec": 300,
  "restart_min_delay_sec": 30,
  "restart_max_delay_sec": 300,
  "battery": {
    "low_alarm_threshold_pct": 15.0
  }
}
```

### Configuration Keys

| Key | Type | Description |
|-----|------|-------------|
| `sensors` | array | Array of sensor objects (see below) |
| `temperature_type_default` | int | Default type for new sensors (0-6) |
| `log_level` | string | Logging level: DEBUG, INFO, WARNING, ERROR |
| `stale_threshold_sec` | int | Seconds before sensor marked disconnected |

### Sensor Object Fields

Each sensor in the `sensors` array has:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mac` | string | Yes | MAC address (uppercase, e.g., "A4:C1:38:XX:XX:XX") |
| `name` | string | No | Custom display name (defaults to "GVH5101_XXXX") |
| `temperature_type` | int | No | Type 0-6 (defaults to `temperature_type_default`) |
| `device_instance` | int/null | No | VRM device instance (auto-assigned if null) |

**Example:**
```json
{
  "mac": "A4:C1:38:XX:XX:XX",
  "name": "Freezer",
  "temperature_type": 6
}
```

## Service Management

```bash
# Check status
svstat /service/govee-ble

# Restart service
svc -t /service/govee-ble

# Stop service
svc -d /service/govee-ble

# Start service
svc -u /service/govee-ble

# View logs
tail -f /data/govee-ble/logs/govee_ble.log
```

## Troubleshooting

### Sensors Not Appearing

1. Check logs for discovered sensors: `tail -f /data/govee-ble/logs/govee_ble.log`
2. Verify MAC addresses in sensors array (must be uppercase): `cat /data/govee-ble/config.json`
3. Ensure sensors have fresh batteries and are within range (10-30m)
4. Check service is running: `svstat /service/govee-ble`

### Service Won't Start

```bash
# Check logs for errors
tail -n 50 /data/govee-ble/logs/govee_ble.log

# Verify btmon is working
btmon -T | head -n 20

# Test Python imports
python3 -c "import sys; sys.path.insert(1, '/data/govee-ble/ext/velib_python'); from vedbus import VeDbusService; print('OK')"
```

### D-Bus Issues

```bash
# List temperature services
dbus-send --system --print-reply \
  --dest=org.freedesktop.DBus \
  /org/freedesktop/DBus \
  org.freedesktop.DBus.ListNames | grep temperature

# Read a specific value
dbus-send --system --print-reply \
  --dest=com.victronenergy.temperature.govee_xxxx \
  /Temperature \
  com.victronenergy.BusItem.GetValue
```

## Project Structure

```
govee-ble-venus-py/
├── src/                           # Source code
│   ├── govee_ble_service.py       # Main service orchestrator
│   ├── govee_temperature_service.py # D-Bus temperature service
│   ├── parser_adapter.py          # BLE advertisement parser
│   ├── btmon_reader.py            # btmon process manager
│   ├── config_manager.py          # Configuration management
│   └── validate_parsing_v2.py     # Validation tool
├── service/                       # Runit service files
│   └── govee-ble/run              # Service startup script
├── ext/                           # Dependencies
│   └── velib_python/              # Victron Venus library
├── docs/                          # User documentation
│   ├── INSTALL.md
│   └── DEPLOYMENT.md
├── dev-notes/                     # Development notes (not in releases)
├── config.example.json            # Example configuration
└── README.md                      # This file
```

## Technical Details: BLE Data Decoding

### How H510x Data Is Decoded

Govee H5101/H5102/H5104 sensors broadcast their readings in Bluetooth Low Energy (BLE) advertisements. The service captures these advertisements using `btmon` and decodes them using the GoveeWatcher algorithm.

#### Data Format

Each advertisement contains 6 bytes of manufacturer data (Company ID: 0x0001):

```
Byte Position:  [0]   [1]   [2]   [3]   [4]   [5]
Purpose:        Marker Marker  ----24-bit packed----  Battery
Example:        0x01  0x01   0x00  0xB8  0xEB    0x49
```

**Marker Bytes [0-1]:** Always `0x01 0x01` to identify H510x data

**Packed Value [2-4]:** 24-bit combined temperature and humidity value

**Battery [5]:** Direct percentage (0-100)

#### Decoding Algorithm

**Step 1: Combine bytes into 24-bit value**
```
packet_value = (byte[2] << 16) | (byte[3] << 8) | byte[4]
```

**Step 2: Decode temperature**
```
if bit 23 is set (value >= 0x800000):
    # Negative temperature (freezing)
    clear bit 23: packet_value = packet_value & 0x7FFFFF
    temperature = -((packet_value / 1000) / 10.0)
else:
    # Positive temperature
    temperature = (packet_value / 1000) / 10.0
```

**Step 3: Decode humidity**
```
# Always clear bit 23 first
packet_value = packet_value & 0x7FFFFF
humidity = (packet_value % 1000) / 10.0
```

#### Real Example

**Raw BLE data:** `01 01 00 B8 EB 49`

**Decoding steps:**
1. Marker check: `01 01` ✓ Valid H510x data
2. Combine bytes: `(0x00 << 16) | (0xB8 << 8) | 0xEB = 0x00B8EB = 47339`
3. Temperature: `(47339 / 1000) / 10.0 = 4.7°C`
4. Humidity: `(47339 % 1000) / 10.0 = 33.9%`
5. Battery: `0x49 = 73%`

**Result:** 4.7°C, 33.9% humidity, 73% battery

**Note on Humidity:** The humidity calculation shows ~15-20% lower than the Govee app. This is a known limitation of the current algorithm. Temperature and battery readings are highly accurate.

#### Freezing Temperature Example

**Raw BLE data:** `01 01 82 7A 85 3F`

**Decoding steps:**
1. Combine bytes: `(0x82 << 16) | (0x7A << 8) | 0x85 = 0x827A85 = 8551045`
2. Check bit 23: `0x827A85 >= 0x800000` ✓ Negative temperature
3. Clear sign bit: `0x827A85 & 0x7FFFFF = 0x027A85 = 162437`
4. Temperature: `-(162437 / 1000) / 10.0 = -16.2°C`
5. Humidity (with cleared bit): `(162437 % 1000) / 10.0 = 43.7%`
6. Battery: `0x3F = 63%`

**Result:** -16.2°C, 43.7% humidity, 63% battery

## Venus OS Environment

This project is designed for Venus OS's unique environment:

- **Python:** 3.12.12 (no pip, standard library only)
- **Shell:** BusyBox ash
- **Bluetooth:** BlueZ 5.72 with btmon utility
- **Init:** runit service manager
- **D-Bus:** System bus for Venus OS integration

## Known Limitations

1. **Humidity Accuracy** - ~15-20% discrepancy vs Govee app (algorithm limitation)
2. **H5101 Only** - Other models (H5075, H5074) parsers not implemented
3. **BLE Range** - Limited by Bluetooth adapter and sensor proximity

## Performance

Typical resource usage on Cerbo GX:

- **CPU:** <1% idle, ~3-5% during BLE processing
- **Memory:** 15-20 MB
- **Disk:** Up to 70 MB (log rotation @ 10MB × 7 files)
- **Network:** None (D-Bus local only)

## Updates

To update to a new version:

1. Download new release tarball
2. Transfer to Venus OS: `scp govee-ble-deploy.tar.gz root@venus.local:/tmp/`
3. Extract and run installer:
   ```bash
   cd /tmp
   tar xzf govee-ble-deploy.tar.gz
   cd govee-ble-deploy
   ./install.sh
   ```

**Automatic Backup:** The installer automatically backs up your existing installation to `/data/govee-ble.backup.YYYYMMDD_HHMMSS` before installing. The backup directory location is displayed at the end of installation.

**To restore a backup:**
```bash
svc -d /service/govee-ble
rm -rf /data/govee-ble
mv /data/govee-ble.backup.YYYYMMDD_HHMMSS /data/govee-ble
svc -u /service/govee-ble
```

Configuration files are preserved during updates (both in the backup and carried forward to the new installation).

## Development

For developers interested in contributing or extending this project:

- Development notes: `dev-notes/`
- Venus OS constraints: `dev-notes/ENVIRONMENT_NOTES.md`
- Test samples: `samples/`

## License

MIT License - See LICENSE file for details

## Credits

- **Parser Algorithm:** Based on [GoveeWatcher](https://github.com/Thrilleratplay/GoveeWatcher)
- **Venus OS Integration:** Uses Victron's `velib_python` library
- **BLE Monitoring:** BlueZ `btmon` utility

## Support

For issues, questions, or feature requests:
- Open an [Issue](../../issues) on GitHub
- Include logs: `/data/govee-ble/logs/govee_ble.log`
- Provide Venus OS version and sensor model

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.
