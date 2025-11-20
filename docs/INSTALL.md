# Phase 1 Installation on Venus OS

## Quick Install

### 1. Transfer Files to Venus OS

```bash
# On your computer, from where you downloaded govee-ble-phase1.tar.gz:
scp govee-ble-phase1.tar.gz root@<venus-ip>:/data/

# Or use WinSCP / FileZilla if on Windows
```

### 2. Extract and Test

```bash
# SSH to Venus OS
ssh root@<venus-ip>

# Extract
cd /data
tar -xzf govee-ble-phase1.tar.gz
cd govee-ble

# Run quick test
./quicktest.sh
```

**Expected output:**
```
==================================================
Govee BLE Parser - Phase 1 Quick Test
==================================================

1. Checking Python version...
   Python 3.12.12

2. Checking btmon...
   5.72

3. Checking Bluetooth...
   hci0: UP RUNNING

4. Running parser smoke test...
   âœ“ Parser test PASSED

5. Running config manager test...
   âœ“ Config manager test PASSED

6. Scanning for Govee sensors (10 seconds)...
   [Should see GVH5101 devices]

==================================================
Phase 1 Quick Test Complete!
==================================================
```

---

## Validation Workflow

### Step 1: Collect Samples (Venus OS)

```bash
cd /data/govee-ble

# Collect from your two sensors
python3 validate_parsing.py --collect \
  --macs A4:C1:38:B8:DF:A1 A4:C1:38:8E:0D:AF \
  --samples 10 \
  --duration 120 \
  --output samples.json

# This will take ~2 minutes and collect 10 samples from each sensor
```

**Expected output:**
```
Collected sample 1/10 for A4:C1:38:B8:DF:A1 (H5101): 4.7Â°C, 83.5%, 73%
Collected sample 2/10 for A4:C1:38:B8:DF:A1 (H5101): 4.7Â°C, 83.5%, 73%
...
Collection complete for all target MACs
Saved 20 samples to samples.json
```

### Step 2: Export from Govee App (iPhone)

1. Open **Govee Home** app
2. Select your **H5101** sensor (e.g., GVH5101_DFA1)
3. Tap the **temperature/humidity graph**
4. Tap the **share/export** icon (usually top-right)
5. Select **Export as CSV** or **Share**
6. Email to yourself or use AirDrop

**Note:** Some Govee apps export as:
- CSV file: `govee_export_2025-01-15.csv`
- Or in app settings â†’ Data Export

### Step 3: Transfer CSV to Venus OS

```bash
# From your computer:
scp govee_export.csv root@<venus-ip>:/data/govee-ble/
```

### Step 4: Compare

```bash
# On Venus OS:
cd /data/govee-ble
python3 validate_parsing.py --compare samples.json govee_export.csv
```

**Successful output:**
```
âœ“ PASS | Time diff: 2.3s
  Temperature: 22.5Â°C vs 22.5Â°C (diff: 0.00Â°C) âœ“
  Humidity:    65.2% vs 65.3% (diff: 0.10%) âœ“
  Battery:     85% vs 85% (diff: 0%) âœ“

âœ“ ALL COMPARISONS PASSED
```

---

## Troubleshooting

### Problem: "btmon not found"

```bash
# Check if btmon exists
which btmon

# If not found, install bluez-utils
opkg update
opkg install bluez-utils
```

### Problem: "No advertisements received"

```bash
# Check Bluetooth status
hciconfig

# Bring up interface
hciconfig hci0 up

# Enable scanning
bluetoothctl
[bluetooth]# scan on
[bluetooth]# devices

# You should see your Govee sensors listed
```

### Problem: "Parser returns None"

Enable verbose logging:
```bash
python3 validate_parsing.py --collect --duration 30 --verbose
```

Look for:
- `"Could not extract model from name"` - Name format unexpected
- `"No parser available for model"` - Model not supported
- `"Invalid H510x marker"` - Wrong data format

### Problem: "Govee app doesn't have export"

Try these alternatives:
1. **Screenshot method:** Take screenshots of the history graph
2. **Manual CSV:** Create CSV manually from app readings
3. **API method:** Some Govee devices support API export

**Manual CSV format:**
```csv
Timestamp,Temperature,Humidity,Battery
2025-01-15 10:30:00,22.5,65.2,85
2025-01-15 10:31:00,22.4,65.3,85
```

---

## Files Included

```
govee-ble/
â”œâ”€â”€ parser_adapter.py      - Core parser (H5101/H5102/H5104)
â”œâ”€â”€ btmon_reader.py        - btmon management
â”œâ”€â”€ config_manager.py      - Configuration handling
â”œâ”€â”€ validate_parsing.py    - Validation tool
â”œâ”€â”€ quicktest.sh           - Quick system test
â”œâ”€â”€ README_PHASE1.md       - Detailed documentation
â”œâ”€â”€ PHASE1_SUMMARY.md      - Completion summary
â””â”€â”€ INSTALL.md             - This file
```

---

## Next Steps After Validation

Once validation passes:

1. **Report results** - Share comparison output
2. **Identify any issues** - If any comparisons fail, we'll debug
3. **Proceed to Phase 2** - D-Bus integration and full system

---

## Support

If you encounter issues:

1. Run `./quicktest.sh` and share output
2. Run with `--verbose` flag for detailed logs
3. Share btmon output: `btmon -T 2>&1 | grep -A 15 GVH5101 | head -50`
4. Check system: `python3 --version`, `hciconfig`, `bluetoothctl list`

---

## What's Working

After successful installation:
- âœ… Parse H5101/H5102/H5104 sensors
- âœ… Detect Govee devices automatically
- âœ… Read live BLE advertisements
- âœ… Compare against app exports
- âœ… Safe configuration management
- âœ… Comprehensive error handling

Ready for Phase 2 after validation!
