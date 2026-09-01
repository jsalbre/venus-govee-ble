# Architecture

**Version:** 1.1 | **Updated:** 2026-09-01

**Project:** Govee BLE Venus OS Bridge
**GitHub:** jsalbre/venus-govee-ble (public)

See `Development/environment-notes/venus-os-cerbo-gx.md` for generic Venus
OS/Cerbo GX platform facts (BusyBox constraints, Python stdlib limits,
D-Bus conventions, SetupHelper packaging mechanics, runit service
management) — this document covers only what's specific to this project.

---

## Overview

Govee H510x BLE temperature/humidity sensor bridge for Victron Venus OS (Cerbo GX). Reads BLE advertisements from Govee sensors via btmon, parses temperature/humidity/battery data, and publishes readings to the Venus OS D-Bus as `com.victronenergy.temperature` services. Sensors appear natively in the Venus OS GUI, Remote Console, and VRM Portal.

---

## Source Files

| File | Description |
|------|-------------|
| `src/_version.py` | Reads the root `version` file at import time |
| `src/govee_ble_service.py` | Main orchestrator daemon |
| `src/govee_temperature_service.py` | D-Bus service per sensor |
| `src/parser_adapter.py` | BLE advertisement parser |
| `src/btmon_reader.py` | btmon process manager with watchdog |
| `src/config_manager.py` | Thread-safe config with atomic writes |
| `src/validate_parsing_v2.py` | Parsing validation tool |

---

## Design Decisions

### Sensors Array Config (v1.2.0+)

Replaced separate `allowlist`, `names`, `temperature_type`, and `device_instances` dicts with a single `sensors` array. Each sensor object contains all its properties. This was a breaking change from the v1.1.0 format. The old format required each MAC address to appear in 4 separate dictionaries.

### Lazy Service Creation

D-Bus services are created on first BLE advertisement, not at startup. This ensures accurate model detection from the real BLE name rather than using fallback values. Without this, all sensors showed as "Govee H510x" with incorrect ProductIDs. Services appear 2-30 seconds after startup, which matches standard Venus OS BLE device behavior.

### Private D-Bus Connections

Each sensor uses `dbus.SystemBus(private=True)` to get its own connection. The default `dbus.SystemBus()` returns a singleton, and multiple sensors registering root path handlers on the same connection causes `KeyError: "Can't register the object-path handler for '/'"`.

### Name-Based BLE Filtering

Replaced OUI-based MAC prefix filtering (A4:C1:38) with Govee device name pattern matching (GVH\d+). This was required when H5100/H5105 support was added because those models use LE_RANDOM static addresses with unpredictable prefixes, unlike H5101/02/04 which use LE_PUBLIC addresses with Govee's OUI.

### ProductID Formula

```python
product_id = 0xB000 + int(model[-3:], 16)
```

The last 3 characters of the model number are parsed as **hexadecimal**. Example: GVH5105 -> H5105 -> "105" -> 0x105 = 261 -> 0xB000 + 261 = 0xB105. An earlier bug used decimal parsing, producing wrong IDs (e.g., 0xB069 instead of 0xB105).

### Config Persistence via D-Bus

Venus OS GUI changes to CustomName and TemperatureType are persisted back to config.json via D-Bus write callbacks. Device instances are auto-assigned on first advertisement and persisted per sensor.

### Humidity Control

Venus OS GUI cannot display custom D-Bus paths (hardcoded QML files). Humidity toggle is config-file-only via `humidity_enabled` boolean per sensor. When disabled, the `/Humidity` D-Bus path is not created at startup. Service restart required to apply changes.

### Auto-Discovery (v1.4.0+)

The service writes discovered unconfigured Govee MACs to `discovered_sensors.json` as a `{MAC: BLE_name}` dict. On startup, the file is loaded and pruned of any MACs now present in the `sensors` config array. At runtime, each new unconfigured Govee advertisement adds the MAC to the file (once per MAC). The `add-sensor.sh` interactive menu reads this file to present discovered sensors for selection. When a sensor is added to config via `add-sensor.sh`, it removes the entry from `discovered_sensors.json`.

### SetupHelper Packaging (v1.5.0+)

