# Govee BLE Venus OS Bridge

**Version:** 1.0.0
**Status:** Production Ready

Python bridge for integrating Govee H510x Bluetooth temperature/humidity sensors with Victron Energy Venus OS.

## Overview

This project enables Victron Cerbo GX devices to monitor Govee H5101/H5102/H5104 temperature and humidity sensors via Bluetooth Low Energy (BLE). Sensor readings appear natively in Venus OS as `com.victronenergy.temperature` services, making them available in:

- Remote Console / Local display
- VRM Portal dashboards
- Node-RED flows
- Victron apps (VictronConnect, VRM)

## Features

- **Automatic Discovery** - Detects and monitors allowlisted Govee sensors
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

Use the discovery tool:

```bash
/data/govee-ble/find-sensors.sh
```

This scans for 30 seconds and displays:
- MAC addresses (needed for config)
- Device names
- Example configuration JSON

### 4. Configure

Add discovered MAC addresses to config:

```bash
vi /data/govee-ble/config.json
```

Example (from find-sensors.sh output):

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
    "A4:C1:38:8E:0D:AF": 6,
    "A4:C1:38:B8:DF:A1": 1
  }
}
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
  "allowlist": ["MAC1", "MAC2"],
  "names": {
    "MAC1": "Custom Name"
  },
  "temperature_type": {
    "MAC1": 1
  },
  "temperature_type_default": 2,
  "log_level": "INFO",
  "log_path": "/data/govee-ble/logs/govee_ble.log",
  "stale_threshold_sec": 120,
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
| `allowlist` | array | MAC addresses to monitor (uppercase) |
| `names` | object | Custom display names per MAC |
| `temperature_type` | object | Temperature type override per MAC |
| `temperature_type_default` | int | Default type for new sensors (0-6) |
| `log_level` | string | Logging level: DEBUG, INFO, WARNING, ERROR |
| `stale_threshold_sec` | int | Seconds before sensor marked disconnected |

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

1. Check allowlist: `cat /data/govee-ble/config.json`
2. Verify MAC addresses (must be uppercase)
3. Check sensors are advertising: `btmon -T | grep -i gvh`
4. Review logs: `tail -n 100 /data/govee-ble/logs/govee_ble.log`

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
  --dest=com.victronenergy.temperature.govee_0daf \
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
2. Stop service: `svc -d /service/govee-ble`
3. Extract new files over existing installation
4. Review changelog for config changes
5. Start service: `svc -u /service/govee-ble`

Configuration files are preserved during updates.

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
