# Future Development TODO

## Planned Features & Improvements

### High Priority

#### Configuration File Restructuring
**Status:** Not started
**Priority:** High
**Estimated Effort:** Medium

**Current Problem:**
The config.json file requires repeating MAC addresses in three separate sections:
```json
{
  "allowlist": ["A4:C1:38:XX:XX:XX", "A4:C1:38:YY:YY:YY"],
  "names": {
    "A4:C1:38:XX:XX:XX": "Freezer",
    "A4:C1:38:YY:YY:YY": "Fridge"
  },
  "temperature_type": {
    "A4:C1:38:XX:XX:XX": 6,
    "A4:C1:38:YY:YY:YY": 1
  }
}
```

**Proposed Solution:**
Combine into a single sensor array structure:
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

**Benefits:**
- Single source of truth for each sensor
- No MAC repetition (DRY principle)
- Easier to add/remove sensors
- More maintainable
- Clearer structure

**Implementation Notes:**
- Need migration script for existing configs
- Update ConfigManager to support both old and new formats during transition
- Update add-sensor.sh script
- Update all documentation
- Consider backward compatibility period

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

#### Improved Humidity Algorithm
**Status:** Research needed
**Priority:** Medium
**Estimated Effort:** High

**Current Status:**
- Temperature: ±0.5°C (excellent)
- Battery: Exact match (excellent)
- Humidity: ~15-20% error (needs improvement)

**Next Steps:**
- Collect more sample data
- Compare with Govee app readings
- Research alternative decoding algorithms
- Test with multiple sensors
- Validate improvements

---

### Low Priority

#### Configuration GUI/Web Interface
**Status:** Idea phase
**Priority:** Low
**Estimated Effort:** High

Web-based configuration interface for:
- Sensor discovery and addition
- Name and type editing
- Service management
- Log viewing
- Real-time sensor readings

**Technologies:**
- Lightweight web server (Flask/Bottle)
- Venus OS web integration
- REST API for service control

---

#### Historical Data Export
**Status:** Idea phase
**Priority:** Low
**Estimated Effort:** Medium

Export sensor readings to CSV/JSON for analysis:
- Configurable time ranges
- Multiple sensors
- Include metadata (temperature, humidity, battery, RSSI)
- Integration with Venus OS VRM data

---

#### Multi-Adapter Support
**Status:** Idea phase
**Priority:** Low
**Estimated Effort:** Medium

Support for multiple Bluetooth adapters:
- Load balancing across adapters
- Failover on adapter failure
- Configurable adapter assignment per sensor

---

## Completed Items

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
