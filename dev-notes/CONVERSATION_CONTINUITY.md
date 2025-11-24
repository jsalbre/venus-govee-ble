# Govee BLE Project - Conversation Continuity Document
**Last Updated:** 2025-11-24 (v1.1.0 Released - Bug Fixes and Polish)
**Project Phase:** v1.1.0 PRODUCTION - Stable with Automated Deployment

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

## Current Status: v1.1.0 PRODUCTION RELEASE (2025-11-24) ✅

### Release v1.1.0 - Bug Fixes and Polish

**Status:** Stable, all installation and discovery issues resolved

**Fixes in v1.1.0:**

1. **Installation Improvements**
   - Automatic backup before updates
   - Service stop before file updates
   - Accurate sensor count detection (Python JSON parsing)
   - Boot persistence via /data storage and rc.local

2. **Helper Script Fixes**
   - add-sensor.sh: Fixed ANSI color codes printing literally
   - add-sensor.sh: Anonymized MAC addresses in examples
   - Removed find-sensors.sh (replaced with automatic log-based discovery)

3. **Configuration Updates**
   - Stale threshold: 120s → 300s
   - Device ID range: 0-99 → 400-499

4. **Documentation Polish**
   - Added BLE decoding formulas with real examples
   - Removed all find-sensors.sh references
   - Corrected sensor discovery instructions
   - Anonymized all MAC addresses
   - Updated GitHub username

**Deployment Package:**
- Location: `dist/govee-ble-deploy.tar.gz` (72K)
- Version: v1.1.0
- Files: 43 total

---

## Previous Release: v1.0.0 PRODUCTION RELEASE (2025-11-24)

### Release v1.0.0 - Production-Ready Deployment Package

**Status:** Feature complete, validated, and ready for deployment

**Major Improvements Since Phase 2:**

1. **Automated Installation System**
   - `install.sh` - One-command automated installation
   - `add-sensor.sh` - Helper script to add sensors to allowlist
   - Automatic backup of existing installations before update
   - Service stop/start automation
   - Boot persistence via /data/rc.local

2. **Automatic Sensor Discovery**
   - Service logs all discovered Govee sensors automatically
   - No separate discovery tool needed
   - Log format: "Discovered Govee sensor not in allowlist: MAC (name)"
   - Users monitor logs to find sensor MAC addresses

3. **Documentation Overhaul**
   - README.md - Production-ready user guide with BLE decoding formulas
   - CHANGELOG.md - Complete version history
   - INSTALL.txt - Simplified installation instructions
   - Technical details section with real decoding examples
   - All MAC addresses anonymized (kept OUI A4:C1:38)

4. **Configuration Management**
   - Stale threshold increased: 120s → 300s
   - Device ID range: 400-499 (was 0-99)
   - Temperature types: 0=Battery, 1=Fridge, 2=Generic, 3=Room, 4=Outdoor, 5=Water heater, 6=Freezer
   - Config persistence: GUI changes auto-save to config.json

5. **Service Improvements**
   - Service persistence across reboots (/data/govee-ble/service)
   - Automatic symlink creation in rc.local
   - Proper stop sequence during updates
   - Accurate sensor count detection (Python JSON parsing)

6. **Build System**
   - Local build directory: `/Volumes/Repo/Development/govee-ble-venus-py/build/`
   - Release artifacts: `/Volumes/Repo/Development/govee-ble-venus-py/dist/`
   - Tarball includes: README.md, CHANGELOG.md, add-sensor.sh
   - No meta files in deployment (dev-notes, samples excluded)

**Deployment Package:**
- Location: `dist/govee-ble-deploy.tar.gz` (72K)
- GitHub repo: `jsalbre/govee-ble-venus-py`
- Files: 43 total (service files, scripts, documentation)

**Known Limitations:**
- Humidity: ~15-20% discrepancy vs Govee app (algorithm limitation)
- Temperature and battery: Highly accurate (±0.5°C, exact match)
- Models: Only H510x family supported (H5075, H5074 parsers not implemented)

---

## Previous Phase: Phase 2 TESTING - Bug Fixes Applied (2025-11-23)

