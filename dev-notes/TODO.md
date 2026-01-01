# Future Development TODO

## Planned Features & Improvements

### High Priority

No high priority items at this time.

---

### Medium Priority

#### Additional Sensor Models
**Status:** Not started
**Priority:** Medium
**Estimated Effort:** Medium

Add parser support for:
- H5075 (different encoding)
- H5074 (different encoding)
- B5178 (different encoding)

**Implementation:**
- Research encoding formats for each model
- Add parser functions to parser_adapter.py
- Update PARSER_REGISTRY
- Test with real devices
- Update documentation

---

### Low Priority

No low priority items at this time.

---

## Completed Items

### v1.3.3
- ✅ Fixed ProductID calculation (parse model suffix as hexadecimal)
- ✅ Separated CustomName from model extraction
- ✅ Custom name priority system (config → BLE name → fallback)
- ✅ Added ble_name parameter to GoveeTemperatureService

### v1.3.2
- ✅ Lazy service creation (on-demand when first advertisement arrives)
- ✅ Correct model detection from real BLE names
- ✅ Updated service initialization flow

### v1.3.1
- ✅ Dynamic ProductID and ProductName based on model
- ✅ Model extraction from device name
- ✅ Removed ANSI color codes from add-sensor.sh

### v1.3.0
- ✅ H5100 sensor support (static random BLE address)
- ✅ H5105 sensor support (static random BLE address)
- ✅ Name-based filtering (replaced OUI-based filtering)
- ✅ Automatic discovery logging for sensors not in configuration
- ✅ Updated parser version to v1.1.0

### v1.2.0
- ✅ Configuration file restructuring
- ✅ Consolidated allowlist, names, temperature_type, device_instances into sensors array
- ✅ Eliminated MAC address repetition (DRY principle)
- ✅ Updated ConfigManager with add_sensor(), remove_sensor(), get_sensors(), update_sensor()
- ✅ Updated add-sensor.sh to work with sensors array
- ✅ Updated install.sh sensor count detection
- ✅ Updated all documentation (README, CHANGELOG, INSTALL.txt)

### v1.1.0
- ✅ Automatic backup on install
- ✅ Service stop before updates
- ✅ Accurate sensor count detection
- ✅ Boot persistence via rc.local
- ✅ Fixed add-sensor.sh color codes
- ✅ Removed find-sensors.sh
- ✅ Updated stale threshold to 300s
- ✅ Changed device ID range to 400-499
- ✅ Added BLE decoding documentation
- ✅ Anonymized MAC addresses
- ✅ Local build directory structure

### v1.0.0
- ✅ Automated installation script
- ✅ Configuration persistence (GUI → config.json)
- ✅ Service health monitoring
- ✅ Exponential backoff error recovery
- ✅ Log rotation
- ✅ Documentation overhaul
- ✅ GitHub release preparation

---

## Notes

- Review and prioritize quarterly
- Add new items as discovered
- Link to issues/PRs when created
- Update status as work progresses
