"""
Parser adapter for Govee BLE sensors.
Converts btmon advertisement data to normalized readings.

Currently supports:
- H5100, H5101, H5102, H5104, H5105 (H510x family)

Future expansion points:
- Add new model parsers to PARSER_REGISTRY
- Add new name patterns to GOVEE_NAME_PATTERNS
- Add new company IDs to GOVEE_COMPANY_IDS
"""

import struct
import logging
from typing import Optional, Dict, List
import re

PARSER_VERSION = "local_h510x_v1.1.0_h5100_h5105_support"

_LOGGER = logging.getLogger(__name__)

# Known Govee manufacturer company IDs
GOVEE_COMPANY_IDS = {
    1,    # Nokia Mobile Phones (used by Govee H510x series)
    0x0001,  # Same as above, explicit hex
}

# Govee device name patterns (regex)
GOVEE_NAME_PATTERNS = [
    re.compile(r'^GVH\d+'),      # GVH5101, GVH5075, etc.
    re.compile(r'^Govee_'),      # Govee_XXXX
    re.compile(r'^B51\d+'),      # B5178, etc.
    # Add more patterns as new models are discovered
]


def is_govee_device(name: Optional[str], manufacturer_data: Dict[int, bytes]) -> bool:
    """
    Determine if a device is a Govee sensor.
    
    Uses both name pattern matching and company ID detection.
    
    Args:
        name: Device local name or None
        manufacturer_data: Dict of company_id -> bytes
    
    Returns:
        True if device appears to be a Govee sensor
    """
    # Check company ID
    if any(cid in manufacturer_data for cid in GOVEE_COMPANY_IDS):
        return True
    
    # Check name patterns
    if name:
        for pattern in GOVEE_NAME_PATTERNS:
            if pattern.match(name):
                return True
    
    return False


def extract_model_from_name(name: Optional[str]) -> Optional[str]:
    """
    Extract model identifier from device name.
    
    Examples:
        "GVH5101_DFA1" -> "H5101"
        "GVH5075_1234" -> "H5075"
        "Govee_H5074" -> "H5074"
        "B5178_ABCD" -> "B5178"
    
    Args:
        name: Device local name
    
    Returns:
        Model string (e.g., "H5101") or None
    """
    if not name:
        return None
    
    # Pattern: GVH5101 -> H5101
    match = re.match(r'^GVH(\d+)', name)
    if match:
        return f"H{match.group(1)}"
    
    # Pattern: Govee_H5074 -> H5074
    match = re.match(r'^Govee_([HB]\d+)', name)
    if match:
        return match.group(1)
    
    # Pattern: B5178 -> B5178
    match = re.match(r'^(B\d+)', name)
    if match:
        return match.group(1)
    
    return None


def decode_temps(packet_value: int) -> float:
    """
    Decode temperature from 24-bit packed value.
    
    Based on GoveeWatcher implementation:
    https://github.com/Thrilleratplay/GoveeWatcher/issues/2
    
    Args:
        packet_value: 24-bit packed value (bytes 2-4)
    
    Returns:
        Temperature in Celsius
    """
    if packet_value & 0x800000:
        # Handle freezing temperatures (sign bit set)
        packet_value &= 0x7FFFFF  # Clear sign bit
        return float(int(packet_value / 1000) / -10)
    return float(int(packet_value / 1000) / 10)


def decode_humi(packet_value: int) -> float:
    """
    Decode humidity from 24-bit packed value.
    
    Based on GoveeWatcher implementation:
    https://github.com/Thrilleratplay/GoveeWatcher/issues/2
    
    Args:
        packet_value: 24-bit packed value (bytes 2-4)
    
    Returns:
        Humidity in percent (0-100)
    """
    # CRITICAL: Clear sign bit BEFORE calculating humidity
    packet_value &= 0x7FFFFF
    return float((packet_value % 1000) / 10)


