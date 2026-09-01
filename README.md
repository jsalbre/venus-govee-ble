# Govee BLE Venus OS Bridge

**Version:** 1.5.0
**Status:** Production Ready

Python bridge for integrating Govee H510x Bluetooth temperature/humidity sensors with Victron Energy Venus OS.

## Overview

This project enables Victron Cerbo GX devices to monitor Govee H5100/H5101/H5102/H5104/H5105 temperature and humidity sensors via Bluetooth Low Energy (BLE). Sensor readings appear natively in Venus OS as `com.victronenergy.temperature` services, making them available in:

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
- **Sensors** - Govee H5100, H5101, H5102, H5104, or H5105

## Supported Sensors

| Model | Status | Notes |
|-------|--------|-------|
| **H5100** | ✓ Compatible | Same protocol as H5101, uses static random BLE address |
| **H5101** | ✓ Tested | Primary support, refrigerator/freezer monitoring |
| **H5102** | ✓ Compatible | Same protocol as H5101 |
| **H5104** | ✓ Compatible | Same protocol as H5101 |
| **H5105** | ✓ Compatible | Same protocol as H5101, uses static random BLE address |
| H5075, H5074 | ⚠ Untested | May work, parser not implemented |

## Sensor Accuracy

Based on validation against Govee mobile app:

| Metric | Accuracy | Notes |
|--------|----------|-------|
| **Temperature** | ±0.5°C | Excellent |
| **Battery** | Exact | 100% match |
| **Humidity** | ±3-5% | Good |
| **RSSI** | Real-time | Signal strength |

## Installation (Cerbo GX)

This package installs via Victron's community [SetupHelper](https://github.com/kwindrem/SetupHelper) framework. If SetupHelper isn't already installed:

```bash
wget -qO - https://github.com/kwindrem/SetupHelper/archive/latest.tar.gz | tar -xzf - -C /data
rm -rf /data/SetupHelper
mv /data/SetupHelper-latest /data/SetupHelper
/data/SetupHelper/setup
```

Then install this package:

```bash
mkdir -p /tmp/venus-govee-ble-download /data/venus-govee-ble
wget -qO /tmp/venus-govee-ble-download/archive.tar.gz https://github.com/jsalbre/venus-govee-ble/archive/main.tar.gz
tar xzf /tmp/venus-govee-ble-download/archive.tar.gz -C /tmp/venus-govee-ble-download
mv /tmp/venus-govee-ble-download/venus-govee-ble-*/* /data/venus-govee-ble/
/data/venus-govee-ble/setup install auto
```

**Upgrading from the old (pre-1.5.0) manual installer?** `setup install auto` detects the previous `/data/govee-ble` install automatically, migrates `config.json` and `discovered_sensors.json` into the new location, and removes every remnant of the old install (old service, old `/data/rc.local` boot hook, old install directory, and any timestamped backups) — no manual cleanup needed.

### Updating

Once installed, PackageManager's GitHub auto-update will pick up new releases. To update manually:

```bash
mkdir -p /tmp/venus-govee-ble-download
wget -qO /tmp/venus-govee-ble-download/archive.tar.gz https://github.com/jsalbre/venus-govee-ble/archive/main.tar.gz
tar xzf /tmp/venus-govee-ble-download/archive.tar.gz -C /tmp/venus-govee-ble-download
mv /tmp/venus-govee-ble-download/venus-govee-ble-*/* /data/venus-govee-ble/
/data/venus-govee-ble/setup install auto
```

`setup install auto` diffs the service run file and restarts the service itself — never manually `svc -d`/`svc -u` around an update. Configuration lives under `/data/setupOptions/venus-govee-ble/`, which persists across updates.

### Uninstalling

```bash
/data/venus-govee-ble/setup uninstall
```

### Add Sensors

**Important:** Govee H510x sensors do NOT display MAC addresses on the device or in the Govee app. The service discovers them automatically via BLE.

Once the service is running (it starts automatically after install), use the interactive helper to add sensors:

```bash
/data/venus-govee-ble/add-sensor.sh
```

The menu shows sensors the service has discovered but aren't yet configured. You can:
- **Select a discovered sensor** — choose by number, set name and type
- **Scan** — run a BLE scan to find sensors not yet discovered
- **Manual entry** — enter a MAC address directly

**Temperature Types:** 0=Battery, 1=Fridge, 2=Generic, 3=Room, 4=Outdoor, 5=Water heater, 6=Freezer