### Phase 2 Bugs Found and Fixed During Testing

**Bug #1: Import Path Error** (Fixed in commit `ac6bc96`)
- **Error:** `ModuleNotFoundError: No module named 'vedbus'`
- **Cause:** Import path `'../ext/velib_python'` was incorrect when scripts run from `/data/govee-ble/`
- **Fix:** Changed to `'ext/velib_python'` in both service files
- **Files:** `govee_temperature_service.py:14`, `govee_ble_service.py:23`

**Bug #2: D-Bus Path Conflict** (Fixed in commit `7543729`)
- **Error:** `KeyError: "Can't register the object-path handler for '/': there is already a handler"`
- **Cause:** `dbus.SystemBus()` returns singleton connection; both sensors tried to register root path on same connection
- **Fix:** Create private D-Bus connections using `dbus.SystemBus(private=True)` for each sensor
- **File:** `govee_ble_service.py:198`

**Bug #3: Temperature Type Values** (Fixed in commit `6081080`)
- **Issue:** Temperature type enum values were incorrect
- **Correct Values:** 0=battery, 1=fridge, 2=generic, 3=room, 4=outdoor, 5=waterheater, 6=freezer
- **Fix:** Made TemperatureType and CustomName writable, updated config (Freezer=6, Fridge=1)
- **Files:** `govee_temperature_service.py:100-102`, `config.example.json`

**Bug #4: Advertisement Key Mismatch** (Fixed in commit `b586b38`) 🔴 **CRITICAL**
- **Symptom:** Services registered on D-Bus but no sensor data appeared; Govee MACs never showed in logs
- **Root Cause:** `_handle_advertisement()` looked for key `'address'` but `AdvertisementAssembler` returns `'mac'`
- **Result:** All advertisements were silently filtered out even when properly assembled
- **Fix:** Changed `adv_data.get('address', '')` → `adv_data.get('mac', '')`
- **File:** `govee_ble_service.py:242`
- **Impact:** This was preventing ALL sensor data from reaching D-Bus services

**Bug #5: Performance - Processing All BLE Devices** (Fixed in commits `9d8b237`, `aa497dd`) 🔴 **CRITICAL**
- **Symptom:** System falling ~2 minutes behind; taking ~3 seconds to process each advertisement
- **Root Causes:**
  1. Parsed complete advertisement data for ALL 100+ BLE devices in range
  2. Debug logging spam - hundreds of log writes per second
  3. Read only 1 line per 100ms callback - backlog buildup
- **Triple Fix:**
  1. **Govee OUI Filter (A4:C1:38):** Two-stage filtering - check Govee OUI prefix first, then allowlist. Silently discard 99% of devices before parsing details
  2. **Remove Debug Spam:** Eliminated "Started event" and "Filtered MAC" logs for non-Govee devices. Only log accepted Govee sensors
  3. **Multi-line Reading:** Read up to 100 lines per callback instead of 1. Clears backlog quickly
- **Files:** `btmon_reader.py:99-111,220-234,283`, `govee_ble_service.py:293-300,313-337`
- **Impact:** Near real-time processing with no backlog; minimal CPU and I/O overhead

### Phase 2 Implementation Complete

✅ **velib_python Dependency:**
- Successfully cloned from https://github.com/victronenergy/velib_python
- Location: `/ext/velib_python/`
- All files available: `vedbus.py`, `ve_utils.py`, supporting modules

✅ **govee_temperature_service.py (v2.0.0):**
- D-Bus service class for individual sensors
- Implements `com.victronenergy.temperature` service type
- All required D-Bus paths implemented
- Stale detection support
- Custom name and temperature type configuration

✅ **govee_ble_service.py (v2.0.0):**
- Main orchestrator daemon
- btmon reader integration
- Advertisement routing to services
- Exponential backoff for restarts (30s → 300s)
- Log rotation (10MB × 7 files)
- Graceful shutdown handling
- Stale sensor monitoring (120s threshold)

