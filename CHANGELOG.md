# Changelog

All notable changes to the Govee BLE Venus OS Bridge project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
**Links:** [1.0.0] = https://github.com/yourusername/govee-ble-venus-py/releases/tag/v1.0.0
