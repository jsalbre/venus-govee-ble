# Changelog

All notable changes to the Govee BLE Venus OS Bridge project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-12-04

### ⚠️ BREAKING CHANGE

**Configuration File Format Changed**

The config.json structure has been simplified to eliminate MAC address repetition. This is a **breaking change** requiring reconfiguration.

#### Old Format (v1.1.0):
```json
{
  "allowlist": ["A4:C1:38:XX:XX:XX"],
  "names": {"A4:C1:38:XX:XX:XX": "Freezer"},
  "temperature_type": {"A4:C1:38:XX:XX:XX": 6},
  "device_instances": {"A4:C1:38:XX:XX:XX": 450}
}
```

#### New Format (v1.2.0):
```json
{
  "sensors": [
    {
      "mac": "A4:C1:38:XX:XX:XX",
      "name": "Freezer",
      "temperature_type": 6,
      "device_instance": 450
    }
  ]
}
```

### Changed

#### Configuration Structure
- **Sensors Array** - Consolidated `allowlist`, `names`, `temperature_type`, and `device_instances` into single `sensors` array
- **DRY Principle** - Each MAC address now appears only once instead of 4 times
- **Clearer Structure** - All sensor properties grouped together in single object
- **Easier Maintenance** - Add/remove sensors by adding/removing array elements

#### ConfigManager API
- **Added Methods**: `add_sensor()`, `remove_sensor()`, `get_sensors()`, `update_sensor()`
- **Updated Methods**: All getter methods now search sensors array
- **Removed Methods**: `update_allowlist()`, `remove_from_allowlist()`, `get_allowlist()`, `update_device_instances()`

#### Scripts & Tools
- **add-sensor.sh** - Rewritten to work with sensors array, now updates existing sensors
- **install.sh** - Updated sensor count detection to use sensors array

#### Service Behavior
- **Device Instances** - Now persisted per-sensor in config (auto-assigned on first run)
- **Discovery Logs** - Updated messages to reference "sensors array" instead of "allowlist"

### Migration Notes

**No automatic migration provided.** This release requires fresh configuration:

1. **Backup existing config** - Installer automatically backs up to `/data/govee-ble.backup.YYYYMMDD_HHMMSS`
2. **Fresh install** - Extract v1.2.0 tarball and run `./install.sh`
3. **Add sensors** - Use `/data/govee-ble/add-sensor.sh MAC [name] [type]` for each sensor
4. **Restart service** - `svc -t /service/govee-ble`

Device instances will be automatically calculated and persisted.

---

## [1.1.0] - 2025-11-24

### Fixed

#### Installation & Deployment
- **Automatic Backup** - Installer now backs up existing installation to `/data/govee-ble.backup.YYYYMMDD_HHMMSS` before updating
- **Service Stop Sequence** - Service properly stopped before file updates to prevent file-in-use issues
- **Sensor Count Detection** - Fixed false positive sensor counts using Python JSON parsing instead of regex
- **Boot Persistence** - Service now properly persists across reboots via /data storage and rc.local

#### Helper Scripts
- **add-sensor.sh** - Fixed ANSI color codes printing literally by removing bash variables from Python output
- **add-sensor.sh** - Anonymized MAC addresses in usage examples
- **Removed find-sensors.sh** - Replaced with automatic discovery via service logs (simpler, more reliable)

#### Configuration
- **Stale Threshold** - Increased from 120s to 300s for better sensor reliability
- **Device ID Range** - Changed from 0-99 to 400-499 to avoid conflicts with other Venus OS devices

