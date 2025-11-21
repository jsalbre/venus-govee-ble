# Phase 2: D-Bus Integration - Implementation Plan

**Status:** In Progress  
**Started:** 2025-11-20  
**Goal:** Publish Govee sensor readings to Venus OS D-Bus

## Overview

Integrate validated BLE parsing (Phase 1) with Venus OS D-Bus system to display temperature and humidity readings in the Victron ecosystem.

## Architecture

```
govee_ble_service.py (Main Daemon)
    ├── btmon_reader.py (BLE advertisements)
    ├── parser_adapter.py (Parse advertisements)
    └── GoveeTemperatureService × N (One per sensor)
            └── Venus OS D-Bus
                    └── com.victronenergy.temperature.govee_XXXX
```

## Requirements

### Sensor Display
- **Service Type:** `com.victronenergy.temperature`
- **Metrics:** Temperature (°C) + Humidity (%)
- **Naming:** Govee name by default, user-configurable custom name
- **Update Frequency:** Real-time (every BLE advertisement)

### Service Management
- **Auto-start:** Run on boot via runit
- **Auto-restart:** Recover from crashes with exponential backoff
- **Logging:** Rotated logs (10MB × 7 files = 70MB max)

### Configuration
- **Whitelist:** Only configured MACs are monitored (empty = monitor nothing)
- **Custom Names:** Per-sensor configurable
- **Temperature Type:** Per-sensor (0=battery, 1=fridge, 2=generic), default 2

## Device Identity

### Product ID
- **Value:** `0xB101` (custom, "B" for Bluetooth + "101" for H5101)
- **Rationale:** Unique identifier, won't conflict with Victron products

### Device Instance
- **Algorithm:** `(last_4_bytes_of_mac) % 100`
- **Example:** `A4:C1:38:8E:0D:AF` → `0x0DAF` = 3503 → instance 3
- **Benefit:** Consistent across reinstalls for same sensor

### Service Name
- **Pattern:** `com.victronenergy.temperature.govee_<last4_mac_hex>`
- **Example:** `com.victronenergy.temperature.govee_0daf`

## D-Bus Paths (per Venus OS spec)

Each sensor exposes these paths:

| Path | Type | Description |
|------|------|-------------|
| `/Temperature` | float | Temperature in °C |
| `/Humidity` | float | Relative humidity % |
| `/Status` | int | 0=Ok, 1=Disconnected |
| `/Connected` | int | 1=connected, 0=disconnected |
| `/TemperatureType` | int | 0=battery, 1=fridge, 2=generic |
| `/CustomName` | string | User-configurable name |
| `/DeviceInstance` | int | Unique instance (0-99) |
| `/ProductId` | int | 0xB101 (45313 decimal) |
| `/ProductName` | string | "Govee H5101" |
| `/FirmwareVersion` | string | "1.0.0" |
| `/Mgmt/ProcessName` | string | "govee_ble_service" |
| `/Mgmt/ProcessVersion` | string | "2.0.0" |
| `/Mgmt/Connection` | string | "Bluetooth LE" |

## Connection State Management

### Stale Detection
- Track last advertisement timestamp per sensor
- Mark as "Disconnected" if no advertisement for 120 seconds (configurable)
- Update `/Status` to 1 (Disconnected)
- Update `/Connected` to 0
- Log disconnection event

### Reconnection
- Sensor automatically reconnects when advertisements resume
- Update `/Status` to 0 (Ok)
- Update `/Connected` to 1
- Log reconnection event

### Service Persistence
- D-Bus service stays registered when sensor disconnected
- No create/destroy cycle for temporary disconnections
- Prevents device instance churn

## Error Handling

### btmon Process Failure
- Detect via watchdog or process exit
- Log error with details
- Restart with exponential backoff: 30s, 60s, 120s, 300s (cap at 5min)
- Reset backoff after 1 hour of successful operation

### D-Bus Connection Loss
- Rare but possible
- Attempt reconnection
- Log error and recovery

### Malformed Advertisements
- Log once per unique error
- Don't spam logs with repeated errors
- Continue processing valid advertisements

## Logging Strategy

### Log Rotation
```python
RotatingFileHandler(
    '/data/govee-ble/logs/govee_ble.log',
    maxBytes=10*1024*1024,  # 10MB per file
    backupCount=7            # Keep 7 files = 70MB total
)
```

### Log Levels
- **INFO:** Service start/stop, sensor connect/disconnect, config changes
- **WARNING:** Recoverable errors, stale sensors, restart attempts
- **ERROR:** Unrecoverable errors, btmon failures, D-Bus issues
- **DEBUG:** Verbose mode (disabled by default)

### Logged Events
- Service startup/shutdown
- Sensor registration/deregistration
- Connection/disconnection events
- Advertisement processing errors
- btmon restarts
- Configuration reloads
- Backoff/retry attempts

## Configuration

