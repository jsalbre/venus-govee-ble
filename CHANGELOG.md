# Changelog

All notable changes to the Govee BLE Venus OS Bridge project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.2] - 2026-05-12

### Fixed

- **Missing LICENSE file** - Added MIT license (was referenced in README but missing from repo)
- **Stale `allowlist` config read** - `govee_ble_service.py` was reading a `config.get('allowlist')` key removed in v1.2.0, producing a misleading log line ("Assembler configured to filter for 0 allowlisted MACs")
- **Stale `parser_version` default** - `config_manager.py` DEFAULT_CONFIG had version `v1.0.3` instead of `v1.1.0`
- **Commented-out code** - Removed placeholder commented-out registry entries in `parser_adapter.py`
- **Garbled Unicode** - Removed encoding-corrupted characters (`âœ"`, `Â°C`, `â†'`) from `parser_adapter.py`, `config_manager.py`, and `validate_parsing_v2.py`
- **CHANGELOG cleanup** - Moved planned features from `[Unreleased]` section to the project TODO list where they belong

---

## [1.4.1] - 2026-02-09

### Fixed

#### Humidity Accuracy Documentation
- **Corrected humidity claims** - Removed all references to "~15-20% error" across docs and code. Humidity readings confirmed accurate (±3-5%).

#### Install Instructions
- **Updated for interactive add-sensor.sh** - Install script now directs users to run `add-sensor.sh` (no args) for the interactive discovery menu instead of the old log-grep workflow.
- **Updated INSTALL.txt** - Simplified sensor discovery and add-sensor instructions in the bundled INSTALL.txt.

---

## [1.4.0] - 2026-01-05

### Added

#### DeviceName D-Bus Path
- **New Read-Only Path** - Added `/DeviceName` D-Bus path
  - Contains BLE advertisement name (e.g., "GVH5105_240C")
  - Separate from `/CustomName` which is user-writable
  - Useful for identifying actual device model and MAC suffix

#### Per-Sensor Humidity Control
- **Toggle Humidity Display** - Added ability to disable/enable humidity readings per sensor
  - New config field: `humidity_enabled` (boolean, defaults to true)
  - Control via config file only (Venus OS GUI does not display custom paths)
  - When disabled: `/Humidity` path not created on service startup
  - When enabled: `/Humidity` path created and populated with readings
  - Requires service restart to apply changes
  - Humidity still parsed from BLE (always available in logs)

#### Dynamic Firmware Version
- **Track Service Version** - Firmware version now matches service version
  - Changed from hardcoded '1.0.0' to dynamic `__version__`
  - Currently shows "2.1.0" matching service version
  - Automatically updates with service releases

### Technical Implementation

#### Config Manager (src/config_manager.py)
- Added `get_humidity_enabled(mac)` method - returns bool, defaults to True
- Added `update_humidity_enabled(mac, enabled)` method - persists changes
- Updated `update_sensor()` to accept 'humidity_enabled' field

#### Temperature Service (src/govee_temperature_service.py)
- Added `humidity_enabled` parameter to constructor
- Conditional `/Humidity` path creation based on config at startup
- Safe path checks before humidity updates in `update()` method
- Config-file-only control (no D-Bus writeable path)

#### Main Service (src/govee_ble_service.py)
- Reads `humidity_enabled` from config during service creation
- Passes humidity state to temperature service constructor

### Configuration Example

```json
{
  "sensors": [
    {
      "mac": "A4:C1:38:XX:XX:XX",
      "name": "Freezer",
      "temperature_type": 6,
      "humidity_enabled": false
    }
  ]
}
```

### D-Bus Paths Added

- `/DeviceName` - BLE advertisement name (read-only)

### Backward Compatibility

- Existing configs without `humidity_enabled` default to `true`
- All sensors show humidity by default (same as v1.3.3)
- New paths are additions only (no breaking changes)

---

## [1.3.3] - 2026-01-01

### Fixed

#### Product ID Calculation Bug
- **Correct Model Number Extraction** - Fixed ProductID calculation error
  - Bug: Used full model number (5105) instead of last 3 digits (105)
  - Result: Wrong ProductIDs (0xC3F1, 0xC3ED instead of 0xB105, 0xB101)
  - Fix: Extract last 3 digits: `model[-3:]` → "H5105" becomes 105
  - Now: H5100 → 0xB100, H5101 → 0xB101, H5105 → 0xB105 ✓

#### Custom Name Priority
- **Respect User Custom Names** - Custom names now take priority over BLE names
  - Bug: BLE name (GVH5105_240C) overrode user's custom name ("Freezer")
  - Fix: Separate CustomName (user-facing) from model extraction (ProductID)
  - CustomName priority: 1) Config custom name, 2) BLE name, 3) Fallback
  - Model extraction: Always from BLE name (for accurate ProductID)

### Technical Details

**Two Separate Concerns:**
- `device_name` → CustomName field (what user sees: "Freezer", "Living Room")
- `ble_name` → Model extraction (for ProductID: "GVH5105_240C" → H5105 → 0xB105)

**Product ID Calculation:**
```python
# Before (WRONG - v1.3.2):
model_num = int(model[1:])  # "H5105" → "5105" → 5105 decimal
return 0xB000 + model_num    # 0xB000 + 5105 = 0xC3F1 ❌

# Still Wrong (v1.3.3 attempt 1):
model_num = int(model[-3:])  # "H5105" → "105" → 105 decimal
return 0xB000 + model_num     # 0xB000 + 105 = 0xB069 ❌

# Correct (v1.3.3 final):
model_num = int(model[-3:], 16)  # "H5105" → "105" → 0x105 = 261 decimal
return 0xB000 + model_num         # 0xB000 + 261 = 0xB105 ✓
```

