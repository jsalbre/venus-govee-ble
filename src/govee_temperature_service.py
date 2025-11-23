"""
Govee Temperature D-Bus Service.

Publishes a single Govee sensor's readings to Venus OS D-Bus.
Implements com.victronenergy.temperature service specification.
"""

import logging
import time
import sys
import os

# Add velib_python to path
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'ext/velib_python'))

from vedbus import VeDbusService

_LOGGER = logging.getLogger(__name__)

__version__ = "2.0.0"


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

    def __init__(self, mac_address: str, device_name: str,
                 device_instance: int, temperature_type: int = TEMP_TYPE_GENERIC,
                 dbusconn=None):
        """
        Initialize Govee temperature service.

        Args:
            mac_address: Sensor MAC address (e.g., "A4:C1:38:8E:0D:AF")
            device_name: Display name (e.g., "Freezer" or "GVH5101_0DAF")
            device_instance: Unique device instance number (0-99)
            temperature_type: 0=battery, 1=fridge, 2=generic
            dbusconn: D-Bus connection (None = auto-detect system/session bus)
        """
        self.mac_address = mac_address.upper()
        self.device_name = device_name
        self.device_instance = device_instance
        self.temperature_type = temperature_type

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

    def _add_paths(self):
        """Add all D-Bus paths for temperature sensor."""

        # Mandatory paths (per Venus OS spec)
        self._dbusservice.add_mandatory_paths(
            processname='govee_ble_service',
            processversion=__version__,
            connection='Bluetooth LE',
            deviceinstance=self.device_instance,
            productid=0xB101,  # Custom: "B" for Bluetooth + "101" for H5101
            productname='Govee H5101',
            firmwareversion='1.0.0',
            hardwareversion=None,
            connected=1
        )

        # Temperature sensor specific paths
        self._dbusservice.add_path('/Temperature', value=None, description='Temperature in Celsius')
        self._dbusservice.add_path('/Humidity', value=None, description='Relative humidity in percent')
        self._dbusservice.add_path('/Status', value=self.STATUS_OK, description='Status: 0=Ok, 1=Disconnected')
        self._dbusservice.add_path('/TemperatureType', value=self.temperature_type,
                                   description='0=battery, 1=fridge, 2=generic')
        self._dbusservice.add_path('/CustomName', value=self.device_name, description='Custom name')

        # Additional info paths
        self._dbusservice.add_path('/Battery', value=None, description='Battery level percentage')
        self._dbusservice.add_path('/RSSI', value=None, description='Bluetooth signal strength (dBm)')
        self._dbusservice.add_path('/Mgmt/LastUpdate', value=0, description='Unix timestamp of last update')
        self._dbusservice.add_path('/Mgmt/MAC', value=self.mac_address, description='Sensor MAC address')

    def update(self, temperature: float, humidity: float, battery: int, rssi: int):
        """
        Update sensor readings.

        Args:
            temperature: Temperature in Celsius
            humidity: Relative humidity in percent
            battery: Battery level (0-100)
            rssi: Signal strength in dBm
        """
        now = time.time()

        # Update all sensor values
        self._dbusservice['/Temperature'] = round(temperature, 2)
        self._dbusservice['/Humidity'] = round(humidity, 2)
        self._dbusservice['/Battery'] = battery
        self._dbusservice['/RSSI'] = rssi
        self._dbusservice['/Mgmt/LastUpdate'] = int(now)

        # Mark as connected if it was disconnected
        if self._dbusservice['/Status'] == self.STATUS_DISCONNECTED:
            _LOGGER.info(f"{self.service_name}: Sensor reconnected")
            self._dbusservice['/Status'] = self.STATUS_OK
            self._dbusservice['/Connected'] = 1

        self.last_update_time = now

        _LOGGER.debug(
            f"{self.service_name}: Updated - Temp={temperature:.2f}°C, "
            f"Humidity={humidity:.2f}%, Battery={battery}%, RSSI={rssi}dBm"
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