Replaced the bespoke `install.sh` (manual runit symlink + `/data/rc.local` boot hook) with Victron's community SetupHelper framework — see `Development/environment-notes/venus-os-cerbo-gx.md` for the general mechanism. Persistent state (`config.json`, `discovered_sensors.json`, `logs/`) lives under `/data/setupOptions/venus-govee-ble/` rather than `/data/venus-govee-ble/` itself, since SetupHelper replaces the entire package directory on every update. `ext/velib_python` is vendored as plain committed files rather than a git submodule, since PackageManager installs via a bare GitHub branch archive, which never includes submodule content.

---

## Configuration Format

Current format (v1.2.0+):

```json
{
  "sensors": [
    {
      "mac": "A4:C1:38:XX:XX:XX",
      "name": "Freezer",
      "temperature_type": 6,
      "device_instance": 403,
      "humidity_enabled": true
    }
  ],
  "ble_interface": "hci0",
  "log_level": "INFO",
  "log_path": "/data/setupOptions/venus-govee-ble/logs/govee_ble.log",
  "stale_threshold_sec": 300,
  "restart_min_delay_sec": 30,
  "restart_max_delay_sec": 300,
  "battery": {
    "low_alarm_threshold_pct": 15.0
  },
  "temperature_type_default": 2,
  "parser_version": "local_h510x_v1.1.0_h5100_h5105_support"
}
```

**Temperature types:** 0=Battery, 1=Fridge, 2=Generic, 3=Room, 4=Outdoor, 5=Water heater, 6=Freezer

### ConfigManager API

Key methods for sensor management:

- `add_sensor(mac, name, temperature_type)` - Add sensor (idempotent)
- `remove_sensor(mac)` - Remove sensor
- `get_sensors()` - Get all sensors
- `update_sensor(mac, **kwargs)` - Update sensor properties
- `is_allowed(mac)` - Check if MAC is in sensors array
- `get_device_name(mac)` - Get custom name
- `get_device_instance(mac)` - Get instance number
- `get_temperature_type(mac)` - Get type with fallback to default
- `get_humidity_enabled(mac)` - Get humidity toggle (defaults True)

---

## D-Bus Service Structure

**Service name pattern:** `com.victronenergy.temperature.govee_<last4_mac_hex>`
**Example:** `com.victronenergy.temperature.govee_0daf`

| Path | Type | Description |
|------|------|-------------|
| `/Temperature` | float | Temperature in Celsius |
| `/Humidity` | float | Relative humidity % (conditional on humidity_enabled) |
| `/Status` | int | 0=Ok, 1=Disconnected |
| `/Connected` | int | 1=connected, 0=disconnected |
| `/TemperatureType` | int | See temperature types above (writable, persisted) |
| `/CustomName` | string | User-configurable name (writable, persisted) |
| `/DeviceName` | string | BLE advertisement name (read-only) |
| `/DeviceInstance` | int | Unique instance number (400-499 range) |
| `/ProductId` | int | 0xB000 + model suffix (e.g., 0xB105 for H5105) |
| `/ProductName` | string | "Govee H5105" (dynamic from BLE name) |
| `/FirmwareVersion` | string | Project version from `_version.py` |
| `/Mgmt/ProcessName` | string | "govee_ble_service" |
| `/Mgmt/ProcessVersion` | string | Project version from `_version.py` |
| `/Mgmt/Connection` | string | "Bluetooth LE" |

Note: the D-Bus service name is keyed off the MAC address, not the package
name — it is unaffected by the `govee-ble-venus-py` -> `venus-govee-ble`
rename, so existing devices keep their identity (VRM widget positions,
custom names) across the migration.

### Service Behavior

- **Stale detection:** Sensor marked Disconnected after 300 seconds without advertisement
- **Reconnection:** Automatic when advertisements resume
- **Error recovery:** Exponential backoff for btmon restarts (30s -> 300s cap)
- **Backoff reset:** After 1 hour of successful operation
- **Log rotation:** 10MB per file, 7 files max (~70MB total)
- **BLE rate:** Govee sensors advertise every 2-3 seconds

---

## BLE Advertisement Format

**Company ID:** 1 (Nokia Mobile Phones - used by Govee)

**Manufacturer data (6 bytes):**

```
Byte 0:    01 (marker)
Byte 1:    01 (sub-type)
Bytes 2-4: Temperature and humidity (24-bit packed)
Byte 5:    Battery (0-100)
```

**Temperature decoding:** Signed 16-bit value / 39 = Celsius
**Humidity decoding:** GoveeWatcher algorithm (values > 100 are divided by 2)

### btmon Event Detection

btmon truncates event names after event #10. Always match on the hex code, never the event name:

```python
# Correct - matches regardless of truncation
HCI_EVENT_PATTERN = re.compile(r'> HCI Event:.*\(0x3e\).*\[hci0\]')

# Wrong - fails after event #10 when name truncates
HCI_EVENT_PATTERN = re.compile(r'> HCI Event: LE Meta Event.*\[hci0\]')
```

---

## Supported Models

| Model | Address Type | Status |
|-------|-------------|--------|
| H5100 | LE_RANDOM static | Supported (v1.3.0+) |
| H5101 | LE_PUBLIC (A4:C1:38) | Supported (v1.0.0+) |
| H5102 | LE_PUBLIC (A4:C1:38) | Supported (v1.0.0+) |
| H5104 | LE_PUBLIC (A4:C1:38) | Supported (v1.0.0+) |
| H5105 | LE_RANDOM static | Supported (v1.3.0+) |
| H5075 | Unknown | Not implemented (different encoding) |
| H5074 | Unknown | Not implemented (different encoding) |
| B5178 | Unknown | Not implemented (different encoding) |

All supported models share the H510x parser.

---

## Known Limitations

- **Model support:** Only H510x family. Other models use different encoding.
- **Venus OS GUI:** Cannot display custom D-Bus paths. Humidity toggle is config-file-only.
- **BLE range:** 10-30 meters line of sight. Metal/concrete walls reduce range.
- **Config changes:** Humidity toggle requires service restart. CustomName and TemperatureType persist via D-Bus in real time.

---

## File Structure

```
/data/venus-govee-ble/                     # SetupHelper package directory (replaced on every update)
  setup                                    # SetupHelper install/uninstall script
  version, gitHubInfo                      # SetupHelper package metadata
  src/                                     # Source code
  ext/velib_python/                        # Victron D-Bus library (vendored, not a submodule)
  services/venus-govee-ble/run             # Runit service script
  add-sensor.sh                            # Sensor management helper

/data/setupOptions/venus-govee-ble/        # Persistent state (survives package updates)
  config.json                              # Active configuration
  discovered_sensors.json                  # Auto-discovered unconfigured sensors
  logs/                                    # Rotating log files

~/iCloud-Dev/venus-govee-ble/              # Development (iCloud-synced)
  src/                                     # Source (same as above)
  samples/                                 # Private (gitignored)
```

### Privacy Separation

**Gitignored (private, synced via iCloud only):**
- `samples/` - Raw BLE data, btmon captures (contain MAC addresses)

**Git-tracked (public, pushed to GitHub):**
- `src/`, `README.md`, `CHANGELOG.md`, `ARCHITECTURE.md`, `TODO.md`, `PROJECT.md`, `config.example.json`, etc.

---

## Quick Reference

### Service Management

```bash
svstat /service/venus-govee-ble           # Check status
svc -t /service/venus-govee-ble           # Restart
svc -d /service/venus-govee-ble           # Stop
svc -u /service/venus-govee-ble           # Start
tail -f /data/setupOptions/venus-govee-ble/logs/govee_ble.log  # Follow logs
```

### D-Bus Inspection

```bash
# List Govee services
dbus-send --system --print-reply \
  --dest=org.freedesktop.DBus /org/freedesktop/DBus \
  org.freedesktop.DBus.ListNames | grep govee

# Read temperature
dbus-send --system --print-reply \
  --dest=com.victronenergy.temperature.govee_0daf \
  /Temperature com.victronenergy.BusItem.GetValue
```

### Deployment

```bash
mkdir -p /tmp/venus-govee-ble-download /data/venus-govee-ble
wget -qO /tmp/venus-govee-ble-download/archive.tar.gz https://github.com/jsalbre/venus-govee-ble/archive/main.tar.gz
tar xzf /tmp/venus-govee-ble-download/archive.tar.gz -C /tmp/venus-govee-ble-download
mv /tmp/venus-govee-ble-download/venus-govee-ble-*/* /data/venus-govee-ble/
/data/venus-govee-ble/setup install auto
```

---

## Release Workflow

### Version Bumping

The root `version` file is the single source of truth — `src/_version.py`
reads it at import time. Update:

1. `version` — bump the version string
2. `README.md` — Version metadata line (docs, not read programmatically)
3. `CHANGELOG.md` — add an entry

### Build and Release

1. Bump version, add CHANGELOG.md entry
2. Commit, tag (`git tag vX.Y.Z`), push

No build/packaging step — SetupHelper's PackageManager downloads the bare
GitHub branch archive directly.
