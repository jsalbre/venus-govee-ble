# Govee BLE Project - Conversation Continuity Document
**Last Updated:** 2025-11-21  
**Project Phase:** Phase 1 Complete → Phase 2 Ready to Begin

---

## CRITICAL: Document Maintenance Requirement

**All conversation continuity documents MUST be updated throughout development.**  
This ensures seamless LLM handoffs between conversations. Update this document and related files as work progresses.

---

## Project Context

Jeremy is building a Govee BLE bridge for Venus OS (Cerbo GX) to integrate H5101 Bluetooth temperature/humidity sensors with the Victron Energy ecosystem. The project monitors refrigerator and freezer temperatures.

**Sensors:**
- Freezer: A4:C1:38:8E:0D:AF (GVH5101_0DAF)
- Fridge: A4:C1:38:B8:DF:A1 (GVH5101_DFA1)

**Environment:**
- Venus OS (BusyBox-based Linux)
- Python 3.12.12
- BlueZ 5.72 (btmon utility)
- Working directory: `/data/govee-ble/`
- GitHub repository: `govee-ble-venus-py` (private)

---

## Current Status: Phase 1 COMPLETE ✅

### Working Components

✅ **Parser (parser_adapter.py v1.0.3):**
- GoveeWatcher algorithm implemented
- Temperature decoding: accurate (±0.5°C) using /39 formula
- Battery decoding: accurate (exact byte value)
- Humidity decoding: ~15-20% error vs app (known issue, **proceeding anyway** since temp is primary requirement)
- Smoke tests passing

✅ **btmon_reader.py:**
- Successfully processes HCI Event format from Jeremy's btmon
- Continuous advertisement collection working
- Handles both MGMT Event and HCI Event formats
- Watchdog and midnight rollover working
- **Previous 8-advertisement bug: RESOLVED**

✅ **config_manager.py v1.0.0:**
- Thread-safe configuration with file locking
- Allowlist management (MAC addresses)
- Custom names per sensor
- Device instance tracking
- All tests passing

✅ **validate_parsing.py:**
- Live BLE sample collection working
- Govee app CSV import and comparison
- Tolerance-based validation
- All functionality verified

### Validation Results

**Temperature:** Accurate within ±0.5°C of Govee iPhone app readings  
**Battery:** Exact match with app  
**Humidity:** ~15-20% discrepancy from app (not blocking - temperature is priority)

---

## Phase 2: D-Bus Integration - READY TO BEGIN

### Objectives

1. Register virtual temperature sensors on Venus OS D-Bus
2. Publish temperature/humidity readings from BLE advertisements
3. Handle sensor connection/disconnection gracefully
4. Service management (runit for automatic startup/restart)
5. Configuration for sensor-to-device-instance mapping

### Design Decisions (Finalized)

**D-Bus Service:**
- Service type: `com.victronenergy.temperature`
- Service name pattern: `com.victronenergy.temperature.govee_<last_4_mac>`
- Example: `com.victronenergy.temperature.govee_0daf`

**Product/Device IDs:**
- ProductID: `0xB101` (custom: "B" for Bluetooth + "101" for H5101)
- DeviceInstance: Derived from MAC address → `(last_4_bytes % 100)`
  - Consistent across reinstalls for same sensor
  - Example: A4:C1:38:8E:0D:AF → instance 15 (0DAF % 100)

**D-Bus Paths (Required):**
```
/Temperature           # Celsius
/Humidity              # Percent
/Status                # 0=Ok, 1=Disconnected
/Connected             # 1 or 0
/TemperatureType       # 0=battery, 1=fridge, 2=generic (default 2, configurable)
/CustomName            # User-configurable name (default: GVH5101_XXXX)
/DeviceInstance        # Unique instance number
/ProductId             # 0xB101
/ProductName           # "Govee H5101"
/FirmwareVersion       # "1.0.0"
/Mgmt/ProcessName      # "govee_ble_service"
/Mgmt/ProcessVersion   # "2.0.0"
/Mgmt/Connection       # "Bluetooth LE"
```

**Configuration Features:**
- ✅ Allowlist already exists in config_manager.py
- ✅ Custom names per sensor already exists
- **Empty allowlist = monitor NOTHING** (security: only whitelisted sensors appear)
- Temperature type: default 2 (generic), configurable per sensor
- Update frequency: Every BLE advertisement push (~2-3 seconds)
- Stale sensor detection: 120 seconds without advertisement → mark Disconnected