✅ **config_manager.py Updates:**
- Added `restart_min_delay_sec: 30`
- Added `restart_max_delay_sec: 300`
- Updated log path to `/data/govee-ble/logs/govee_ble.log`
- All Phase 2 configuration fields present

✅ **Runit Service Script:**
- Created at `service/govee-ble/run`
- Ready for deployment to `/service/govee-ble/`

✅ **Documentation:**
- `config.example.json` - Example configuration with user's sensors
- `docs/DEPLOYMENT.md` - Complete deployment guide for Venus OS

### Ready for Phase 2 Testing

**Next Steps:**
1. Deploy to Venus OS test environment
2. Test D-Bus service registration
3. Verify sensors appear in Venus OS GUI
4. Test stale detection (power off sensor)
5. Test service restart/recovery
6. Monitor logs and performance
7. Address any issues found in testing

---

## Phase 1 Status: COMPLETE ✅

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

**velib_python Dependency (2025-11-22 Update):**
- ✅ Successfully cloned complete repository via git (on Jeremy's local machine)
- Location: `ext/velib_python/`
- All files available: `vedbus.py`, `ve_utils.py`, and supporting modules
- Note: git works on Jeremy's local machine; previous issues were in Claude-hosted environment

---

## Files Status

**Phase 1 Files (Complete):**
- ✅ `parser_adapter.py` - v1.0.3
- ✅ `btmon_reader.py` - Working
- ✅ `config_manager.py` - v1.0.0
- ✅ `validate_parsing.py` - Renamed from validate_parsing_v2.py
- ✅ `debug_btmon.py` - v1.0.0

**Phase 2 Files (Complete 2025-11-22):**
- ✅ `ext/velib_python/` - Complete repository cloned
- ✅ `src/govee_temperature_service.py` - v2.0.0 (D-Bus service per sensor)
- ✅ `src/govee_ble_service.py` - v2.0.0 (Main orchestrator daemon)
- ✅ `src/config_manager.py` - Updated with Phase 2 fields
- ✅ `service/govee-ble/run` - Runit service script
- ✅ `config.example.json` - Example configuration
- ✅ `docs/DEPLOYMENT.md` - Deployment guide

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

## Phase 2 Implementation Summary (2025-11-22)

### Completed Tasks
1. ✅ Cloned velib_python dependency
2. ✅ Implemented govee_temperature_service.py (v2.0.0)
3. ✅ Implemented govee_ble_service.py (v2.0.0)
4. ✅ Updated config_manager.py with Phase 2 fields
5. ✅ Created runit service script
6. ✅ Created example configuration
7. ✅ Created deployment guide
8. ✅ Updated all documentation

### Next Immediate Actions - Testing Phase

**Deployment Instructions:**
```bash
# Quick fix (just update fixed file):
scp src/govee_ble_service.py root@venus.local:/data/govee-ble/

# OR full clean deployment:
scp ~/govee-ble-deploy.tar.gz root@venus.local:/tmp/
ssh root@venus.local "rm -rf /data/govee-ble /service/govee-ble && cd / && tar xzf /tmp/govee-ble-deploy.tar.gz"
```

**Testing Checklist:**
1. ⏳ **Deploy bug fixes** - Transfer updated govee_ble_service.py to Venus OS
2. ⏳ **Verify advertisements received** - Check logs for Govee MACs appearing
3. ⏳ **Verify D-Bus updates** - Check temperature/humidity values updating
4. ⏳ **Test in Venus OS GUI** - Verify sensors show in temperature list with correct data
5. ⏳ **Stale detection test** - Power off sensor, verify disconnect after 120s
6. ⏳ **Recovery test** - Kill service, verify runit restarts it
7. ⏳ **Log monitoring** - Verify rotation and no errors
8. ⏳ **Performance check** - Monitor CPU/memory usage over 24 hours

---

**Status:** Phase 2 TESTING - Bug Fixes Applied (2025-11-23)
**Priority:** HIGH - Critical bug fixed (advertisement key mismatch), ready for retest
**Blocker:** None - All known bugs fixed, ready for Venus OS testing
**Files Ready:** Updated tarball at `~/govee-ble-deploy.tar.gz` (455K)
