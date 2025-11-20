"""
btmon reader for Govee BLE sensors.

Spawns btmon -T and parses output to assemble complete BLE advertisements.
Handles MGMT Event format with proper timestamp parsing and midnight rollover.
"""

import subprocess
import logging
import re
import time
import datetime
from typing import Optional, Dict, Callable, Tuple
from collections import defaultdict

_LOGGER = logging.getLogger(__name__)


class BtmonWatchdog:
    """Detect btmon stalls and trigger restart."""
    
    def __init__(self, stall_timeout_sec: int = 180, heartbeat_interval_sec: int = 60):
        """
        Initialize watchdog.
        
        Args:
            stall_timeout_sec: Exit if no btmon output for this many seconds
            heartbeat_interval_sec: Log heartbeat every N seconds
        """
        self.stall_timeout = stall_timeout_sec
        self.heartbeat_interval = heartbeat_interval_sec
        self.last_line_time = time.time()
        self.last_heartbeat = time.time()
    
    def reset(self):
        """Call when btmon produces a line."""
        self.last_line_time = time.time()
    
    def check(self):
        """
        Check if btmon has stalled.
        
        Raises:
            SystemExit: If btmon has stalled beyond timeout
        """
        now = time.time()
        
        # Heartbeat
        if now - self.last_heartbeat > self.heartbeat_interval:
            elapsed = int(now - self.last_line_time)
            _LOGGER.debug(f"Watchdog heartbeat: last btmon line {elapsed}s ago")
            self.last_heartbeat = now
        
        # Stall detection
        if now - self.last_line_time > self.stall_timeout:
            _LOGGER.error(
                f"btmon stalled: no output for {self.stall_timeout}s. "
                f"Exiting for runit restart."
            )
            raise SystemExit(1)


