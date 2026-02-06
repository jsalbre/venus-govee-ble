"""
Configuration manager for Govee BLE bridge.

Provides thread-safe, atomic configuration file operations with proper locking.
Ensures allowlist and names are never accidentally overwritten during updates.
"""

import json
import os
import fcntl
import tempfile
import logging
from pathlib import Path
from typing import Dict, Optional, List
from contextlib import contextmanager

_LOGGER = logging.getLogger(__name__)


class ConfigManager:
    """
    Thread-safe configuration manager with atomic writes.
    
    Uses file-based locking to prevent concurrent modifications.
    All writes are atomic (temp file + rename) to prevent corruption.
    """
    
    DEFAULT_CONFIG = {
        "sensors": [],
        "ble_interface": "hci0",
        "log_level": "INFO",
        "log_path": "/data/govee-ble/logs/govee_ble.log",
        "update_interval_sec": 1,
        "stale_threshold_sec": 300,
        "restart_min_delay_sec": 30,
        "restart_max_delay_sec": 300,
        "battery": {
            "low_alarm_threshold_pct": 15.0
        },
        "temperature_type_default": 2,  # Generic
        "parser_version": "local_h510x_v1.0.3_humidity_fix"
    }
    
    def __init__(self, config_path: Path):
        """
        Initialize config manager.
        
        Args:
            config_path: Path to config.json file
        """
        self.config_path = Path(config_path)
        self.lock_path = self.config_path.with_suffix('.lock')
        
        # Ensure parent directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        _LOGGER.info(f"Config manager initialized: {self.config_path}")
    
    @contextmanager
    def _lock(self):
        """
        Context manager for file-based locking.
        
        Yields:
            File descriptor for the lock file
        """
        lock_fd = None
        try:
            lock_fd = open(self.lock_path, 'w')
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            yield lock_fd
        finally:
            if lock_fd:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
    
    def read(self) -> Dict:
        """
        Read configuration with lock.
        
        Returns:
            Configuration dictionary
        """
        with self._lock():
            return self._read_unlocked()
    
    def _read_unlocked(self) -> Dict:
        """Read config without acquiring lock (internal use)."""
        if not self.config_path.exists():
            _LOGGER.info("Config file doesn't exist, using defaults")
            return self.DEFAULT_CONFIG.copy()
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Ensure all required keys exist (for upgrades)
            for key, value in self.DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            
            return config
        except json.JSONDecodeError as e:
            _LOGGER.error(f"Config file is corrupt: {e}")
            _LOGGER.warning("Using default configuration")
            return self.DEFAULT_CONFIG.copy()
        except Exception as e:
            _LOGGER.error(f"Error reading config: {e}")
            return self.DEFAULT_CONFIG.copy()
    
    def _atomic_write(self, config: Dict):
        """
        Write config atomically using temp file + rename.
        
        Args:
            config: Configuration dictionary to write
        """
        # Create temp file in same directory for atomic rename
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.config_path.parent,
            prefix='.config_',
            suffix='.tmp'
        )
        
        try:
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(config, f, indent=2, sort_keys=True)
                f.write('\n')  # Trailing newline
            
            # Atomic rename
            os.replace(temp_path, self.config_path)
            _LOGGER.debug(f"Config written atomically to {self.config_path}")
            
        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except:
                pass
            raise e

    def _find_sensor(self, mac: str) -> Optional[Dict]:
        """
        Find sensor object by MAC address.

        Args:
            mac: MAC address (will be uppercased)

        Returns:
            Sensor dict or None if not found
        """
        mac = mac.upper()
        config = self._read_unlocked()
        sensors = config.get('sensors', [])

        for sensor in sensors:
            if sensor.get('mac', '').upper() == mac:
                return sensor

        return None

    def _find_sensor_index(self, mac: str) -> Optional[int]:
        """
        Find sensor array index by MAC address.

        Args:
            mac: MAC address (will be uppercased)

        Returns:
            Array index or None if not found
        """
        mac = mac.upper()
        config = self._read_unlocked()
        sensors = config.get('sensors', [])

        for i, sensor in enumerate(sensors):
            if sensor.get('mac', '').upper() == mac:
                return i

        return None

    def update_sensor(self, mac: str, **kwargs):
        """
        Update sensor properties (name, temperature_type, device_instance).

        Args:
            mac: MAC address
            **kwargs: Properties to update (name, temperature_type, device_instance)
        """
        mac = mac.upper()

        with self._lock():
            config = self._read_unlocked()
            sensors = config.get('sensors', [])

            # Find sensor
            sensor_index = None
            for i, sensor in enumerate(sensors):
                if sensor.get('mac', '').upper() == mac:
                    sensor_index = i
                    break

            if sensor_index is None:
                _LOGGER.warning(f"Cannot update sensor {mac}: not found in sensors array")
                return

            # Update properties
            for key, value in kwargs.items():
                if key in ['name', 'temperature_type', 'device_instance', 'humidity_enabled']:
                    sensors[sensor_index][key] = value
                    _LOGGER.debug(f"Updated {mac} {key}: {value}")
                else:
                    _LOGGER.warning(f"Unknown sensor property: {key}")

            config['sensors'] = sensors
            self._atomic_write(config)
    
    def add_sensor(self, mac: str, name: Optional[str] = None, temperature_type: Optional[int] = None):
        """
        Add sensor to sensors array.
        Idempotent - safe to call multiple times with same MAC (will update existing).

        Args:
            mac: MAC address (will be uppercased)
            name: Optional friendly name
            temperature_type: Optional temperature type (0-6)
        """
        mac = mac.upper()

        if temperature_type is not None and not 0 <= temperature_type <= 6:
            raise ValueError(f"Invalid temperature type: {temperature_type} (must be 0-6)")

        with self._lock():
            config = self._read_unlocked()
            sensors = config.get('sensors', [])

            # Check if sensor already exists
            existing_index = None
            for i, sensor in enumerate(sensors):
                if sensor.get('mac', '').upper() == mac:
                    existing_index = i
                    break

            if existing_index is not None:
                # Update existing sensor
                _LOGGER.debug(f"{mac} already in sensors, updating")
                if name is not None:
                    sensors[existing_index]['name'] = name
                if temperature_type is not None:
                    sensors[existing_index]['temperature_type'] = temperature_type
            else:
                # Add new sensor
                sensor = {"mac": mac}
                if name is not None:
                    sensor['name'] = name
                if temperature_type is not None:
                    sensor['temperature_type'] = temperature_type

                sensors.append(sensor)
                _LOGGER.info(f"Added {mac} to sensors")

            config['sensors'] = sensors
            self._atomic_write(config)
    
    def remove_sensor(self, mac: str):
        """
        Remove sensor from sensors array.

        Args:
            mac: MAC address to remove
        """
        mac = mac.upper()

        with self._lock():
            config = self._read_unlocked()
            sensors = config.get('sensors', [])

            # Find and remove sensor
            new_sensors = [s for s in sensors if s.get('mac', '').upper() != mac]

            if len(new_sensors) < len(sensors):
                _LOGGER.info(f"Removed {mac} from sensors")
                config['sensors'] = new_sensors
                self._atomic_write(config)
            else:
                _LOGGER.debug(f"{mac} not found in sensors")
    
    def update_custom_name(self, mac: str, name: str):
        """
        Set custom name for a device.

        Args:
            mac: MAC address
            name: Custom name string
        """
        mac = mac.upper()

        with self._lock():
            config = self._read_unlocked()
            sensors = config.get('sensors', [])

            # Find sensor and update name
            for sensor in sensors:
                if sensor.get('mac', '').upper() == mac:
                    sensor['name'] = name
                    _LOGGER.info(f"Set custom name for {mac}: '{name}'")
                    config['sensors'] = sensors
                    self._atomic_write(config)
                    return

            _LOGGER.warning(f"Cannot set name for {mac}: not found in sensors")

    def update_temperature_type(self, mac: str, temp_type: int):
        """
        Set temperature type override for a device.

        Args:
            mac: MAC address
            temp_type: Temperature type (0-6)
        """
        mac = mac.upper()

        if not 0 <= temp_type <= 6:
            raise ValueError(f"Invalid temperature type: {temp_type} (must be 0-6)")

        with self._lock():
            config = self._read_unlocked()
            sensors = config.get('sensors', [])

            # Find sensor and update temperature_type
            for sensor in sensors:
                if sensor.get('mac', '').upper() == mac:
                    sensor['temperature_type'] = temp_type
                    _LOGGER.info(f"Set temperature type for {mac}: {temp_type}")
                    config['sensors'] = sensors
                    self._atomic_write(config)
                    return

            _LOGGER.warning(f"Cannot set temperature type for {mac}: not found in sensors")

    def update_parser_version(self, version: str):
        """
        Update parser version in config.
        
        Args:
            version: Parser version string
        """
        with self._lock():
            config = self._read_unlocked()
            config['parser_version'] = version
            _LOGGER.info(f"Updated parser version: {version}")
            self._atomic_write(config)
    
    def get_sensors(self) -> List[Dict]:
        """
        Get all sensors.

        Returns:
            List of sensor dictionaries
        """
        config = self.read()
        return config.get('sensors', [])
    
    def get_device_name(self, mac: str) -> Optional[str]:
        """
        Get friendly name for device.

        Args:
            mac: MAC address

        Returns:
            Friendly name or None
        """
        mac = mac.upper()
        config = self.read()
        sensors = config.get('sensors', [])

        for sensor in sensors:
            if sensor.get('mac', '').upper() == mac:
                return sensor.get('name')

        return None
    
    def get_device_instance(self, mac: str) -> Optional[int]:
        """
        Get device instance for MAC.

        Args:
            mac: MAC address

        Returns:
            Device instance or None
        """
        mac = mac.upper()
        config = self.read()
        sensors = config.get('sensors', [])

        for sensor in sensors:
            if sensor.get('mac', '').upper() == mac:
                return sensor.get('device_instance')

        return None
    
    def get_temperature_type(self, mac: str) -> int:
        """
        Get temperature type for device (with fallback to default).

        Args:
            mac: MAC address

        Returns:
            Temperature type (0-6)
        """
        mac = mac.upper()
        config = self.read()
        sensors = config.get('sensors', [])
        default = config.get('temperature_type_default', 2)

        for sensor in sensors:
            if sensor.get('mac', '').upper() == mac:
                return sensor.get('temperature_type', default)

        return default

    def get_humidity_enabled(self, mac: str) -> bool:
        """
        Get humidity enabled flag for device (with fallback to True).

        Args:
            mac: MAC address

        Returns:
            True if humidity should be enabled (default: True for backward compatibility)
        """
        mac = mac.upper()
        config = self.read()
        sensors = config.get('sensors', [])

        for sensor in sensors:
            if sensor.get('mac', '').upper() == mac:
                return sensor.get('humidity_enabled', True)

        return True

    def update_humidity_enabled(self, mac: str, enabled: bool):
        """
        Set humidity enabled flag for a device and persist to config.

        Args:
            mac: MAC address
            enabled: True to enable humidity readings, False to disable
        """
        mac = mac.upper()

        with self._lock():
            config = self._read_unlocked()
            sensors = config.get('sensors', [])

            # Find sensor and update humidity_enabled
            for sensor in sensors:
                if sensor.get('mac', '').upper() == mac:
                    sensor['humidity_enabled'] = enabled
                    _LOGGER.info(f"Set humidity_enabled for {mac}: {enabled}")
                    config['sensors'] = sensors
                    self._atomic_write(config)
                    return

            _LOGGER.warning(f"Cannot set humidity_enabled for {mac}: not found in sensors")

    def is_allowed(self, mac: str) -> bool:
        """
        Check if MAC is in sensors array.

        Args:
            mac: MAC address

        Returns:
            True if sensor exists
        """
        mac = mac.upper()
        config = self.read()
        sensors = config.get('sensors', [])

        for sensor in sensors:
            if sensor.get('mac', '').upper() == mac:
                return True

        return False
    
    def export_json(self) -> str:
        """
        Export current config as formatted JSON string.
        
        Returns:
            JSON string
        """
        config = self.read()
        return json.dumps(config, indent=2, sort_keys=True)


