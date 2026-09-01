# TODO

---

## Low Priority

### Configuration Web Interface

**Status:** Not started

Add a web-based configuration UI for managing sensors without SSH access.

---

### Historical Data Export

**Status:** Not started

Export historical readings to CSV or other formats for external analysis.

---

### Bluetooth Adapter Redundancy

**Status:** Not started

Support failover to a secondary Bluetooth adapter and/or multiple simultaneous adapters.

---

### Additional Sensor Models

**Status:** Not started

Add parser support for:
- H5075 (different encoding)
- H5074 (different encoding)
- B5178 (different encoding)

**Implementation:**
1. Research encoding formats for each model
2. Add parser functions to `src/parser_adapter.py`
3. Update PARSER_REGISTRY
4. Test with real devices
5. Update documentation