def parse_h510x_manufacturer_data(data: bytes) -> Optional[Dict]:
    """
    Parse H510x series manufacturer data (company ID 0x0001).
    
    Supports: H5101, H5102, H5104
    
    Format (6 bytes):
        [0:1]  Marker: 0x01 0x01
        [2:4]  Packed 24-bit value containing temp and humidity
        [5]    Battery: unsigned 8-bit (0-100%)
    
    The 24-bit value in bytes [2:4] is packed as:
        bit 23: temperature sign (1=negative, 0=positive)
        bits 22-0: combined value where:
            - temperature = (value / 1000) / 10.0
            - humidity = (value % 1000) / 10.0
    
    Algorithm (from GoveeWatcher):
        https://github.com/Thrilleratplay/GoveeWatcher/issues/2

        packet_value = (byte[2] << 16) | (byte[3] << 8) | byte[4]
        temp = decode_temps(packet_value)
        humidity = decode_humi(packet_value)  # Note: uses masked value

    Args:
        data: Raw manufacturer data bytes
    
    Returns:
        Dict with temperature_c, humidity, battery, or None if invalid
    """
    if len(data) < 6:
        _LOGGER.debug(f"H510x data too short: {len(data)} bytes")
        return None
    
    # Check marker bytes
    if data[0] != 0x01 or data[1] != 0x01:
        _LOGGER.debug(f"Invalid H510x marker: {data[0]:02x} {data[1]:02x}")
        return None
    
    # Combine bytes [2:4] into 24-bit packed value
    packet_value = (data[2] << 16) | (data[3] << 8) | data[4]
    
    # Decode temperature (handles sign bit internally)
    temp_c = decode_temps(packet_value)
    
    # Decode humidity (masks sign bit internally)
    humidity = decode_humi(packet_value)
    
    # Battery: byte [5]
    battery = data[5]
    
    # Debug logging with both packet and individual bytes for analysis
    _LOGGER.debug(
        f"Raw: {data.hex()} -> packet=0x{packet_value:06x}({packet_value}), "
        f"bytes[2-4]=0x{data[2]:02x}{data[3]:02x}{data[4]:02x}, "
        f"temp={temp_c:.1f}C, hum={humidity:.1f}%, batt={battery}%"
    )
    
    # Plausibility checks
    if temp_c < -40.0 or temp_c > 85.0:
        _LOGGER.warning(f"Temperature out of plausible range: {temp_c:.1f}C")
        temp_c = None
    
    if humidity < 0.0 or humidity > 100.0:
        _LOGGER.warning(f"Humidity out of valid range: {humidity:.1f}%")
        humidity = None
    
    if battery < 0 or battery > 100:
        _LOGGER.warning(f"Battery out of valid range: {battery}%")
        battery = None
    
    return {
        'temperature_c': temp_c,
        'humidity': humidity,
        'battery': battery
    }


# Parser registry: maps model identifiers to parsing functions
PARSER_REGISTRY = {
    'H5100': parse_h510x_manufacturer_data,
    'H5101': parse_h510x_manufacturer_data,
    'H5102': parse_h510x_manufacturer_data,
    'H5104': parse_h510x_manufacturer_data,
    'H5105': parse_h510x_manufacturer_data,
}


def parse_advertisement(mac: str, name: Optional[str], rssi: Optional[int],
                       manufacturer_data: Dict[int, bytes]) -> Optional[Dict]:
    """
    Parse a complete BLE advertisement into normalized sensor reading.
    
    This is the main entry point for parsing. It:
    1. Checks if device is a Govee sensor
    2. Extracts model from name
    3. Routes to appropriate model parser
    4. Returns normalized reading
    
    Args:
        mac: Uppercase MAC address (AA:BB:CC:DD:EE:FF)
        name: Local name string or None
        rssi: RSSI value in dBm or None
        manufacturer_data: Dict of company_id -> bytes
    
    Returns:
        Normalized reading dict with keys:
            - mac: str
            - model: str or None
            - rssi: int or None
            - temperature_c: float or None
            - humidity: float or None
            - battery: int or None
        Returns None if device is not parseable or not a Govee device
    """
    # First, check if this is a Govee device
    if not is_govee_device(name, manufacturer_data):
        return None
    
    # Extract model from name
    model = extract_model_from_name(name)
    
    if not model:
        _LOGGER.debug(f"Could not extract model from name: {name}")
        return None
    
    # Check if we have a parser for this model
    if model not in PARSER_REGISTRY:
        _LOGGER.debug(f"No parser available for model: {model}")
        return None
    
    # Get manufacturer data for known Govee company IDs
    mfr_data = None
    for company_id in GOVEE_COMPANY_IDS:
        if company_id in manufacturer_data:
            mfr_data = manufacturer_data[company_id]
            break
    
    if not mfr_data:
        _LOGGER.debug(f"No Govee manufacturer data found for {mac} ({name})")
        return None
    
    # Parse with appropriate parser
    parser_func = PARSER_REGISTRY[model]
    result = parser_func(mfr_data)
    
    if result is None:
        return None
    
    # Add metadata
    result['mac'] = mac
    result['model'] = model
    result['rssi'] = rssi
    
    return result