**Alternative:** Edit `/data/setupOptions/venus-govee-ble/config.json` directly (see Configuration section below).

### Verify

```bash
# Check logs
tail -f /data/setupOptions/venus-govee-ble/logs/govee_ble.log
```

Verify in Venus OS GUI:
- **Settings → Temperature sensors** - Sensors appear here
- **Device list** - Shows live readings
- **VRM Portal** - Historical data (after 15 minutes)

## Configuration

The service is configured via `/data/setupOptions/venus-govee-ble/config.json`:

```json
{
  "sensors": [
    {
      "mac": "A4:C1:38:XX:XX:XX",
      "name": "Custom Name",
      "temperature_type": 1,
      "device_instance": null,
      "humidity_enabled": true
    }
  ],
  "temperature_type_default": 2,
  "log_level": "INFO",
  "log_path": "/data/setupOptions/venus-govee-ble/logs/govee_ble.log",
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
| `humidity_enabled` | bool | No | Show humidity readings (defaults to `true`). Config-file only, requires service restart to apply. |

**Example:**
```json
{
  "mac": "A4:C1:38:XX:XX:XX",
  "name": "Freezer",
  "temperature_type": 6,
  "humidity_enabled": true
}
```

## Service Management

```bash
# Check status
svstat /service/venus-govee-ble

# Restart service
svc -t /service/venus-govee-ble

# Stop service
svc -d /service/venus-govee-ble

# Start service
svc -u /service/venus-govee-ble

# View logs
tail -f /data/setupOptions/venus-govee-ble/logs/govee_ble.log
```

## Troubleshooting

### Sensors Not Appearing

1. Check logs for discovered sensors: `tail -f /data/setupOptions/venus-govee-ble/logs/govee_ble.log`
2. Verify MAC addresses in sensors array (must be uppercase): `cat /data/setupOptions/venus-govee-ble/config.json`
3. Ensure sensors have fresh batteries and are within range (10-30m)
4. Check service is running: `svstat /service/venus-govee-ble`

### Service Won't Start

```bash
# Check logs for errors
tail -n 50 /data/setupOptions/venus-govee-ble/logs/govee_ble.log

# Verify btmon is working
btmon -T | head -n 20

# Test Python imports
python3 -c "import sys; sys.path.insert(1, '/data/venus-govee-ble/ext/velib_python'); from vedbus import VeDbusService; print('OK')"
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
venus-govee-ble/
├── src/                           # Source code
│   ├── _version.py                # Reads the root `version` file
│   ├── govee_ble_service.py       # Main service orchestrator
│   ├── govee_temperature_service.py # D-Bus temperature service
│   ├── parser_adapter.py          # BLE advertisement parser
│   ├── btmon_reader.py            # btmon process manager
│   ├── config_manager.py          # Configuration management
│   └── validate_parsing_v2.py     # Validation tool
├── services/                      # SetupHelper runit service files
│   └── venus-govee-ble/{run,log/run}
├── ext/                           # Dependencies
│   └── velib_python/              # Victron Venus library (vendored)
├── config.example.json            # Example configuration
├── setup                          # SetupHelper install/uninstall script
├── version, gitHubInfo            # SetupHelper package metadata
├── add-sensor.sh                  # Sensor configuration helper
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
- **Shell:** bash (BusyBox utilities)
- **Bluetooth:** BlueZ 5.72 with btmon utility
- **Init:** runit service manager
- **D-Bus:** System bus for Venus OS integration
- **Packaging:** SetupHelper, with PackageManager auto-update

## Known Limitations

1. **Model Support** - Only H510x family currently supported (H5075, H5074, B5178 parsers not implemented)
2. **BLE Range** - Limited by Bluetooth adapter and sensor proximity

## Performance

Typical resource usage on Cerbo GX:

- **CPU:** <1% idle, ~3-5% during BLE processing
- **Memory:** 15-20 MB
- **Disk:** Up to 70 MB (log rotation @ 10MB × 7 files)
- **Network:** None (D-Bus local only)

## License

MIT License - See LICENSE file for details

## Credits

- **Parser Algorithm:** Based on [GoveeWatcher](https://github.com/Thrilleratplay/GoveeWatcher)
- **Venus OS Integration:** Uses Victron's `velib_python` library
- **BLE Monitoring:** BlueZ `btmon` utility

## Support

For issues, questions, or feature requests:
- Open an [Issue](../../issues) on GitHub
- Include logs: `/data/setupOptions/venus-govee-ble/logs/govee_ble.log`
- Provide Venus OS version and sensor model

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.