### Example `config.json`
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
  "ble_interface": "hci0",
  "log_level": "INFO",
  "stale_threshold_sec": 120,
  "restart_min_delay_sec": 30,
  "restart_max_delay_sec": 300
}
```

### Configuration Hot-Reload
- Detect config file changes (periodic check or inotify)
- Compare old vs new configuration
- Add new sensors without restart
- Remove old sensors gracefully
- Update names/settings without disruption

## File Structure

```
/data/govee-ble/
├── govee_ble_service.py           # NEW: Main daemon
├── govee_temperature_service.py   # NEW: D-Bus service per sensor
├── parser_adapter.py              # Phase 1: Validated
├── btmon_reader.py                # Phase 1: Validated
├── config_manager.py              # Phase 1: Minor updates needed
├── validate_parsing.py            # Phase 1: Renamed from _v2
├── config.json                    # Configuration
├── ext/
│   └── velib_python/             # NEW: Victron D-Bus library
└── logs/
    ├── govee_ble.log
    ├── govee_ble.log.1
    └── ...

/service/govee-ble/                # NEW: runit service
├── run                            # Service script
└── log/
    └── run                        # Optional: separate log handling
```

## Implementation Steps

### 1. Install velib_python Dependency
```bash
cd /data/govee-ble
mkdir -p ext
cd ext
git clone https://github.com/victronenergy/velib_python.git
```

### 2. Create `govee_temperature_service.py`
Individual D-Bus service for one sensor.

**Key Features:**
- Uses VeDbusService from velib_python
- Registers all required paths
- Updates values when advertisements arrive
- Tracks connection state
- Handles stale detection

### 3. Create `govee_ble_service.py`
Main orchestrator daemon.

**Responsibilities:**
- Load and validate configuration
- Start btmon_reader
- Create GoveeTemperatureService for each allowlisted MAC
- Route advertisements to appropriate service
- Monitor sensor health (stale detection)
- Handle errors with backoff
- Setup log rotation
- Graceful shutdown

### 4. Update `config_manager.py`
Minor additions:
- `temperature_type` dict (MAC → type)
- `stale_threshold_sec` setting
- `restart_*_delay_sec` settings

### 5. Create runit Service
**File:** `/service/govee-ble/run`
```bash
#!/bin/sh
exec 2>&1
exec chpst -u root /usr/bin/python3 /data/govee-ble/govee_ble_service.py
```

**Enable:**
```bash
chmod +x /service/govee-ble/run
ln -s /service/govee-ble /etc/service/govee-ble
```

### 6. Testing Phases

**Phase 2.1: Core D-Bus Integration**
- [ ] velib_python installed
- [ ] govee_temperature_service.py created
- [ ] govee_ble_service.py created
- [ ] D-Bus registration working
- [ ] Readings visible in dbus-spy
- [ ] Sensors appear in Venus OS GUI

**Phase 2.2: Production Hardening**
- [ ] Log rotation configured
- [ ] Error recovery with backoff
- [ ] Stale sensor detection
- [ ] runit service configured
- [ ] Auto-start on boot working
- [ ] Service survives btmon crash

**Phase 2.3: Validation**
- [ ] 24-hour stability test
- [ ] Sensor disconnect/reconnect test
- [ ] Config hot-reload test
- [ ] Log rotation verification
- [ ] Resource usage monitoring

## Success Criteria

- ✓ Service registers sensors on Venus OS D-Bus
- ✓ Temperature and humidity visible in Venus OS GUI
- ✓ VRM Portal receives data automatically
- ✓ Sensors marked Disconnected after 120s without advertisement
- ✓ Service recovers from btmon crash with backoff
- ✓ Logs rotate at 10MB, keep 7 files
- ✓ Empty allowlist = no sensors active
- ✓ Custom names display correctly
- ✓ Device instances consistent across restarts
- ✓ Service auto-starts on boot
- ✓ Service auto-restarts on crash

## Venus OS Integration Points

### D-Bus Service Discovery
Venus OS automatically discovers services matching:
- `com.victronenergy.temperature.*`
- Displays in Settings → Temperature sensors
- Publishes to VRM Portal

### GUI Display
- Temperature shown with configured name
- Humidity shown if available
- Status indicator (connected/disconnected)
- Device type icon based on TemperatureType

### Settings Access
- Custom name editable via GUI (if implemented)
- Temperature type selectable
- Connection status visible

## Future Enhancements (Post Phase 2)

- Web UI for configuration
- MQTT integration for remote monitoring
- Battery level warnings
- Historical data graphs
- Multiple BLE adapter support
- Support for additional Govee models

## References

- [Venus OS D-Bus API](https://github.com/victronenergy/venus/wiki/dbus-api)
- [velib_python Documentation](https://github.com/victronenergy/velib_python)
- [dbus-adc Temperature Paths](https://github.com/victronenergy/dbus-adc)
- [Community Examples](https://community.victronenergy.com/questions/235893/emulate-temperature-sensor.html)

---

**Status:** Ready to begin implementation  
**Next:** Install velib_python and create govee_temperature_service.py