class AdvertisementAssembler:
    """
    Assemble complete advertisement reports from btmon output.
    
    btmon -T produces MGMT Event blocks that look like:
    
    @ MGMT Event: Device Found (0x0012) plen 45  {0x0001} [hci0] 2025-11-12 06:54:31.955895
            LE Address: A4:C1:38:B8:DF:A1 (OUI A4-C1-38)
            RSSI: -76 dBm (0xb4)
            Flags: 0x00000000
            Data length: 31
            Name (complete): GVH5101_DFA1
            16-bit Service UUIDs (complete): 1 entry
              Unknown (0xec88)
            Flags: 0x05
              LE Limited Discoverable Mode
              BR/EDR Not Supported
            Company: Nokia Mobile Phones (1)
              Data: 010100b8eb49
    
    We extract: MAC, Name, RSSI, Company ID -> Data
    """
    
    # Regex patterns for parsing btmon output
    # Supports both formats:
    # - MGMT Event: @ MGMT Event: Device Found (0x0012) [hci0] timestamp
    # - HCI Event: > HCI Event with (0x3e) [hci0] timestamp
    MGMT_EVENT_PATTERN = re.compile(r'@ MGMT Event:.*\(0x0012\).*\[hci0\] (\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2}:\d{2}\.\d+)')
    HCI_EVENT_PATTERN = re.compile(r'> HCI Event:.*\(0x3e\).*\[hci0\] (\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2}:\d{2}\.\d+)')
    LE_ADVERTISING_REPORT = re.compile(r'LE Advertising Report')
    LE_ADDRESS_PATTERN = re.compile(r'Address: ([0-9A-Fa-f:]+)')
    RSSI_PATTERN = re.compile(r'RSSI: (-?\d+) dBm')
    NAME_PATTERN = re.compile(r'Name \((complete|short)\): (.+)')
    COMPANY_PATTERN = re.compile(r'Company: .+ \((\d+)\)')
    DATA_PATTERN = re.compile(r'^\s+Data: ([0-9a-f]+)\s*$')
    
    def __init__(self):
        """Initialize assembler with date tracking for timestamp parsing."""
        self.current_date = datetime.date.today()
        self.last_time = None
        self.current_event = None
        self.current_company_id = None
    
    def parse_timestamp(self, date_str: Optional[str], time_str: str) -> datetime.datetime:
        """
        Parse timestamp from btmon -T output and handle midnight rollover.
        
        btmon -T can output:
        - Just time: "19:20:03.134837"
        - Date + time: "2025-11-12 19:20:03.134837"
        
        We track date separately when not provided and detect midnight rollover.
        
        Args:
            date_str: Optional date string like "2025-11-12 "
            time_str: Time string like "19:20:03.134837"
        
        Returns:
            datetime object with proper date
        """
        # Parse time
        time_obj = datetime.datetime.strptime(time_str, '%H:%M:%S.%f').time()
        
        # Use provided date if available
        if date_str:
            date_part = datetime.datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
            self.current_date = date_part
        else:
            # Detect midnight rollover
            if self.last_time and time_obj.hour < self.last_time.hour:
                self.current_date += datetime.timedelta(days=1)
                _LOGGER.info(f"Detected midnight rollover, date now: {self.current_date}")
        
        timestamp = datetime.datetime.combine(self.current_date, time_obj)
        self.last_time = timestamp
        return timestamp
    
    def process_line(self, line: str) -> Optional[Dict]:
        """
        Process a single line from btmon output.
        
        Supports both MGMT Event and HCI Event formats.
        
        Args:
            line: One line from btmon
        
        Returns:
            Complete advertisement dict if event is complete, else None
        """
        line = line.rstrip()
        
        # Check for new MGMT Event (format 1)
        match = self.MGMT_EVENT_PATTERN.search(line)
        if match:
            # If we have a pending event, yield it (incomplete)
            result = None
            if self.current_event:
                result = self._finalize_event()
            
            # Start new event
            timestamp = self.parse_timestamp(match.group(1), match.group(2))
            self.current_event = {
                'timestamp': timestamp,
                'mac': None,
                'name': None,
                'rssi': None,
                'manufacturer_data': {}
            }
            self.current_company_id = None
            _LOGGER.debug(f"Started new MGMT event at {timestamp}")
            return result
        
        # Check for new HCI Event (format 2)
        match = self.HCI_EVENT_PATTERN.search(line)
        if match:
            # If we have a pending event, yield it (incomplete)
            result = None
            if self.current_event:
                result = self._finalize_event()
            
            # Start new event
            timestamp = self.parse_timestamp(match.group(1), match.group(2))
            self.current_event = {
                'timestamp': timestamp,
                'mac': None,
                'name': None,
                'rssi': None,
                'manufacturer_data': {},
                'is_hci_format': True
            }
            self.current_company_id = None
            _LOGGER.debug(f"Started new HCI event at {timestamp}")
            return result
        
        # Check for LE Advertising Report (confirms HCI format)
        if self.LE_ADVERTISING_REPORT.search(line):
            if self.current_event:
                self.current_event['confirmed_advertising'] = True
            return None
        
        # If no current event, ignore line
        if not self.current_event:
            return None
        
        # Parse Address (both formats use "Address:" but HCI might not have "LE" prefix)
        match = self.LE_ADDRESS_PATTERN.search(line)
        if match:
            self.current_event['mac'] = match.group(1).upper()
            return None
        
        # Parse RSSI
        match = self.RSSI_PATTERN.search(line)
        if match:
            self.current_event['rssi'] = int(match.group(1))
            return None
        
        # Parse Name
        match = self.NAME_PATTERN.search(line)
        if match:
            self.current_event['name'] = match.group(2).strip()
            return None
        
        # Parse Company ID
        match = self.COMPANY_PATTERN.search(line)
        if match:
            self.current_company_id = int(match.group(1))
            return None
        
        # Parse Data (follows Company line)
        if self.current_company_id is not None:
            match = self.DATA_PATTERN.match(line)
            if match:
                data_hex = match.group(1)
                data_bytes = bytes.fromhex(data_hex)
                # Store manufacturer data (overwrite if multiple Data lines for same company)
                self.current_event['manufacturer_data'][self.current_company_id] = data_bytes
                self.current_company_id = None  # Reset after data line
                return None
        
        return None
    
    def _finalize_event(self) -> Optional[Dict]:
        """
        Finalize current event and return if valid.
        
        Returns:
            Event dict if MAC is present, else None
        """
        if not self.current_event:
            return None
        
        event = self.current_event
        self.current_event = None
        
        # Must have at least a MAC address
        if not event['mac']:
            return None
        
        return event


