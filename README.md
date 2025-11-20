# Govee BLE Venus OS Bridge

Python bridge for integrating Govee H5101 Bluetooth temperature/humidity sensors with Victron Energy Venus OS.

## Overview

This project enables Victron Cerbo GX devices to monitor Govee H5101 sensors via Bluetooth Low Energy (BLE) advertisements. Temperature readings are parsed from BLE advertisements and will be published to the Venus OS D-Bus for integration with the Victron ecosystem.

**Current Status:** Phase 1 Complete - BLE parsing and validation
**Next Phase:** Phase 2 - D-Bus integration

## Hardware Requirements

- Victron Cerbo GX (or compatible Venus OS device)
- Govee H5101 Bluetooth Temperature/Humidity Sensors
- Bluetooth adapter (built-in or USB)

## Supported Sensors

- **Govee H5101** - Primary support (refrigerator/freezer monitoring)
- Additional Govee models may work but are untested

## Project Structure

```
govee-ble-venus-py/
├── src/                    # Source code
│   ├── parser_adapter.py   # BLE advertisement parser
│   ├── btmon_reader.py     # btmon process manager
│   ├── config_manager.py   # Configuration management
│   └── validate_parsing_v2.py  # Validation tool
├── tests/                  # Test files
├── samples/                # Sample data and validation exports
├── docs/                   # Documentation
│   ├── CONVERSATION_CONTINUITY.md  # LLM conversation handoff
│   ├── ENVIRONMENT_NOTES.md        # Venus OS environment specifics
│   └── PHASE1_SUMMARY.md           # Phase 1 completion notes
└── .github/                # GitHub configuration
```

## Installation

See [INSTALL.md](docs/INSTALL.md) for detailed installation instructions.

Quick start:
```bash
# Copy files to Venus OS
scp -r src/* root@cerbo-gx.local:/data/govee-ble/

# Test parser
python3 /data/govee-ble/parser_adapter.py

# Collect samples
python3 /data/govee-ble/validate_parsing_v2.py --collect \
  --macs A4:C1:38:B8:DF:A1 A4:C1:38:8E:0D:AF \
  --duration 900 \
  --output samples.json
```

## Current Capabilities

### Temperature Monitoring ✓
- Accuracy: ±0.5°C vs Govee app
- Decoding: Signed 16-bit value ÷ 39
- Validated against iPhone app exports

### Battery Monitoring ✓
- Accuracy: Exact match with app
- Direct byte value reading

### Humidity Monitoring ⚠️
- Known issue: ~15-20% discrepancy vs app
- Using GoveeWatcher algorithm
- Proceeding despite limitation (temperature is primary requirement)

## Venus OS Environment

This project runs on Venus OS, which uses BusyBox and has specific limitations:

- **Python:** 3.12.12 (no pip/external packages)
- **Shell:** BusyBox ash
- **Bluetooth:** BlueZ 5.72 with btmon utility
- See [docs/ENVIRONMENT_NOTES.md](docs/ENVIRONMENT_NOTES.md) for detailed constraints

## Development Workflow

All code changes must be committed to GitHub. See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for contribution guidelines.

## Documentation

- **[CONVERSATION_CONTINUITY.md](docs/CONVERSATION_CONTINUITY.md)** - For resuming AI-assisted development
- **[ENVIRONMENT_NOTES.md](docs/ENVIRONMENT_NOTES.md)** - Venus OS environment specifics
- **[PHASE1_SUMMARY.md](docs/PHASE1_SUMMARY.md)** - Phase 1 completion details
- **[INSTALL.md](docs/INSTALL.md)** - Installation instructions

## Roadmap

### Phase 1: BLE Parsing ✓ Complete
- [x] Parse BLE advertisements from btmon
- [x] Decode temperature (accurate)
- [x] Decode battery (accurate)
- [x] Decode humidity (known limitation)
- [x] Validation framework

### Phase 2: D-Bus Integration (Next)
- [ ] Publish temperature readings to Venus OS D-Bus
- [ ] Create virtual temperature sensors
- [ ] Handle sensor disconnection/reconnection
- [ ] Service management (runit)

### Phase 3: Production Deployment
- [ ] Automatic startup on boot
- [ ] Logging and monitoring
- [ ] Configuration management
- [ ] Update mechanism

## License

Private/proprietary - No license specified

## Contact

Jeremy - Project Owner