def smoke_test() -> bool:
    """
    Self-check parser with known test samples.

    Raises:
        AssertionError: If any test fails
    
    Returns:
        True if all tests pass
    """
    _LOGGER.info("Running parser smoke test...")
    
    # Test 1: Freezer data
    # Raw: 0101827a853f
    # Expected: temp=-16.2C, humidity=43.7%, battery=63%
    test1_data = bytes.fromhex("0101827a853f")
    result1 = parse_h510x_manufacturer_data(test1_data)

    assert result1 is not None, "Test 1: Parser returned None"

    assert result1['temperature_c'] is not None, "Test 1: Temperature is None"
    assert -17.0 <= result1['temperature_c'] <= -15.5, \
        f"Test 1: Temperature {result1['temperature_c']:.1f}C not in expected range"

    assert result1['humidity'] is not None, "Test 1: Humidity is None"
    assert 40.0 <= result1['humidity'] <= 47.0, \
        f"Test 1: Humidity {result1['humidity']:.1f}% not in expected range"

    assert result1['battery'] == 63, \
        f"Test 1: Battery {result1['battery']}% != 63%"

    _LOGGER.info(
        f"Test 1 passed: Freezer data - "
        f"temp={result1['temperature_c']:.1f}C, "
        f"hum={result1['humidity']:.1f}%, "
        f"batt={result1['battery']}%"
    )
    
    # Test 2: Fridge data
    # Raw: 010100b8eb49
    # Expected: temp=4.7C, humidity=33.9%, battery=73%
    test2_data = bytes.fromhex("010100b8eb49")
    result2 = parse_h510x_manufacturer_data(test2_data)

    assert result2 is not None, "Test 2: Parser returned None"

    assert result2['temperature_c'] is not None, "Test 2: Temperature is None"
    assert 4.0 <= result2['temperature_c'] <= 5.5, \
        f"Test 2: Temperature {result2['temperature_c']:.1f}C not in expected range"

    assert result2['humidity'] is not None, "Test 2: Humidity is None"
    assert 30.0 <= result2['humidity'] <= 37.0, \
        f"Test 2: Humidity {result2['humidity']:.1f}% not in expected range"

    assert result2['battery'] == 73, \
        f"Test 2: Battery {result2['battery']}% != 73%"

    _LOGGER.info(
        f"Test 2 passed: Fridge data - "
        f"temp={result2['temperature_c']:.1f}C, "
        f"hum={result2['humidity']:.1f}%, "
        f"batt={result2['battery']}%"
    )
    
    # Test 3: Invalid marker rejection
    test3_data = bytes.fromhex("0201827a853f")  # Wrong first marker
    result3 = parse_h510x_manufacturer_data(test3_data)
    assert result3 is None, "Test 3: Should reject invalid marker"
    _LOGGER.info("Test 3 passed: Invalid marker rejected")
    
    # Test 4: Short data rejection
    test4_data = bytes.fromhex("0101827a")  # Only 4 bytes
    result4 = parse_h510x_manufacturer_data(test4_data)
    assert result4 is None, "Test 4: Should reject short data"
    _LOGGER.info("Test 4 passed: Short data rejected")
    
    _LOGGER.info("All smoke tests PASSED!")
    return True


def get_supported_models() -> List[str]:
    """
    Get list of currently supported models.
    
    Returns:
        List of model identifiers (e.g., ['H5101', 'H5102', 'H5104'])
    """
    return sorted(PARSER_REGISTRY.keys())


if __name__ == "__main__":
    # Run smoke test when executed directly
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s.%(msecs)03dZ %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )
    
    try:
        smoke_test()
        print("\n" + "="*60)
        print(f"Parser version: {PARSER_VERSION}")
        print(f"Supported models: {', '.join(get_supported_models())}")
        print("="*60)
    except AssertionError as e:
        _LOGGER.error(f"Smoke test FAILED: {e}")
        exit(1)