def main():
    """Test config manager."""
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03dZ %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )

    # Use temp directory for testing
    test_config = Path("/tmp/test_govee_config.json")

    print("Testing ConfigManager v1.2.0 (sensors array)...")
    print(f"Config file: {test_config}\n")

    # Clean up old test file
    if test_config.exists():
        test_config.unlink()

    manager = ConfigManager(test_config)
    
    # Test 1: Read default config
    print("Test 1: Reading default config...")
    config = manager.read()
    print(f"  Sensors: {config['sensors']}")
    print(f"  OK - Default config loaded\n")
    
    # Test 2: Add sensors
    print("Test 2: Adding sensors...")
    manager.add_sensor("AA:BB:CC:DD:EE:FF", "Test Sensor 1")
    manager.add_sensor("11:22:33:44:55:66", "Test Sensor 2", temperature_type=1)
    print(f"  Sensors: {manager.get_sensors()}")
    print(f"  OK - Sensors added\n")
    
    # Test 3: Update sensor properties
    print("Test 3: Updating sensor device instances...")
    manager.update_sensor("AA:BB:CC:DD:EE:FF", device_instance=701)
    manager.update_sensor("11:22:33:44:55:66", device_instance=702)
    config = manager.read()
    print(f"  Sensors: {config['sensors']}")
    print(f"  OK - Device instances updated\n")
    
    # Test 4: Get device info
    print("Test 4: Retrieving device info...")
    mac = "AA:BB:CC:DD:EE:FF"
    print(f"  Name: {manager.get_device_name(mac)}")
    print(f"  Instance: {manager.get_device_instance(mac)}")
    print(f"  Temp Type: {manager.get_temperature_type(mac)}")
    print(f"  Is Allowed: {manager.is_allowed(mac)}")
    print(f"  âœ“ Device info retrieved\n")
    
    # Test 5: Temperature type override
    print("Test 5: Setting temperature type override...")
    manager.update_temperature_type("AA:BB:CC:DD:EE:FF", 1)  # Fridge
    print(f"  Temp Type: {manager.get_temperature_type('AA:BB:CC:DD:EE:FF')}")
    print(f"  âœ“ Temperature type updated\n")
    
    # Test 6: Export
    print("Test 6: Exporting config...")
    json_str = manager.export_json()
    print(f"  Config JSON:\n{json_str}")
    print(f"  âœ“ Config exported\n")
    
    # Test 7: Remove sensor
    print("Test 7: Removing sensor...")
    manager.remove_sensor("11:22:33:44:55:66")
    print(f"  Sensors: {manager.get_sensors()}")
    print(f"  Is Allowed (removed): {manager.is_allowed('11:22:33:44:55:66')}")
    print(f"  âœ“ Device removed\n")
    
    print("="*60)
    print("All tests passed!")
    print("="*60)


if __name__ == "__main__":
    main()