**Service Management:**
- Run on boot via runit
- Auto-restart on crash with exponential backoff (30s, 60s, 120s, 300s max)
- Reset backoff after 1 hour successful operation
- Log rotation: 10MB per file, 7 files max (~70MB total)

### Implementation Plan

**File Structure:**
```
/data/govee-ble/
├── govee_ble_service.py          # NEW: Main orchestrator daemon
├── govee_temperature_service.py  # NEW: D-Bus service per sensor
├── parser_adapter.py             # Existing (Phase 1)
├── btmon_reader.py               # Existing (Phase 1)
├── config_manager.py             # Existing (Phase 1, minor updates needed)
├── validate_parsing.py           # Existing (renamed from _v2)
├── ext/
│   └── velib_python/             # NEW: Victron library dependency
│       ├── vedbus.py
│       └── ve_utils.py
└── logs/
    └── govee_ble.log             # Rotated logs

/service/govee-ble/               # NEW: runit service
├── run                           # Service script
└── log/
    └── run                       # Log script (optional)
```

**Development Order:**
1. ✅ Clone/fetch velib_python dependency (vedbus.py, ve_utils.py)
2. Create `govee_temperature_service.py` (D-Bus interface for individual sensor)
3. Create `govee_ble_service.py` (main orchestrator)
4. Update `config_manager.py` (add temperature_type, stale_threshold_sec)
5. Create runit service script
6. Test on Venus OS
7. Update documentation

**Testing Strategy:**
1. Smoke test: Verify parser still works
2. Dry run: Start service, verify D-Bus registration without real sensors
3. Live test: Run with real sensors, verify readings in Venus OS GUI
4. Disconnect test: Power off sensor, verify Status→Disconnected after 120s
5. Restart test: Kill btmon, verify service recovers with exponential backoff
6. Log test: Generate many advertisements, verify rotation at 10MB

---

## Technical Details

### btmon Output Format
Jeremy's btmon outputs **HCI Event format**, not MGMT Event format:
```
> HCI Event: LE Meta... (0x3e) plen 43 #1026 [hci0] 2025-11-18 16:13:20.682531
      LE Advertising Report (0x02)
        Num reports: 1
        Event type: Connectable undirected - ADV_IND (0x00)
        Address type: Public (0x00)
        Address: A4:C1:38:8E:0D:AF (OUI A4-C1-38)
        Data length: 31
        Name (complete): GVH5101_0DAF
        16-bit Service UUIDs (complete): 1 entry
          Unknown (0xec88)
        Flags: 0x05
          LE Limited Discoverable Mode
          BR/EDR Not Supported
        Company: Nokia Mobile Phones (1)
          Data: 010182386140
        RSSI: -68 dBm (0xbc)
```

### btmon_reader.py Event Detection
The code has patterns for BOTH formats:
```python
MGMT_EVENT_PATTERN = re.compile(r'@ MGMT Event:.*\(0x0012\).*\[hci0\] (\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2}:\d{2}\.\d+)')
HCI_EVENT_PATTERN = re.compile(r'> HCI Event: LE Meta Event.*\[hci0\] (\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2}:\d{2}\.\d+)')
LE_ADVERTISING_REPORT = re.compile(r'LE Advertising Report')
```

---

## GitHub Access Status (Claude Development Environment)

**Issue:** Network proxy blocks git operations with 401 authentication errors

**Test Results (2025-11-21):**
- ❌ `git clone` - FAILED (public repos)
- ❌ `git push` - FAILED
- ❌ `git pull` - FAILED
- ✅ `web_fetch` tool - WORKS for individual file retrieval

**Workaround:**
- Files retrieved via `web_fetch` and created manually in Claude environment
- Testing done locally in Claude environment
- Files packaged for transfer to Venus OS where git works normally
- Jeremy performs git operations on Venus OS system

**velib_python Dependency:**
- Successfully retrieved `vedbus.py` content via web_fetch
- Need to retrieve `ve_utils.py` content
- Will create files manually in development environment

---

## Files Status

**Phase 1 Files (Complete):**
- ✅ `parser_adapter.py` - v1.0.3
- ✅ `btmon_reader.py` - Working
- ✅ `config_manager.py` - v1.0.0
- ✅ `validate_parsing.py` - Renamed from validate_parsing_v2.py
- ✅ `debug_btmon.py` - v1.0.0

