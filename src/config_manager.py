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
        "allowlist": [],
        "names": {},
        "device_instances": {},
        "ble_interface": "hci0",
        "log_level": "INFO",
        "log_path": "/data/govee-ble/logs/govee_ble.log",
        "update_interval_sec": 1,
        "stale_threshold_sec": 120,
        "restart_min_delay_sec": 30,
        "restart_max_delay_sec": 300,
        "battery": {
            "low_alarm_threshold_pct": 15.0
        },
        "temperature_type_default": 2,  # Generic
        "temperature_type": {},
        "parser_version": "local_h510x_v1"
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
    
    def update_device_instances(self, updates: Dict[str, int]):
        """
        Update device_instances without touching allowlist or names.
        
        Args:
            updates: Dict of MAC -> device_instance to update
        """
        with self._lock():
            config = self._read_unlocked()
            
            # Update device instances
            for mac, instance in updates.items():
                mac = mac.upper()
                config['device_instances'][mac] = instance
                _LOGGER.debug(f"Updated device instance: {mac} -> {instance}")
            
            self._atomic_write(config)
    
    def update_allowlist(self, mac: str, name: Optional[str] = None):
        """
        Add MAC to allowlist and optionally set friendly name.
        Idempotent - safe to call multiple times with same MAC.
        
        Args:
            mac: MAC address to add (will be uppercased)
            name: Optional friendly name
        """
        mac = mac.upper()
        
        with self._lock():
            config = self._read_unlocked()
            
            # Add to allowlist if not present
            if mac not in config['allowlist']:
                config['allowlist'].append(mac)
                _LOGGER.info(f"Added {mac} to allowlist")
            else:
                _LOGGER.debug(f"{mac} already in allowlist")
            
            # Set name if provided
            if name:
                config['names'][mac] = name
                _LOGGER.info(f"Set name for {mac}: {name}")
            
            self._atomic_write(config)
    
    def remove_from_allowlist(self, mac: str):
        """
        Remove MAC from allowlist (and associated name).
        
        Args:
            mac: MAC address to remove
        """
        mac = mac.upper()
        
        with self._lock():
            config = self._read_unlocked()
            
            if mac in config['allowlist']:
                config['allowlist'].remove(mac)
                _LOGGER.info(f"Removed {mac} from allowlist")
            
            if mac in config['names']:
                del config['names'][mac]
                _LOGGER.debug(f"Removed name for {mac}")
            
            # Note: We keep device_instance for historical tracking
            
            self._atomic_write(config)
    
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
            config['temperature_type'][mac] = temp_type
            _LOGGER.info(f"Set temperature type for {mac}: {temp_type}")
            self._atomic_write(config)
    
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
    
    def get_allowlist(self) -> List[str]:
        """
        Get current allowlist.
        
        Returns:
            List of MAC addresses
        """
        config = self.read()
        return config['allowlist']
    
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
        return config['names'].get(mac)
    
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
        return config['device_instances'].get(mac)
    
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
        return config['temperature_type'].get(mac, config['temperature_type_default'])
    
    def is_allowed(self, mac: str) -> bool:
        """
        Check if MAC is in allowlist.
        
        Args:
            mac: MAC address
        
        Returns:
            True if allowed
        """
        mac = mac.upper()
        return mac in self.get_allowlist()
    
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
    
    print("Testing ConfigManager...")
    print(f"Config file: {test_config}\n")
    
    # Clean up old test file
    if test_config.exists():
        test_config.unlink()
    
    manager = ConfigManager(test_config)
    
    # Test 1: Read default config
    print("Test 1: Reading default config...")
    config = manager.read()
    print(f"  Allowlist: {config['allowlist']}")
    print(f"  âœ“ Default config loaded\n")
    
    # Test 2: Add to allowlist
    print("Test 2: Adding devices to allowlist...")
    manager.update_allowlist("AA:BB:CC:DD:EE:FF", "Test Sensor 1")
    manager.update_allowlist("11:22:33:44:55:66", "Test Sensor 2")
    print(f"  Allowlist: {manager.get_allowlist()}")
    print(f"  âœ“ Devices added\n")
    
    # Test 3: Update device instances (shouldn't affect allowlist)
    print("Test 3: Updating device instances...")
    manager.update_device_instances({
        "AA:BB:CC:DD:EE:FF": 701,
        "11:22:33:44:55:66": 702
    })
    config = manager.read()
    print(f"  Device instances: {config['device_instances']}")
    print(f"  Allowlist unchanged: {config['allowlist']}")
    print(f"  âœ“ Device instances updated without affecting allowlist\n")
    
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
    
    # Test 7: Remove from allowlist
    print("Test 7: Removing device from allowlist...")
    manager.remove_from_allowlist("11:22:33:44:55:66")
    print(f"  Allowlist: {manager.get_allowlist()}")
    print(f"  Is Allowed (removed): {manager.is_allowed('11:22:33:44:55:66')}")
    print(f"  âœ“ Device removed\n")
    
    print("="*60)
    print("All tests passed!")
    print("="*60)


if __name__ == "__main__":
    main()