**Result:**
- H5100 → 0xB100 (45312 decimal)
- H5101 → 0xB101 (45313 decimal)
- H5105 → 0xB105 (45317 decimal)

---

## [1.3.2] - 2026-01-01

### Fixed

#### Lazy Service Creation - Correct Model Detection
- **On-Demand Service Creation** - Services now created when first BLE advertisement is received
  - Uses real BLE advertisement name (e.g., "GVH5105_240C") instead of generated fallback
  - Ensures ProductID and ProductName are always correct (H5100 → 0xB100, H5105 → 0xB105, etc.)
  - **Fixes issue where all sensors showed as "Govee H510x" (0xB510)**
  - Previously: Services created at startup with hardcoded "GVH5101_XXXX" fallback
  - Now: Services created when sensor detected with correct model from BLE name

### Changed

#### Service Initialization
- **Startup Behavior** - Services appear 2-30 seconds after startup (when first advertisement arrives)
  - Logs configured sensors at startup
  - Clear messaging: "Waiting for BLE advertisements from N sensor(s)..."
  - Services register with correct model immediately when created
  - Matches standard Venus OS BLE device behavior

#### Logging Improvements
- Added "Creating service for MAC (GVH5105_240C)" messages
- Shows which sensors are configured vs detected
- Clear feedback when services are registered

### Technical Details

**Service Creation Flow:**
1. Startup: Log configured sensor MACs, don't create services
2. First advertisement: Create service with real BLE name
3. Extract model from BLE name: "GVH5105_240C" → "H5105"
4. Set correct ProductID (0xB105) and ProductName ("Govee H5105")
5. Register on D-Bus with accurate model info

**Benefits:**
- ✓ Always shows correct model in Venus OS UI
- ✓ Correct ProductID in VRM Portal from first data point
- ✓ No model misidentification
- ✓ Simpler code - one service creation path

**Trade-off:**
- Services appear when sensor detected (2-30 sec delay) vs immediately at startup
- This is standard behavior for BLE devices in Venus OS

---

## [1.3.1] - 2026-01-01

### Fixed

#### Model-Specific Product Display
- **Dynamic Product ID & Name** - Sensors now display with correct model information in Venus OS UI
  - H5100 sensors show as "Govee H5100" (Product ID: 0xB100)
  - H5105 sensors show as "Govee H5105" (Product ID: 0xB105)
  - H5101/02/04 show with correct model names (Product IDs: 0xB101/02/04)
  - Previously all sensors incorrectly showed as "Govee H5101"

#### Script Output Cleanup
- **add-sensor.sh** - Removed ANSI color codes that displayed literally on Venus OS
  - Clean output without escape sequences (`\033[0;34m`, etc.)
  - Added H5105 example to usage documentation
  - Better compatibility with BusyBox ash shell

### Changed

#### Service Version
- Updated `govee_temperature_service.py` version: 2.0.0 → 2.1.0
- Added model extraction and product ID generation methods

### Technical Details

**Product ID Mapping:**
- H5100 → 0xB100 (45312 decimal)
- H5101 → 0xB101 (45313 decimal)
- H5102 → 0xB102 (45314 decimal)
- H5104 → 0xB104 (45316 decimal)
- H5105 → 0xB105 (45317 decimal)
- Unknown model → 0xB510 (46352 decimal, generic H510x)

**Model Detection:**
- Extracts model from device name (e.g., "GVH5105_240C" → "H5105")
- Sets ProductName dynamically (e.g., "Govee H5105")
- Falls back to "Govee H510x" for unrecognized names

---

## [1.3.0] - 2025-12-31

### Added

#### New Sensor Support
- **H5100** - Added parser support for H5100 sensors (static random BLE addresses)
- **H5105** - Added parser support for H5105 sensors (static random BLE addresses)

#### Improved Discovery
- **Automatic Sensor Discovery** - Service now logs discovered Govee sensors not in configuration
  - Example: `Discovered Govee sensor not in sensors: D1:30:38:36:24:0C (GVH5105_240C) - Add to config.json sensors array to monitor`
  - Helps users find new sensors without separate discovery tools

### Changed

#### BLE Address Filtering
- **Name-Based Filtering** - Replaced OUI-based filtering (A4:C1:38) with Govee name pattern matching (GVH\d+)
  - Now compatible with both LE_PUBLIC addresses (H5101/02/04) and LE_RANDOM static addresses (H5100/05)
  - Filters by device name pattern before parsing manufacturer data (improved performance)
  - Rejects non-Govee devices early, reducing unnecessary processing

#### Parser Version
- Updated parser version: `local_h510x_v1.1.0_h5100_h5105_support`

### Technical Details

**BLE Address Type Support:**
- H5100/H5105 use static random BLE addresses (starting with C or D prefixes)
- H5101/H5102/H5104 use public BLE addresses (Govee OUI A4:C1:38)
- Both address types now fully supported via name-pattern filtering

**Performance:**
- Early rejection: Non-Govee devices rejected after name field (before parsing manufacturer data)
- Only parses 2 lines (Address, Name) before rejecting non-Govee advertisements

---

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
| Humidity | ±3-5% |

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

1. **Model Support** - Only H510x family currently supported
   - H5075, H5074, B5178 parsers not implemented
   - Easy to extend by adding new parser functions

2. **BLE Range** - Limited by Bluetooth adapter capabilities
   - Typical range: 10-30 meters line of sight
   - Metal/concrete walls significantly reduce range

### Documentation

- **README.md** - Production-ready user guide

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
