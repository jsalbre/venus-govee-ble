# Venus OS Environment Notes

**System:** Venus OS (Victron Energy)  
**Device:** Cerbo GX  
**Base:** BusyBox-based Linux  
**Purpose:** Document environment-specific constraints and workarounds

## Python Environment

### Version
- Python 3.12.12

### Package Management
- **NO pip available**
- **NO external packages** can be installed
- Must use Python standard library only
- Exception: `statistics` module is NOT available despite being stdlib

### Standard Library Limitations
**Missing/Unavailable:**
- `statistics` module - must implement `mean()` and `median()` manually

**Available and Working:**
- `subprocess` - for btmon process management
- `re` - regex operations
- `json` - JSON parsing/serialization
- `csv` - CSV parsing
- `datetime` - timestamp handling
- `logging` - logging framework
- `threading` - thread management
- `pathlib` - path operations

## Shell Environment (BusyBox)

### BusyBox Version
Venus OS uses BusyBox ash shell with limited command set.

### Command Availability

#### DOES NOT EXIST
```bash
timeout          # No timeout command available
```

#### EXISTS BUT LIMITED

##### head / tail
**Incorrect syntax:**
```bash
head -50 file.txt        # Does NOT work
tail -100 file.txt       # Does NOT work
```

**Correct syntax:**
```bash
head -n50 file.txt       # Use -n flag
tail -n100 file.txt      # Use -n flag
head -n 50 file.txt      # Space after -n also works
```

##### ps
**Incorrect syntax:**
```bash
ps -aux                  # Does NOT work
ps aux                   # Does NOT work
```

**Correct syntax:**
```bash
ps                       # Simple ps works
ps | grep btmon          # Pipe to grep works
```

##### grep
**Works normally:**
```bash
grep pattern file
grep -i pattern file     # Case insensitive
grep -n pattern file     # Line numbers
grep -E pattern file     # Extended regex
grep -v pattern file     # Invert match
```

##### sed
**Works normally:**
```bash
sed -n '1,10p' file      # Print lines 1-10
sed 's/old/new/' file    # Substitution
```

## Bluetooth Environment

### BlueZ Version
- BlueZ 5.72

### btmon Utility
**Available and working:**
```bash
btmon                    # Monitor BLE traffic
btmon -T                 # Include timestamps
```

**Output format:** HCI Event (not MGMT Event) on Jeremy's system
```
> HCI Event: LE Meta Event (0x3e) plen 43 #1 [hci0] 2025-11-18 16:13:20.682531
      LE Advertising Report (0x02)
        ...
```

**Critical behavior:** Event name truncation
- Events #1-9: `> HCI Event: LE Meta Event (0x3e)`
- Events #10-99: `> HCI Event: LE Meta Ev.. (0x3e)`  (truncated)
- Events #100+: `> HCI Event: LE Meta E.. (0x3e)`    (more truncated)

**Solution:** Always match on `(0x3e)` hex code, not event name

### Bluetooth Commands
```bash
hciconfig                # HCI device configuration
hcitool                  # HCI tool for scanning
```

## File System

### Working Directory
- Primary: `/data/govee-ble/`
- Persistent across reboots (stored on data partition)

### Permissions
- Root access available
- Standard Unix permissions apply

## Network

### Connectivity
- SSH available
- Network accessible for remote deployment

## Process Management

### Service Management
- Venus OS uses **runit** for service management (not systemd)
- Service directories in `/service/`

### Process Control
```bash
# Check running processes
ps | grep process_name

# Kill processes
kill PID
kill -9 PID              # Force kill
```

## Development Workflow

### File Transfer
```bash
# SCP to device
scp file.py root@cerbo-gx.local:/data/govee-ble/

# SCP from device
scp root@cerbo-gx.local:/data/govee-ble/file.py ./
```

### Remote Execution
```bash
# SSH and run command
ssh root@cerbo-gx.local "python3 /data/govee-ble/script.py"

# Interactive session
ssh root@cerbo-gx.local
```

## Code Patterns for Venus OS

### Manual Statistics Functions
Since `statistics` module unavailable, implement manually:

```python
def mean(values):
    """Calculate mean of a list of numbers."""
    if not values:
        return None
    return sum(values) / len(values)

def median(values):
    """Calculate median of a list of numbers."""
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n % 2 == 0:
        return (sorted_vals[n//2 - 1] + sorted_vals[n//2]) / 2
    else:
        return sorted_vals[n//2]
```

### Subprocess Management
```python
# Start process with buffering control
process = subprocess.Popen(
    ['btmon', '-T'],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    bufsize=1,               # Line buffered
    universal_newlines=True  # Text mode
)

# Read line by line
line = process.stdout.readline()

# Clean termination
process.terminate()
process.wait(timeout=5)
```