#### Documentation
- **README.md** - Added BLE data decoding formulas with real examples
- **README.md** - Removed all find-sensors.sh references, updated discovery method
- **docs/INSTALL.md** - Corrected sensor discovery instructions (Govee app doesn't show MACs)
- **All files** - Anonymized MAC addresses (kept OUI A4:C1:38)
- **All files** - Updated GitHub username from placeholder to jsalbre

### Changed
- **Discovery Method** - Users now monitor service logs instead of running separate discovery script
- **Build System** - Moved from /tmp to local build/ and dist/ directories

## [1.0.0] - 2025-11-24

### 🎉 Initial Production Release

First stable release of the Govee BLE Venus OS Bridge. Full integration with Venus OS D-Bus system for monitoring Govee H510x temperature/humidity sensors.

### Added

#### Core Features
- **BLE Advertisement Parsing** - Decodes Govee H5101/H5102/H5104 sensor data from btmon
- **D-Bus Integration** - Publishes sensors as `com.victronenergy.temperature` services
- **Automatic Discovery** - Monitors allowlisted MAC addresses
- **Real-time Monitoring** - Temperature, humidity, battery level, and RSSI
- **Sensor Health Tracking** - Stale detection and automatic reconnection
- **Native Venus OS Integration** - Appears in Remote Console, VRM Portal, and device list

#### Configuration Management
- Thread-safe configuration file handling with file locking
- Atomic writes to prevent corruption
- Persistent storage of GUI changes (custom names, temperature types)
- Example configuration template (`config.example.json`)
- Support for per-sensor temperature type overrides

#### Service Management
- Runit service integration for automatic startup
- Exponential backoff for error recovery (30s-300s)
- Watchdog for btmon process monitoring
- Graceful shutdown handling (SIGTERM/SIGINT)
- Log rotation (10MB × 7 files = 70MB max)

#### Venus OS Integration
- Custom name persistence from Venus OS GUI
- Temperature type selection (Battery, Fridge, Generic, Room, Outdoor, Water Heater, Freezer)
- Device instance calculation from MAC address
- Connection status reporting (Connected/Disconnected)
- Timestamp tracking for last update

### Sensor Support

- **H5101** - Fully tested and validated
- **H5102** - Compatible (same protocol as H5101)
- **H5104** - Compatible (same protocol as H5101)

### Validated Performance

Based on extensive testing against Govee mobile app:

| Metric | Accuracy |
|--------|----------|
| Temperature | ±0.5°C |
| Battery | Exact match |
| Humidity | ~15-20% error (known limitation) |

### Technical Implementation

- **Parser Version:** `local_h510x_v1.0.3_humidity_fix`
- **Python:** 3.12.12 (Venus OS standard library only)
- **Dependencies:** Victron velib_python (included)
- **BLE:** BlueZ 5.72 btmon utility
- **Process Management:** Runit

### Fixed

- **Config Persistence** - Venus OS GUI changes now properly save to `config.json`
- **UTF-8 Encoding** - Removed special characters causing log display artifacts
- **AttributeError** - Fixed incorrect ConfigManager API usage in save callbacks
- **Humidity Decoding** - Sign bit handling in humidity calculation
- **MAC Address Filtering** - Pre-filtering in btmon reader for efficiency
- **btmon Pattern Matching** - Corrected `0x3e` hex pattern handling

### Known Limitations

1. **Humidity Accuracy** - Shows ~15-20% discrepancy compared to Govee mobile app
   - Using GoveeWatcher algorithm
   - Temperature (primary metric) is accurate
   - Proceeding as acceptable for most use cases

2. **Model Support** - Only H510x family currently supported
   - H5075, H5074, B5178 parsers not implemented
   - Easy to extend by adding new parser functions

3. **BLE Range** - Limited by Bluetooth adapter capabilities
   - Typical range: 10-30 meters line of sight
   - Metal/concrete walls significantly reduce range

### Documentation

- **README.md** - Production-ready user guide
- **docs/INSTALL.md** - Detailed installation instructions
- **docs/DEPLOYMENT.md** - Deployment and troubleshooting guide
- **dev-notes/** - Development notes and context (not in releases)

### Security

- Configuration file uses exclusive file locking (fcntl.flock)
- Atomic writes via temp file + rename pattern
- No external dependencies or network access
- Runs with Venus OS system permissions

### Performance

Measured on Victron Cerbo GX:

- **CPU Usage:** <1% idle, 3-5% during BLE processing
- **Memory:** 15-20 MB resident
- **Disk:** 70 MB maximum (rotating logs)
- **Startup Time:** <5 seconds
- **Update Latency:** <1 second from advertisement to D-Bus

### Deployment

- **Installation:** Single tarball extraction + service enable
- **Configuration:** JSON file with MAC allowlist
- **Updates:** Stop service → replace files → restart
- **Rollback:** Replace files with previous version

## [Unreleased]

### Planned Features

- Support for additional Govee models (H5075, H5074, B5178)
- Improved humidity decoding algorithm
- Configuration GUI/web interface
- Historical data export
- Bluetooth adapter failover
- Multi-adapter support

---

## Release Notes

### v1.0.0 Highlights

This release marks the completion of full Venus OS integration. All core features have been implemented and validated:

✅ Accurate temperature readings (±0.5°C)
✅ Native Venus OS GUI integration
✅ Persistent configuration
✅ Robust error handling and recovery
✅ Production-ready stability

The service has been successfully deployed and tested on a Victron Cerbo GX monitoring refrigerator and freezer sensors with excellent reliability.

### Migration Guide

This is the initial release. For users deploying for the first time:

1. Download `govee-ble-deploy.tar.gz` from releases
2. Follow `INSTALL.txt` instructions
3. Configure sensors in `/data/govee-ble/config.json`
4. Service starts automatically via runit

### Breaking Changes

None (initial release)

### Deprecations

None (initial release)

---

**Format:** [Version] - YYYY-MM-DD
**Links:** [1.0.0] = https://github.com/jsalbre/govee-ble-venus-py/releases/tag/v1.0.0
