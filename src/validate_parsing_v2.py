"""
Enhanced validation tool for Govee BLE parsing with 1-minute resolution handling.

This version accounts for the fact that the Govee app exports data at 1-minute
resolution, while our btmon samples can be collected at any interval.

Strategy:
1. Collect btmon samples over an extended period (e.g., 10+ minutes)
2. Group our samples into 1-minute windows matching app export times
3. For each 1-minute window, use the last sample (or average, configurable)
4. Compare windowed samples against app export

Usage:
    # Collect samples for 15 minutes
    python3 validate_parsing_v2.py --collect \\
      --macs A4:C1:38:B8:DF:A1 A4:C1:38:8E:0D:AF \\
      --duration 900 \\
      --output samples_$(date +%Y%m%d_%H%M).json
    
    # Compare against app export (handles 1-minute resolution)
    python3 validate_parsing_v2.py --compare \\
      samples_20251114_1930.json \\
      Refrigerator_export.csv Freezer_export.csv \\
      --timezone-offset -6
"""

import sys
import argparse
import logging
import json
import csv
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Statistics functions (Venus OS compatible - no external deps)
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

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import parser_adapter
import btmon_reader

_LOGGER = logging.getLogger(__name__)


class SampleCollector:
    """Collect samples from btmon with timestamps."""
    
    def __init__(self, target_macs: Optional[List[str]] = None):
        """
        Initialize sample collector.
        
        Args:
            target_macs: List of MACs to collect (None = all Govee devices)
        """
        self.target_macs = [mac.upper() for mac in (target_macs or [])]
        self.samples = defaultdict(list)
        self.total_collected = 0
    
    def process_advertisement(self, adv: Dict):
        """Process advertisement and collect if relevant."""
        mac = adv['mac']
        
        # If we have target MACs, only collect those
        if self.target_macs and mac not in self.target_macs:
            return
        
        # Parse advertisement
        result = parser_adapter.parse_advertisement(
            mac=mac,
            name=adv.get('name'),
            rssi=adv.get('rssi'),
            manufacturer_data=adv.get('manufacturer_data', {})
        )
        
        if not result:
            return
        
        # Add sample with timestamp and raw data
        sample = {
            'timestamp': adv['timestamp'].isoformat(),
            'mac': mac,
            'model': result.get('model'),
            'rssi': result.get('rssi'),
            'temperature_c': result.get('temperature_c'),
            'humidity': result.get('humidity'),
            'battery': result.get('battery'),
            'raw_manufacturer_data': {
                str(k): v.hex() for k, v in adv.get('manufacturer_data', {}).items()
            }
        }
        
        self.samples[mac].append(sample)
        self.total_collected += 1
        
        if self.total_collected % 10 == 0:
            _LOGGER.info(
                f"Collected {self.total_collected} total samples "
                f"({len(self.samples)} unique sensors)"
            )
    
    def get_samples_dict(self) -> Dict:
        """Get samples as dictionary."""
        return dict(self.samples)
    
    def save_to_file(self, filepath: Path):
        """Save samples to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.get_samples_dict(), f, indent=2)
        _LOGGER.info(
            f"Saved {sum(len(v) for v in self.samples.values())} samples "
            f"from {len(self.samples)} sensors to {filepath}"
        )


def collect_samples(duration_sec: int, 
                   target_macs: Optional[List[str]] = None) -> Dict:
    """
    Collect samples from btmon for specified duration.
    
    Args:
        duration_sec: How long to collect (seconds)
        target_macs: List of MACs to collect (None = all)
    
    Returns:
        Dict of MAC -> list of samples
    """
    _LOGGER.info(f"Starting sample collection for {duration_sec}s ({duration_sec//60} minutes)...")
    _LOGGER.info("Collection will continue until duration expires or Ctrl+C")
    
    collector = SampleCollector(target_macs=target_macs)
    
    reader = btmon_reader.BtmonReader(
        advertisement_callback=collector.process_advertisement
    )
    
    # Start collection in a thread
    import threading
    reader_thread = threading.Thread(target=reader.start, daemon=True)
    reader_thread.start()
    
    # Wait for duration
    start_time = time.time()
    try:
        while time.time() - start_time < duration_sec:
            remaining = duration_sec - (time.time() - start_time)
            if remaining > 0 and int(remaining) % 60 == 0:
                _LOGGER.info(f"{int(remaining//60)} minutes remaining...")
            time.sleep(1)
        _LOGGER.info("Collection duration complete")
    except KeyboardInterrupt:
        _LOGGER.info("Collection interrupted by user")
    finally:
        reader.stop()
    
    return collector.get_samples_dict()


def parse_govee_app_export(filepath: Path, timezone_offset_hours: int = -6) -> Dict[str, List[Dict]]:
    """
    Parse Govee app CSV export and convert to UTC.
    
    Govee app format:
        Timestamp for sample frequency every 1 min min, Temperature_Celsius,Relative_Humidity
        2025-11-12 19:19:00,5.3,40.6
        2025-11-12 19:20:00,5.2,39.3
    
    Args:
        filepath: Path to CSV file
        timezone_offset_hours: Offset from UTC (e.g., CST = -6)
    
    Returns:
        Dict of MAC -> list of readings (in UTC)
    """
    samples = []
    
    # Try to extract MAC from filename
    filename = filepath.stem.lower()
    mac = None
    
    # You can add your MAC mappings here or pass them as parameter
    # For now, we'll use the filename as an identifier
    sensor_name = filepath.stem
    
    _LOGGER.info(f"Parsing {filepath.name} as sensor '{sensor_name}'")
    
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        
        # Skip header line
        header = next(reader, None)
        if header:
            _LOGGER.debug(f"CSV header: {header}")
        
        line_num = 1
        for row in reader:
            line_num += 1
            if len(row) < 3:
                _LOGGER.debug(f"Line {line_num}: Skipping short row: {row}")
                continue
            
            try:
                # Parse timestamp (local time from Govee app)
                timestamp_str = row[0].strip()
                try:
                    local_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        local_time = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S')
                    except ValueError:
                        _LOGGER.warning(f"Line {line_num}: Could not parse timestamp: {timestamp_str}")
                        continue
                
                # Convert from local time to UTC
                utc_time = local_time + timedelta(hours=-timezone_offset_hours)
                
                # Parse values
                sample = {
                    'timestamp': utc_time,
                    'timestamp_str': utc_time.isoformat(),
                    'timestamp_local': local_time.isoformat(),
                    'temperature_c': float(row[1]),
                    'humidity': float(row[2]),
                    'battery': None,  # Not in CSV
                    'sensor_name': sensor_name
                }
                samples.append(sample)
                
            except (ValueError, IndexError) as e:
                _LOGGER.warning(f"Line {line_num}: Could not parse row: {row} - {e}")
                continue
    
    _LOGGER.info(f"Loaded {len(samples)} samples from {filepath}")
    return {sensor_name: samples}


def window_samples_by_minute(samples: List[Dict], strategy: str = 'last') -> Dict[datetime, Dict]:
    """
    Group samples into 1-minute windows.
    
    Args:
        samples: List of samples with timestamps
        strategy: How to aggregate samples in each window
            - 'last': Use the last sample in the window (default)
            - 'first': Use the first sample in the window
            - 'average': Average all samples in the window
            - 'median': Use median of samples in the window
    
    Returns:
        Dict mapping minute timestamps to aggregated sample
    """
    if not samples:
        return {}
    
    # Group samples by minute
    by_minute = defaultdict(list)
    for sample in samples:
        ts = datetime.fromisoformat(sample['timestamp'])
        # Round down to the minute
        minute = ts.replace(second=0, microsecond=0)
        by_minute[minute].append(sample)
    
    # Aggregate each minute
    windowed = {}
    for minute, minute_samples in by_minute.items():
        if strategy == 'last':
            windowed[minute] = minute_samples[-1]
        elif strategy == 'first':
            windowed[minute] = minute_samples[0]
        elif strategy == 'average':
            # Average temperature, humidity
            temps = [s['temperature_c'] for s in minute_samples if s['temperature_c'] is not None]
            hums = [s['humidity'] for s in minute_samples if s['humidity'] is not None]
            batts = [s['battery'] for s in minute_samples if s['battery'] is not None]
            
            windowed[minute] = {
                'timestamp': minute.isoformat(),
                'mac': minute_samples[0]['mac'],
                'model': minute_samples[0]['model'],
                'temperature_c': mean(temps) if temps else None,
                'humidity': mean(hums) if hums else None,
                'battery': int(mean(batts)) if batts else None,
                'sample_count': len(minute_samples),
                'raw_manufacturer_data': minute_samples[0].get('raw_manufacturer_data', {})
            }
        elif strategy == 'median':
            temps = [s['temperature_c'] for s in minute_samples if s['temperature_c'] is not None]
            hums = [s['humidity'] for s in minute_samples if s['humidity'] is not None]
            batts = [s['battery'] for s in minute_samples if s['battery'] is not None]
            
            windowed[minute] = {
                'timestamp': minute.isoformat(),
                'mac': minute_samples[0]['mac'],
                'model': minute_samples[0]['model'],
                'temperature_c': median(temps) if temps else None,
                'humidity': median(hums) if hums else None,
                'battery': int(median(batts)) if batts else None,
                'sample_count': len(minute_samples),
                'raw_manufacturer_data': minute_samples[0].get('raw_manufacturer_data', {})
            }
    
    return windowed


def compare_windowed_samples(our_samples: Dict, app_samples: Dict, 
                             mac_to_sensor_name: Dict[str, str],
                             strategy: str = 'last',
                             tolerance_temp: float = 1.0,
                             tolerance_humidity: float = 5.0,
                             time_window_sec: int = 30) -> Tuple[bool, List[Dict]]:
    """
    Compare our samples against app export using 1-minute windowing.
    
    Args:
        our_samples: Our collected samples (MAC -> list)
        app_samples: Govee app export samples (sensor_name -> list)
        mac_to_sensor_name: Map MAC addresses to sensor names in app export
        strategy: Windowing strategy ('last', 'first', 'average', 'median')
        tolerance_temp: Max temperature difference (Â°C)
        tolerance_humidity: Max humidity difference (%)
        time_window_sec: Max time difference for matching (seconds)
    
    Returns:
        Tuple of (all_passed, list of comparison results)
    """
    all_passed = True
    comparisons = []
    
    for mac, our_readings in our_samples.items():
        sensor_name = mac_to_sensor_name.get(mac)
        if not sensor_name or sensor_name not in app_samples:
            _LOGGER.warning(f"MAC {mac} not mapped to sensor name or not in app export")
            continue
        
        app_readings = app_samples[sensor_name]
        
        print(f"\n{'='*70}")
        print(f"Comparing MAC: {mac} â†’ Sensor: {sensor_name}")
        print(f"  Our samples: {len(our_readings)}")
        print(f"  App samples: {len(app_readings)}")
        print(f"  Windowing strategy: {strategy}")
        print(f"{'='*70}\n")
        
        # Window our samples to 1-minute resolution
        windowed = window_samples_by_minute(our_readings, strategy=strategy)
        
        _LOGGER.info(f"Windowed {len(our_readings)} samples into {len(windowed)} minute bins")
        
        # Compare each app reading with our windowed data
        for app_reading in app_readings:
            app_time = app_reading['timestamp']
            
            # Find our windowed sample closest to this timestamp
            closest_time = None
            min_diff = float('inf')
            for our_time in windowed.keys():
                diff = abs((our_time - app_time).total_seconds())
                if diff < min_diff:
                    min_diff = diff
                    closest_time = our_time
            
            if closest_time is None or min_diff > time_window_sec:
                _LOGGER.warning(
                    f"No matching sample found for app time {app_time} "
                    f"(closest was {min_diff:.0f}s away)"
                )
                continue
            
            our_reading = windowed[closest_time]
            
            # Compare values
            temp_diff = abs(our_reading['temperature_c'] - app_reading['temperature_c'])
            humidity_diff = abs(our_reading['humidity'] - app_reading['humidity'])
            
            temp_ok = temp_diff <= tolerance_temp
            humidity_ok = humidity_diff <= tolerance_humidity
            
            status = "âœ“ PASS" if (temp_ok and humidity_ok) else "âœ— FAIL"
            
            comparison = {
                'mac': mac,
                'sensor_name': sensor_name,
                'app_time': app_reading['timestamp_local'],
                'our_time': our_reading['timestamp'],
                'time_diff_sec': min_diff,
                'temp_our': our_reading['temperature_c'],
                'temp_app': app_reading['temperature_c'],
                'temp_diff': temp_diff,
                'temp_ok': temp_ok,
                'hum_our': our_reading['humidity'],
                'hum_app': app_reading['humidity'],
                'hum_diff': humidity_diff,
                'hum_ok': humidity_ok,
                'overall_ok': temp_ok and humidity_ok,
                'raw_data': our_reading.get('raw_manufacturer_data', {})
            }
            comparisons.append(comparison)
            
            print(f"{status} | App time: {app_reading['timestamp_local']}, Time diff: {min_diff:.0f}s")
            print(f"  Temperature: {our_reading['temperature_c']:.1f}Â°C vs {app_reading['temperature_c']:.1f}Â°C "
                  f"(diff: {temp_diff:.2f}Â°C) {'âœ“' if temp_ok else 'âœ—'}")
            print(f"  Humidity:    {our_reading['humidity']:.1f}% vs {app_reading['humidity']:.1f}% "
                  f"(diff: {humidity_diff:.2f}%) {'âœ“' if humidity_ok else 'âœ—'}")
            if hasattr(our_reading, '__getitem__') and 'sample_count' in our_reading:
                print(f"  (Aggregated from {our_reading['sample_count']} samples)")
            # Show raw data if available
            if 'raw_manufacturer_data' in our_reading:
                raw = our_reading['raw_manufacturer_data']
                if raw:
                    print(f"  Raw data: {raw}")
            print()
            
            if not (temp_ok and humidity_ok):
                all_passed = False
    
    return all_passed, comparisons


def main():
    parser = argparse.ArgumentParser(
        description='Enhanced Govee BLE validation with 1-minute resolution handling'
    )
    parser.add_argument('--collect', action='store_true',
                       help='Collect samples from live btmon')
    parser.add_argument('--duration', type=int, default=900,
                       help='Collection duration in seconds (default: 900 = 15 minutes)')
    parser.add_argument('--macs', nargs='+',
                       help='Target MAC addresses (space-separated)')
    parser.add_argument('--output', type=Path,
                       help='Save collected samples to JSON file')
    parser.add_argument('--compare', nargs='+', metavar='FILE',
                       help='Compare: <our_json> <app_csv1> [app_csv2 ...]')
    parser.add_argument('--mac-mapping', nargs='+', metavar='MAC:NAME',
                       help='Map MACs to sensor names (e.g., AA:BB:CC:DD:EE:FF:Refrigerator)')
    parser.add_argument('--strategy', choices=['last', 'first', 'average', 'median'],
                       default='last',
                       help='Windowing strategy for multiple samples per minute (default: last)')
    parser.add_argument('--timezone-offset', type=int, default=-6,
                       help='App timezone offset from UTC in hours (default: -6 for CST)')
    parser.add_argument('--temp-tolerance', type=float, default=1.0,
                       help='Temperature tolerance in Â°C (default: 1.0)')
    parser.add_argument('--humidity-tolerance', type=float, default=5.0,
                       help='Humidity tolerance in %% (default: 5.0)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s.%(msecs)03dZ %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )
    
    # Run parser smoke test first
    print("Running parser smoke test...")
    try:
        parser_adapter.smoke_test()
        print("âœ“ Parser smoke test passed\n")
    except AssertionError as e:
        print(f"âœ— Parser smoke test FAILED: {e}")
        return 1
    
    if args.collect:
        # Collect samples
        samples = collect_samples(
            duration_sec=args.duration,
            target_macs=args.macs
        )
        
        # Display summary
        print(f"\n{'='*70}")
        print("COLLECTION SUMMARY")
        print(f"{'='*70}")
        for mac, readings in samples.items():
            print(f"\n{mac}: {len(readings)} samples")
            if readings:
                first = readings[0]
                last = readings[-1]
                print(f"  First: {first['timestamp']} - "
                      f"T:{first['temperature_c']:.1f}Â°C, "
                      f"H:{first['humidity']:.1f}%, "
                      f"B:{first['battery']}%")
                print(f"  Last:  {last['timestamp']} - "
                      f"T:{last['temperature_c']:.1f}Â°C, "
                      f"H:{last['humidity']:.1f}%, "
                      f"B:{last['battery']}%")
        
        # Save if requested
        if args.output:
            collector = SampleCollector()
            collector.samples = samples
            collector.save_to_file(args.output)
    
    if args.compare:
        if len(args.compare) < 2:
            print("Error: --compare requires at least 2 files: <our_json> <app_csv>")
            return 1
        
        our_json = args.compare[0]
        app_csvs = args.compare[1:]
        
        # Load our samples
        with open(our_json, 'r') as f:
            our_samples = json.load(f)
        
        # Parse MAC mapping if provided
        mac_to_sensor = {}
        if args.mac_mapping:
            for mapping in args.mac_mapping:
                if ':' not in mapping:
                    print(f"Warning: Invalid mapping format: {mapping}")
                    continue
                parts = mapping.rsplit(':', 1)
                if len(parts) == 2:
                    # Last colon separates MAC from name
                    mac_part = mapping[:mapping.rfind(':')]
                    name = mapping[mapping.rfind(':')+1:]
                    mac_to_sensor[mac_part.upper()] = name
        
        # If no mapping provided, try to infer from filenames
        if not mac_to_sensor and len(our_samples) == len(app_csvs):
            macs = sorted(our_samples.keys())
            for i, csv_path in enumerate(app_csvs):
                sensor_name = Path(csv_path).stem
                if i < len(macs):
                    mac_to_sensor[macs[i]] = sensor_name
                    _LOGGER.info(f"Auto-mapped {macs[i]} â†’ {sensor_name}")
        
        if not mac_to_sensor:
            print("\nError: MAC to sensor name mapping required!")
            print("Use --mac-mapping MAC:SensorName (e.g., AA:BB:CC:DD:EE:FF:Refrigerator)")
            return 1
        
        # Load app samples
        app_samples = {}
        for csv_path in app_csvs:
            samples_dict = parse_govee_app_export(
                Path(csv_path), 
                timezone_offset_hours=args.timezone_offset
            )
            app_samples.update(samples_dict)
        
        # Compare
        passed, comparisons = compare_windowed_samples(
            our_samples=our_samples,
            app_samples=app_samples,
            mac_to_sensor_name=mac_to_sensor,
            strategy=args.strategy,
            tolerance_temp=args.temp_tolerance,
            tolerance_humidity=args.humidity_tolerance
        )
        
        # Summary statistics
        if comparisons:
            print(f"\n{'='*70}")
            print("COMPARISON SUMMARY")
            print(f"{'='*70}")
            
            total = len(comparisons)
            temp_pass = sum(1 for c in comparisons if c['temp_ok'])
            hum_pass = sum(1 for c in comparisons if c['hum_ok'])
            overall_pass = sum(1 for c in comparisons if c['overall_ok'])
            
            avg_temp_diff = mean([c['temp_diff'] for c in comparisons])
            avg_hum_diff = mean([c['hum_diff'] for c in comparisons])
            
            print(f"Total comparisons: {total}")
            print(f"Temperature: {temp_pass}/{total} passed ({100*temp_pass/total:.1f}%)")
            print(f"Humidity: {hum_pass}/{total} passed ({100*hum_pass/total:.1f}%)")
            print(f"Overall: {overall_pass}/{total} passed ({100*overall_pass/total:.1f}%)")
            print(f"\nAverage differences:")
            print(f"  Temperature: {avg_temp_diff:.2f}Â°C")
            print(f"  Humidity: {avg_hum_diff:.2f}%")
            
            print(f"\n{'='*70}")
            if passed:
                print("âœ“ ALL COMPARISONS PASSED")
            else:
                print("âœ— SOME COMPARISONS FAILED")
            print(f"{'='*70}")
        
        return 0 if passed else 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
