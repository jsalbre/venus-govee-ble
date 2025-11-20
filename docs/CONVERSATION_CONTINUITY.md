# Conversation Continuity Document

**Last Updated:** 2025-11-19  
**Current Phase:** Phase 1 Complete, Ready for Phase 2  
**Project:** Govee BLE Venus OS Bridge

## Quick Context for New LLM Session

You are working with Jeremy on a Govee H5101 BLE sensor integration for Venus OS (Victron Cerbo GX). The project parses Bluetooth advertisements from btmon and will eventually publish readings to D-Bus.

**Immediate State:**
- Phase 1 parsing is complete and working
- Currently running 15-minute validation test to compare against Govee app exports
- Just moved project to GitHub: govee-ble-venus-py (private repo)

**Key Files:**
- `src/parser_adapter.py` - BLE parser (v1.0.3) - WORKING
- `src/btmon_reader.py` - btmon manager - FIXED (0x3e pattern for HCI events)
- `src/config_manager.py` - Config management (v1.0.0)
- `src/validate_parsing_v2.py` - Validation tool

**Jeremy's Sensors:**
- Freezer: A4:C1:38:8E:0D:AF (GVH5101_0DAF)
- Fridge: A4:C1:38:B8:DF:A1 (GVH5101_DFA1)

## Current Session History

### Issue 1: btmon_reader Stopped After ~99 Advertisements
**Root Cause:** btmon truncates event names in output:
- Events #1-9: `> HCI Event: LE Meta Event (0x3e)`
- Events #10-99: `> HCI Event: LE Meta Ev.. (0x3e)`
- Events #100+: `> HCI Event: LE Meta E.. (0x3e)`

**Fix Applied:** Changed HCI_EVENT_PATTERN to match on `(0x3e)` instead of event name:
```python
HCI_EVENT_PATTERN = re.compile(r'> HCI Event:.*\(0x3e\).*\[hci0\] (\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2}:\d{2}\.\d+)')
```

**Status:** Fixed and working. This fix must be maintained in all future code.

### Issue 2: GitHub Repository Setup
**Action:** Created complete GitHub-ready project structure
**Repo:** govee-ble-venus-py (private)
**Requirements:**
- All code changes must be committed to GitHub
- Regular conversation continuity updates
- Environment notes document maintained
- Claude must have access to the repository

**Status:** In progress - awaiting Jeremy to create GitHub repo and provide access instructions

## Technical Details

### Parsing Accuracy (Validated)
- **Temperature:** ±0.5°C (EXCELLENT) - Divide signed 16-bit by 39
- **Battery:** Exact match (PERFECT) - Direct byte value
- **Humidity:** ~15-20% error (KNOWN ISSUE) - Proceeding anyway

### btmon Output Format
Jeremy's system outputs HCI Event format (not MGMT Event format):
```
> HCI Event: LE Meta Event (0x3e) plen 43 #1 [hci0] 2025-11-18 16:13:20.682531
      LE Advertising Report (0x02)
        Address: A4:C1:38:8E:0D:AF (OUI A4-C1-38)
        Name (complete): GVH5101_0DAF
        Company: Nokia Mobile Phones (1)
          Data: 010182386140
        RSSI: -68 dBm (0xbc)
```

### GoveeWatcher Algorithm
Using the proven algorithm for decoding:
- Temperature: `decode_temps()` with sign bit handling
- Humidity: `decode_humi()` with 24-bit packed format
- Battery: Direct byte value

## Next Steps

1. **Current:** Wait for 15-minute validation test to complete
2. **Compare:** Run comparison against Govee app exports
3. **Document:** Update findings on humidity accuracy
4. **GitHub:** Set up repository access for Claude
5. **Phase 2:** Begin D-Bus integration planning

## Important Constraints

### Venus OS Environment (BusyBox)
See [ENVIRONMENT_NOTES.md](ENVIRONMENT_NOTES.md) for complete details:
- No `timeout` command
- `head`/`tail` use `-n` flag format (not `-50`, use `-n50`)
- `ps` doesn't support `-aux` (use just `ps`)
- Python 3.12.12, no external packages
- No `statistics` module - manual calculations

### Communication Preferences
- Professional tone, not overly complimentary
- Ask clarification questions as needed
- No guesses below 90% certainty
- Provide top 3 options when uncertain
- Be token-efficient
- Track conversation length, prepare handoff documents before limit

## Code Patterns to Maintain

### HCI Event Detection (CRITICAL)
Always use `(0x3e)` pattern, never rely on event name:
```python
HCI_EVENT_PATTERN = re.compile(r'> HCI Event:.*\(0x3e\).*\[hci0\] (\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2}:\d{2}\.\d+)')
```

### Temperature Decoding
```python
def decode_temps(data: bytes) -> float:
    """Decode temperature from bytes 2-3 (signed 16-bit)."""
    if len(data) < 4:
        return None
    temp_raw = int.from_bytes(data[2:4], byteorder='big', signed=True)
    return temp_raw / 39.0
```

### Validation Strategy
- Collect extended samples (15+ minutes)
- Group into 1-minute windows matching app export resolution
- Compare using configurable strategy (last/first/average/median)
- Use windowing because app exports are 1-minute resolution only

## Files to Reference

Before coding, reference these documents:
1. **ENVIRONMENT_NOTES.md** - Check command availability and syntax
2. **This file** - Understand current state and decisions
3. **PHASE1_SUMMARY.md** - Technical implementation details

## GitHub Workflow (To Be Established)

Once repository is created:
1. Clone locally or work directly via API
2. Commit all code changes with descriptive messages
3. Update CONVERSATION_CONTINUITY.md regularly
4. Update ENVIRONMENT_NOTES.md when learning new constraints
5. Push changes after each significant development session

## Key Learnings

### What Worked
- GoveeWatcher algorithm for temperature
- btmon -T with HCI Event format parsing
- 1-minute windowing strategy for validation
- Proceeding despite humidity limitation (temperature is primary requirement)

### What Didn't Work
- Simple byte extraction for humidity
- Assuming btmon event names are consistent (they truncate)
- Expecting 1:1 timestamp matching between btmon and app exports

### Design Decisions
- Accept ~15-20% humidity error (temperature monitoring is primary goal)
- Use last sample in 1-minute window (most recent reading)
- No external Python packages (Venus OS constraint)
- Single-file modules for easy deployment

## Validation Test in Progress

Currently running:
```bash
python3 validate_parsing_v2.py --collect \
  --macs A4:C1:38:B8:DF:A1 A4:C1:38:8E:0D:AF \
  --duration 900 \
  --output samples_$(date +%Y%m%d_%H%M).json
```

Next: Compare against Govee app exports with timezone conversion (CST to UTC, offset -6)

---

## For Next LLM Session

1. Read this document first
2. Check ENVIRONMENT_NOTES.md for Venus OS constraints
3. Review latest commit messages in GitHub
4. Ask Jeremy for current status/blockers
5. Reference the working code in `src/` directory
6. Maintain all established patterns and fixes