**Phase 2 Files (Pending):**
- ⏳ `ext/velib_python/vedbus.py` - Retrieved, needs creation
- ⏳ `ext/velib_python/ve_utils.py` - Needs retrieval
- ⏳ `govee_temperature_service.py` - Not started
- ⏳ `govee_ble_service.py` - Not started
- ⏳ `/service/govee-ble/run` - Not started

**Cleanup Pending (Next Push):**
- Rename `validate_parsing_v2.py` → `validate_parsing.py`
- Remove old/unused script versions
- Keep only production files

---

## Important Constraints

**Venus OS / BusyBox limitations Jeremy has reported:**
- No `timeout` command
- `head` and `tail` require `-n` flag (not `-20`, use `-n20`)
- `ps` doesn't support `-aux` flags (use just `ps`)
- Python 3.12.12 (no external packages available)
- No `statistics` module - use manual mean/median calculations

**Communication preferences:**
- Don't use commands that don't exist on the system
- Provide archives for multiple files, not individual downloads
- No guesses - if uncertain, offer top 3 options
- Professional tone, not overly complimentary
- Be efficient with tokens
- **Update continuity docs throughout development**

---

## Configuration Example (Phase 2)

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
    "A4:C1:38:8E:0D:AF": 1,
    "A4:C1:38:B8:DF:A1": 1
  },
  "device_instances": {},
  "ble_interface": "hci0",
  "log_level": "INFO",
  "stale_threshold_sec": 120,
  "restart_min_delay_sec": 30,
  "restart_max_delay_sec": 300
}
```

---

## Quick Reference Commands

### Phase 1 Testing
```bash
# Test parser
python3 parser_adapter.py

# Debug btmon reader
python3 debug_btmon.py 2>&1 | grep -E "Advertisement|GVH"

# Check btmon process
ps | grep btmon

# Collect samples
python3 validate_parsing.py --collect \
  --macs A4:C1:38:B8:DF:A1 A4:C1:38:8E:0D:AF \
  --duration 900 \
  --output samples_$(date +%Y%m%d_%H%M).json

# View btmon output directly
btmon -T 2>&1 | grep -i gvh -B10 -A10
```

### Phase 2 Testing (Future)
```bash
# Check D-Bus service registration
dbus-send --system --print-reply \
  --dest=org.freedesktop.DBus \
  /org/freedesktop/DBus \
  org.freedesktop.DBus.ListNames | grep govee

# Read temperature value
dbus-send --system --print-reply \
  --dest=com.victronenergy.temperature.govee_0daf \
  /Temperature \
  com.victronenergy.BusItem.GetValue

# Check service status (runit)
svstat /service/govee-ble

# View logs
tail -f /data/govee-ble/logs/govee_ble.log
```

---

## Known Issues and Decisions

### Humidity Discrepancy (Accepted)
- Humidity readings ~15-20% different from Govee app
- **Decision:** Proceeding anyway - temperature monitoring is primary requirement
- May investigate further in future if humidity becomes important

### btmon Output Format
- Jeremy's system outputs **HCI Event format**, not MGMT Event format
- Parser handles both formats correctly
- No action needed

---

## Success Criteria

### Phase 1 (Complete) ✅
- ✅ Parse BLE advertisements correctly
- ✅ Extract temperature, humidity, battery
- ✅ Temperature accurate within ±0.5°C
- ✅ Handle btmon subprocess management
- ✅ Thread-safe configuration
- ✅ Validation against Govee app

### Phase 2 (Pending)
- ⏳ Service starts and registers sensors on D-Bus
- ⏳ Readings appear in Venus OS GUI
- ⏳ Sensors marked Disconnected after 120s without advertisement
- ⏳ Service recovers from btmon crash
- ⏳ Logs rotate at 10MB
- ⏳ Empty allowlist = no sensors active
- ⏳ Custom names appear correctly
- ⏳ Device instances consistent across restarts

---

## Next Immediate Actions

1. **Retrieve ve_utils.py** content via web_fetch
2. **Create velib_python files** in development environment
3. **Implement govee_temperature_service.py** - D-Bus service per sensor
4. **Implement govee_ble_service.py** - Main orchestrator
5. **Update config_manager.py** - Add temperature_type and stale_threshold_sec
6. **Create runit service script**
7. **Test locally** in Claude environment (limited testing without actual D-Bus)
8. **Package for Venus OS deployment**
9. **Update all documentation** throughout process

---

**Status:** Phase 1 Complete, Phase 2 Ready to Begin  
**Priority:** MEDIUM - Core functionality working, D-Bus integration enhances value  
**Blocker:** None - All dependencies identified and retrievable