### Time Operations Without timeout Command
```python
import time

start_time = time.time()
duration = 900  # seconds

while time.time() - start_time < duration:
    # Do work
    time.sleep(1)
```

### Safe File Operations
```python
from pathlib import Path

# Use pathlib for path operations
path = Path('/data/govee-ble/samples.json')

# Check existence
if path.exists():
    # Read file
    with open(path, 'r') as f:
        data = json.load(f)
```

## Regex Patterns for btmon

### Critical: HCI Event Detection
**Always use this pattern:**
```python
HCI_EVENT_PATTERN = re.compile(
    r'> HCI Event:.*\(0x3e\).*\[hci0\] '
    r'(\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2}:\d{2}\.\d+)'
)
```

**Never rely on event name** - it truncates after event #10

### MGMT Event Detection (Alternative Format)
```python
MGMT_EVENT_PATTERN = re.compile(
    r'@ MGMT Event:.*\(0x0012\).*\[hci0\] '
    r'(\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2}:\d{2}\.\d+)'
)
```

### Common Patterns
```python
LE_ADVERTISING_REPORT = re.compile(r'LE Advertising Report')
LE_ADDRESS_PATTERN = re.compile(r'Address: ([0-9A-Fa-f:]+)')
RSSI_PATTERN = re.compile(r'RSSI: (-?\d+) dBm')
NAME_PATTERN = re.compile(r'Name \((complete|short)\): (.+)')
COMPANY_PATTERN = re.compile(r'Company: .+ \((\d+)\)')
DATA_PATTERN = re.compile(r'^\s+Data: ([0-9a-f]+)\s*$')
```

## Testing on Venus OS

### Quick Tests
```bash
# Test parser
python3 /data/govee-ble/parser_adapter.py

# Check btmon works
ps | grep btmon

# Manual btmon check (Ctrl+C to stop)
btmon -T 2>&1 | head -n20
```

### Validation Collection
```bash
# 15-minute collection
python3 /data/govee-ble/validate_parsing_v2.py --collect \
  --macs A4:C1:38:B8:DF:A1 A4:C1:38:8E:0D:AF \
  --duration 900 \
  --output samples_$(date +%Y%m%d_%H%M).json
```

## Known Issues and Workarounds

### Issue: btmon Event Name Truncation
**Problem:** Event names truncate after many events  
**Solution:** Match on hex code `(0x3e)` not event name  
**Status:** Fixed in btmon_reader.py

### Issue: No statistics Module
**Problem:** `import statistics` fails  
**Solution:** Implement mean/median manually  
**Status:** Implemented in validate_parsing_v2.py

### Issue: No timeout Command
**Problem:** Can't use `timeout 900 command`  
**Solution:** Use Python time.time() with duration checking  
**Status:** Implemented in validation scripts

## Debugging Tips

### Check Process Status
```bash
# Find btmon
ps | grep btmon

# Check Python process
ps | grep python3
```

### Monitor btmon Output
```bash
# Live monitoring (Ctrl+C to stop)
btmon -T 2>&1 | grep -i gvh -B5 -A5

# Save to file for analysis
btmon -T > btmon_capture.txt
# Let run for 60 seconds, then Ctrl+C
```

### Check Logs
```bash
# If logging to file
tail -n50 /data/govee-ble/govee.log

# Follow log in real-time
tail -f /data/govee-ble/govee.log
```

## Performance Considerations

### BLE Advertisement Frequency
- Govee H5101 advertises approximately every 2-3 seconds
- Expect ~20-30 advertisements per minute per sensor
- 15-minute collection: ~300-450 samples per sensor

### Resource Usage
- btmon process: Minimal CPU, moderate I/O
- Python parser: Minimal CPU
- Memory: <10MB typically

## Future Considerations

### Phase 2: D-Bus Integration
Will need to investigate:
- D-Bus Python bindings availability
- Venus OS D-Bus service paths
- Temperature sensor registration
- Service management with runit

### Updates and Maintenance
- Files in `/data/` persist across Venus OS updates
- Test after Venus OS upgrades
- Consider version checking in code

## Reference Links

- Venus OS Documentation: https://github.com/victronenergy/venus/wiki
- BlueZ Documentation: http://www.bluez.org/
- BusyBox Commands: https://busybox.net/downloads/BusyBox.html

---

## Quick Reference Card

```bash
# Commands that DON'T work
timeout 60 command       # ✗ No timeout
head -50 file           # ✗ Wrong flag format  
ps -aux                 # ✗ Flags not supported

# Commands that DO work
head -n50 file          # ✓ Correct flag format
ps | grep name          # ✓ Simple ps + pipe
btmon -T                # ✓ BLE monitoring
python3 script.py       # ✓ Python 3.12.12
```

## Update History

- 2025-11-19: Initial document creation
- 2025-11-19: Added btmon truncation behavior
- 2025-11-19: Added HCI event pattern fix