class BtmonReader:
    """
    Spawns and manages btmon process, assembling advertisements.
    """
    
    def __init__(self, 
                 interface: str = "hci0",
                 stall_timeout_sec: int = 180,
                 advertisement_callback: Optional[Callable[[Dict], None]] = None):
        """
        Initialize btmon reader.
        
        Args:
            interface: HCI interface (e.g., "hci0")
            stall_timeout_sec: Watchdog timeout
            advertisement_callback: Function to call with complete advertisements
        """
        self.interface = interface
        self.advertisement_callback = advertisement_callback
        self.watchdog = BtmonWatchdog(stall_timeout_sec=stall_timeout_sec)
        self.assembler = AdvertisementAssembler()
        self.btmon_process = None
        self.running = False
        
        # Statistics
        self.stats = {
            'advertisements': 0,
            'lines_processed': 0,
            'start_time': None
        }
    
    def start(self):
        """Start btmon process and begin reading."""
        if self.running:
            _LOGGER.warning("BtmonReader already running")
            return
        
        _LOGGER.info(f"Starting btmon reader on {self.interface}")
        
        try:
            # Spawn btmon with timestamp flag
            self.btmon_process = subprocess.Popen(
                ['btmon', '-T'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            self.running = True
            self.stats['start_time'] = time.time()
            
            _LOGGER.info(f"btmon process started (PID {self.btmon_process.pid})")
            
            # Read loop
            self._read_loop()
            
        except FileNotFoundError:
            _LOGGER.error("btmon not found - is bluez-utils installed?")
            raise
        except Exception as e:
            _LOGGER.error(f"Failed to start btmon: {e}")
            raise
    
    def _read_loop(self):
        """Main read loop - processes btmon output line by line."""
        _LOGGER.info("Entering btmon read loop")
        
        line_count = 0
        event_count = 0
        
        while self.running:
            try:
                # Read line with timeout
                line = self.btmon_process.stdout.readline()
                
                if not line:
                    # EOF - btmon died
                    _LOGGER.error("btmon process ended unexpectedly")
                    break
                
                # Reset watchdog
                self.watchdog.reset()
                self.stats['lines_processed'] += 1
                line_count += 1
                
                # Log first few lines for debugging
                if line_count <= 5:
                    _LOGGER.debug(f"btmon line {line_count}: {line.rstrip()}")
                
                # Process line
                advertisement = self.assembler.process_line(line)
                
                if advertisement:
                    self.stats['advertisements'] += 1
                    event_count += 1
                    _LOGGER.info(
                        f"Advertisement #{event_count} from {advertisement['mac']} "
                        f"({advertisement.get('name', 'unknown')})"
                    )
                    
                    # Callback
                    if self.advertisement_callback:
                        try:
                            self.advertisement_callback(advertisement)
                        except Exception as e:
                            _LOGGER.error(f"Callback error: {e}", exc_info=True)
                
                # Check watchdog periodically (every ~100 lines)
                if self.stats['lines_processed'] % 100 == 0:
                    self.watchdog.check()
                
            except KeyboardInterrupt:
                _LOGGER.info("Keyboard interrupt received")
                break
            except SystemExit:
                # Watchdog triggered
                raise
            except Exception as e:
                _LOGGER.error(f"Error in read loop: {e}", exc_info=True)
                time.sleep(1)
        
        self._cleanup()
    
    def _cleanup(self):
        """Clean up btmon process."""
        self.running = False
        
        if self.btmon_process:
            _LOGGER.info("Stopping btmon process")
            try:
                self.btmon_process.terminate()
                self.btmon_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _LOGGER.warning("btmon didn't terminate, killing")
                self.btmon_process.kill()
                self.btmon_process.wait()
            
            self.btmon_process = None
        
        # Log statistics
        if self.stats['start_time']:
            runtime = time.time() - self.stats['start_time']
            _LOGGER.info(
                f"BtmonReader stopped - Runtime: {runtime:.1f}s, "
                f"Lines: {self.stats['lines_processed']}, "
                f"Advertisements: {self.stats['advertisements']}"
            )
    
    def stop(self):
        """Request reader to stop."""
        _LOGGER.info("Stop requested")
        self.running = False


def main():
    """Test btmon reader standalone."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03dZ %(levelname)s [%(name)s:%(funcName)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )
    
    def print_advertisement(adv: Dict):
        """Print advertisement in readable format."""
        print(f"\n{'='*60}")
        print(f"Timestamp: {adv['timestamp']}")
        print(f"MAC: {adv['mac']}")
        print(f"Name: {adv.get('name', 'N/A')}")
        print(f"RSSI: {adv.get('rssi', 'N/A')} dBm")
        print(f"Manufacturer Data:")
        for company_id, data in adv['manufacturer_data'].items():
            print(f"  Company {company_id}: {data.hex()}")
        print(f"{'='*60}")
    
    reader = BtmonReader(advertisement_callback=print_advertisement)
    
    try:
        reader.start()
    except KeyboardInterrupt:
        print("\nStopping...")
        reader.stop()


if __name__ == "__main__":
    main()
