"""
Govee Temperature D-Bus Service.

Publishes a single Govee sensor's readings to Venus OS D-Bus.
Implements com.victronenergy.temperature service specification.
"""

import logging
import time
import sys
import os
import re

# Add velib_python to path
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'ext/velib_python'))

from vedbus import VeDbusService

_LOGGER = logging.getLogger(__name__)

__version__ = "2.1.0"


class GoveeTemperatureService:
    """
    D-Bus service for a single Govee temperature/humidity sensor.

    Implements com.victronenergy.temperature service type with additional
    humidity reading support.
    """

    # Temperature type constants (per Venus OS spec)
    TEMP_TYPE_BATTERY = 0
    TEMP_TYPE_FRIDGE = 1
    TEMP_TYPE_GENERIC = 2

    # Status constants
    STATUS_OK = 0
    STATUS_DISCONNECTED = 1

    def __init__(self, mac_address: str, device_name: str, ble_name: str = None,
                 device_instance: int = 0, temperature_type: int = TEMP_TYPE_GENERIC,
                 humidity_enabled: bool = True,
                 dbusconn=None, on_name_change=None, on_type_change=None):
        """
        Initialize Govee temperature service.

        Args:
            mac_address: Sensor MAC address (e.g., "A4:C1:38:8E:0D:AF")
            device_name: Display name for CustomName (e.g., "Freezer" or "GVH5101_0DAF")
            ble_name: BLE advertisement name for model extraction (e.g., "GVH5105_240C")
            device_instance: Unique device instance number (0-99)
            temperature_type: 0=battery, 1=fridge, 2=generic
            humidity_enabled: Whether to expose /Humidity D-Bus path (default: True, config-file only)
            dbusconn: D-Bus connection (None = auto-detect system/session bus)
            on_name_change: Callback function(mac, new_name) when CustomName changes
            on_type_change: Callback function(mac, new_type) when TemperatureType changes
        """
        self.mac_address = mac_address.upper()
        self.device_name = device_name
        self.ble_name = ble_name or device_name  # Fallback to device_name if no BLE name
        self.device_instance = device_instance
        self.temperature_type = temperature_type
        self.humidity_enabled = humidity_enabled
        self.on_name_change = on_name_change
        self.on_type_change = on_type_change

        # Service name: com.victronenergy.temperature.govee_XXXX
        # Use last 4 hex chars of MAC (without colons)
        mac_suffix = mac_address.replace(':', '')[-4:].lower()
        self.service_name = f"com.victronenergy.temperature.govee_{mac_suffix}"

        # Track last update time for stale detection
        self.last_update_time = None

        # Create the D-Bus service
        self._dbusservice = VeDbusService(self.service_name, bus=dbusconn, register=False)

        # Add all paths
        self._add_paths()

        # Register the service
        self._dbusservice.register()

        _LOGGER.info(
            f"Registered D-Bus service: {self.service_name} "
            f"(instance={device_instance}, type={temperature_type})"
        )

    def _handle_name_change(self, path, value):
        """Handle CustomName change from Venus OS GUI."""
        if value != self.device_name:
            _LOGGER.info(f"{self.service_name}: CustomName changed to '{value}'")
            self.device_name = value
            if self.on_name_change:
                self.on_name_change(self.mac_address, value)
        return True  # Accept the change

    def _handle_type_change(self, path, value):
        """Handle TemperatureType change from Venus OS GUI."""
        if value != self.temperature_type:
            _LOGGER.info(f"{self.service_name}: TemperatureType changed to {value}")
            self.temperature_type = value
            if self.on_type_change:
                self.on_type_change(self.mac_address, value)
        return True  # Accept the change

    def _extract_model(self, device_name: str) -> str:
        """
        Extract model from device name.

        Examples:
            "GVH5105_240C" -> "H5105"
            "GVH5101_DFA1" -> "H5101"
            "Custom Name" -> None

        Args:
            device_name: Device name from BLE advertisement

        Returns:
            Model string (e.g., "H5105") or None if not extractable
        """
        if not device_name:
            return None

        match = re.match(r'^GVH(\d+)', device_name)
        if match:
            return f"H{match.group(1)}"
        return None

    def _get_product_id(self, model: str) -> int:
        """
        Get product ID for model.

        Product ID format: 0xBXXX where XXX is the last 3 digits of model
        - H5100 -> 0xB100 (45312 decimal)
        - H5101 -> 0xB101 (45313 decimal)
        - H5105 -> 0xB105 (45317 decimal)
        - Unknown -> 0xB510 (46352 decimal, generic H510x family)

        Args:
            model: Model string (e.g., "H5105")

        Returns:
            Product ID as integer
        """
        if not model or not model.startswith('H'):
            return 0xB510  # Generic H510x family

        try:
            # Extract last 3 digits from model and treat as hex digits
            # "H5105" -> "105" -> 0x105 (261 decimal) -> 0xB000 + 0x105 = 0xB105
            suffix = model[-3:]
            model_num = int(suffix, 16)  # Parse as hex: "105" -> 0x105 = 261
            return 0xB000 + model_num     # H5105 -> 0xB000 + 261 = 0xB105
        except (ValueError, IndexError):
            return 0xB510  # Fallback to generic

    def _add_paths(self):
        """Add all D-Bus paths for temperature sensor."""

        # Extract model from BLE name (not device_name which may be custom)
        # device_name = "Freezer" (custom) → model extraction fails
        # ble_name = "GVH5105_240C" → model = "H5105" ✓
        model = self._extract_model(self.ble_name)
        product_id = self._get_product_id(model)
        product_name = f"Govee {model}" if model else "Govee H510x"

        _LOGGER.debug(
            f"Setting product info for {self.mac_address}: model={model}, "
            f"product_id=0x{product_id:04X}, product_name={product_name}"
        )

        # Mandatory paths (per Venus OS spec)
        self._dbusservice.add_mandatory_paths(
            processname='govee_ble_service',
            processversion=__version__,
            connection='Bluetooth LE',
            deviceinstance=self.device_instance,
            productid=product_id,      # Dynamic: 0xB100, 0xB101, 0xB105, etc.
            productname=product_name,  # Dynamic: "Govee H5100", "Govee H5105", etc.
            firmwareversion=__version__,
            hardwareversion=None,
            connected=1
        )

        # Temperature sensor specific paths
        self._dbusservice.add_path('/Temperature', value=None, description='Temperature in Celsius')

        # Humidity path - conditionally added based on humidity_enabled flag (config-file only)
        if self.humidity_enabled:
            self._dbusservice.add_path('/Humidity', value=None, description='Relative humidity in percent')

        self._dbusservice.add_path('/Status', value=self.STATUS_OK, description='Status: 0=Ok, 1=Disconnected')
        self._dbusservice.add_path('/TemperatureType', value=self.temperature_type, writeable=True,
                                   onchangecallback=self._handle_type_change,
                                   description='0=battery, 1=fridge, 2=generic, 3=room, 4=outdoor, 5=waterheater, 6=freezer')
        self._dbusservice.add_path('/CustomName', value=self.device_name, writeable=True,
                                   onchangecallback=self._handle_name_change,
                                   description='Custom name')

        # Additional info paths
        self._dbusservice.add_path('/Battery', value=None, description='Battery level percentage')
        self._dbusservice.add_path('/RSSI', value=None, description='Bluetooth signal strength (dBm)')
        self._dbusservice.add_path('/Mgmt/LastUpdate', value=0, description='Unix timestamp of last update')
        self._dbusservice.add_path('/Mgmt/MAC', value=self.mac_address, description='Sensor MAC address')
        self._dbusservice.add_path('/DeviceName', value=self.ble_name, description='BLE advertisement device name')

    def update(self, temperature: float, humidity: float, battery: int, rssi: int):
        """
        Update sensor readings.

        Args:
            temperature: Temperature in Celsius (or None if invalid)
            humidity: Relative humidity in percent (or None if invalid)
            battery: Battery level (0-100, or None if invalid)
            rssi: Signal strength in dBm
        """
        now = time.time()

        # Update all sensor values (D-Bus accepts None for invalid/unavailable values)
        self._dbusservice['/Temperature'] = round(temperature, 2) if temperature is not None else None

        # Only update /Humidity if it exists (path may be dynamically removed)
        if '/Humidity' in self._dbusservice:
            self._dbusservice['/Humidity'] = round(humidity, 2) if humidity is not None else None

        self._dbusservice['/Battery'] = battery
        self._dbusservice['/RSSI'] = rssi
        self._dbusservice['/Mgmt/LastUpdate'] = int(now)

        # Mark as connected if it was disconnected
        if self._dbusservice['/Status'] == self.STATUS_DISCONNECTED:
            _LOGGER.info(f"{self.service_name}: Sensor reconnected")
            self._dbusservice['/Status'] = self.STATUS_OK
            self._dbusservice['/Connected'] = 1

        self.last_update_time = now

        # Safe logging with None handling
        temp_str = f"{temperature:.2f}°C" if temperature is not None else "N/A"
        hum_str = f"{humidity:.2f}%" if humidity is not None else "N/A"
        batt_str = f"{battery}%" if battery is not None else "N/A"
        _LOGGER.debug(
            f"{self.service_name}: Updated - Temp={temp_str}, "
            f"Humidity={hum_str}, Battery={batt_str}, RSSI={rssi}dBm"
        )

    def mark_disconnected(self):
        """Mark sensor as disconnected (stale - no recent advertisements)."""
        if self._dbusservice['/Status'] != self.STATUS_DISCONNECTED:
            _LOGGER.warning(
                f"{self.service_name}: Sensor disconnected (no advertisements)"
            )
            self._dbusservice['/Status'] = self.STATUS_DISCONNECTED
            self._dbusservice['/Connected'] = 0

    def check_stale(self, threshold_sec: int) -> bool:
        """
        Check if sensor data is stale.

        Args:
            threshold_sec: Seconds without update before considering stale

        Returns:
            True if stale (should be marked disconnected)
        """
        if self.last_update_time is None:
            return False

        elapsed = time.time() - self.last_update_time
        return elapsed > threshold_sec

    def update_custom_name(self, name: str):
        """
        Update the custom display name.

        Args:
            name: New custom name
        """
        if name != self.device_name:
            self.device_name = name
            self._dbusservice['/CustomName'] = name
            _LOGGER.info(f"{self.service_name}: Name updated to '{name}'")

    def update_temperature_type(self, temp_type: int):
        """
        Update the temperature type.

        Args:
            temp_type: 0=battery, 1=fridge, 2=generic
        """
        if temp_type != self.temperature_type:
            self.temperature_type = temp_type
            self._dbusservice['/TemperatureType'] = temp_type
            _LOGGER.info(f"{self.service_name}: Temperature type updated to {temp_type}")

    def get_service_name(self) -> str:
        """Get the D-Bus service name."""
        return self.service_name

    def get_mac_address(self) -> str:
        """Get the sensor MAC address."""
        return self.mac_address

    def close(self):
        """Clean up and deregister service."""
        _LOGGER.info(f"Closing D-Bus service: {self.service_name}")
        if self._dbusservice:
            self._dbusservice.__del__()
            self._dbusservice = None
