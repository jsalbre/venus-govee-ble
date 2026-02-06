#!/usr/bin/env python3
"""
Govee BLE Service - Main Orchestrator.

Main daemon that:
- Manages btmon reader process
- Creates D-Bus services for each configured sensor
- Routes BLE advertisements to appropriate services
- Monitors sensor health and connection state
- Handles errors with exponential backoff
"""

import sys
import os
import logging
import signal
import time
from pathlib import Path
from typing import Dict, Optional
from logging.handlers import RotatingFileHandler

# Add velib_python to path
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'ext/velib_python'))

from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

# Local imports
from config_manager import ConfigManager
from btmon_reader import AdvertisementAssembler, BtmonWatchdog
from parser_adapter import parse_advertisement, is_govee_device
from govee_temperature_service import GoveeTemperatureService

__version__ = "2.0.0"

_LOGGER = logging.getLogger(__name__)


class RestartBackoff:
    """Manages exponential backoff for service restarts."""

    def __init__(self, min_delay: int, max_delay: int, reset_after: int):
        """
        Initialize backoff manager.

        Args:
            min_delay: Minimum delay in seconds (e.g., 30)
            max_delay: Maximum delay in seconds (e.g., 300)
            reset_after: Reset backoff after N seconds of success (e.g., 3600)
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.reset_after = reset_after
        self.current_delay = min_delay
        self.last_success_time = time.time()

    def wait(self):
        """Sleep for current backoff delay."""
        _LOGGER.info(f"Backoff: Waiting {self.current_delay}s before restart")
        time.sleep(self.current_delay)

        # Increase delay for next time (exponential)
        self.current_delay = min(self.current_delay * 2, self.max_delay)

    def reset_if_successful(self):
        """Reset backoff if enough time has passed since last failure."""
        elapsed = time.time() - self.last_success_time
        if elapsed > self.reset_after:
            if self.current_delay > self.min_delay:
                _LOGGER.info(f"Backoff: Reset after {elapsed:.0f}s of stable operation")
                self.current_delay = self.min_delay

    def mark_success(self):
        """Mark successful operation (start of stable period)."""
        self.last_success_time = time.time()


class GoveeBLEService:
    """Main orchestrator for Govee BLE to D-Bus bridge."""

    def __init__(self, config_path: Path):
        """
        Initialize the service.

        Args:
            config_path: Path to config.json
        """
        self.config_path = config_path
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.read()

        # D-Bus services for each sensor (MAC -> GoveeTemperatureService)
        self.services: Dict[str, GoveeTemperatureService] = {}

        # btmon process and assembler
        self.btmon_process = None
        self.assembler = None
        self.watchdog = None

        # Restart backoff
        self.backoff = RestartBackoff(
            min_delay=self.config.get('restart_min_delay_sec', 30),
            max_delay=self.config.get('restart_max_delay_sec', 300),
            reset_after=3600  # 1 hour
        )

        # GLib mainloop
        self.mainloop = None

        # Shutdown flag
        self.shutdown_requested = False

        # Setup logging
        self._setup_logging()

        _LOGGER.info(f"Govee BLE Service v{__version__} initializing")

    def _setup_logging(self):
        """Configure logging with rotation."""
        log_path = Path(self.config.get('log_path', '/data/govee-ble/logs/govee_ble.log'))
        log_level = self.config.get('log_level', 'INFO')

        # Ensure log directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler (10MB per file, 7 files = 70MB total)
        handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=7
        )

        # Format: timestamp - level - name - message
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        root_logger.addHandler(handler)

        # Also log to console
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root_logger.addHandler(console)

        _LOGGER.info(f"Logging configured: {log_path} (level={log_level})")

    def _calculate_device_instance(self, mac_address: str) -> int:
        """
        Get or calculate consistent device instance from MAC address.

        First checks if instance already stored in config. If not,
        calculates using last 4 bytes of MAC modulo 100, offset by 400,
        and saves it to config.

        Args:
            mac_address: MAC address (e.g., "A4:C1:38:8E:0D:AF")

        Returns:
            Device instance (400-499)
        """
        # Check if already have a device instance in config
        existing_instance = self.config_manager.get_device_instance(mac_address)
        if existing_instance is not None:
            return existing_instance

        # Calculate new instance: last 4 hex chars, convert to int, mod 100, offset by 400
        mac_hex = mac_address.replace(':', '')[-4:]
        instance = 400 + (int(mac_hex, 16) % 100)

        # Save to config for persistence
        try:
            self.config_manager.update_sensor(mac_address, device_instance=instance)
            _LOGGER.debug(f"Saved device instance for {mac_address}: {instance}")
        except Exception as e:
            _LOGGER.warning(f"Failed to save device instance for {mac_address}: {e}")

        return instance

    def _save_custom_name(self, mac_address: str, new_name: str):
        """
        Save custom name change to config file.

        Args:
            mac_address: Sensor MAC address
            new_name: New custom name
        """
        try:
            self.config_manager.update_custom_name(mac_address, new_name)
            # Reload config to stay in sync
            self.config = self.config_manager.read()
        except Exception as e:
            _LOGGER.error(f"Failed to save CustomName for {mac_address}: {e}", exc_info=True)

    def _save_temperature_type(self, mac_address: str, new_type: int):
        """
        Save temperature type change to config file.

        Args:
            mac_address: Sensor MAC address
            new_type: New temperature type
        """
        try:
            self.config_manager.update_temperature_type(mac_address, new_type)
            # Reload config to stay in sync
            self.config = self.config_manager.read()
        except Exception as e:
            _LOGGER.error(f"Failed to save TemperatureType for {mac_address}: {e}", exc_info=True)

    def _create_service_for_sensor(self, mac_address: str, ble_name: str = None) -> GoveeTemperatureService:
        """
        Create D-Bus service for a sensor.

        Args:
            mac_address: Sensor MAC address
            ble_name: BLE advertisement name (e.g., "GVH5105_240C"), if available

        Returns:
            GoveeTemperatureService instance
        """
        # Separate concerns:
        # - device_name: What user sees (custom name OR BLE name)
        # - ble_name: For model extraction (ProductID/ProductName)

        # Priority for CustomName (what user sees):
        # 1. Custom name from config (user preference) - HIGHEST
        # 2. BLE advertisement name (descriptive)
        # 3. Generated default (shouldn't happen with lazy creation)

        custom_name = self.config_manager.get_device_name(mac_address)
        if custom_name:
            device_name = custom_name
            _LOGGER.debug(f"Using custom name for {mac_address}: {custom_name}")
        elif ble_name:
            device_name = ble_name
            _LOGGER.debug(f"Using BLE name for {mac_address}: {ble_name}")
        else:
            # Fallback (shouldn't happen with lazy creation)
            mac_suffix = mac_address.replace(':', '')[-4:].upper()
            device_name = f"GVH5101_{mac_suffix}"
            _LOGGER.warning(
                f"No custom or BLE name for {mac_address}, using fallback: {device_name}"
            )

        # Get temperature type from config
        temp_type = self.config_manager.get_temperature_type(mac_address)

        # Get humidity enabled flag from config
        humidity_enabled = self.config_manager.get_humidity_enabled(mac_address)

        # Calculate device instance
        device_instance = self._calculate_device_instance(mac_address)

        # Create a private D-Bus connection for this service
        # Using private=True creates a separate connection instead of the shared singleton
        import dbus
        dbusconn = dbus.SystemBus(private=True)

        # Create the service with its own D-Bus connection and config callbacks
        # Pass ble_name separately for model extraction (ProductID/ProductName)
        service = GoveeTemperatureService(
            mac_address=mac_address,
            device_name=device_name,  # CustomName (user-facing)
            ble_name=ble_name,         # For model extraction
            device_instance=device_instance,
            temperature_type=temp_type,
            humidity_enabled=humidity_enabled,
            dbusconn=dbusconn,
            on_name_change=self._save_custom_name,
            on_type_change=self._save_temperature_type
        )

        _LOGGER.info(
            f"Created service for {mac_address}: {device_name} "
            f"(instance={device_instance}, type={temp_type})"
        )

        return service

    def _initialize_services(self):
        """
        Log configured sensors and prepare for lazy service creation.

        Services are now created on-demand when first advertisement is received,
        ensuring correct model information (H5100/H5105 etc.) from the BLE name.
        """
        sensors = self.config.get('sensors', [])

        if not sensors:
            _LOGGER.warning("No sensors configured - no sensors will be monitored")
            _LOGGER.info("Add sensors to config.json or use: /data/govee-ble/add-sensor.sh")
            return

        sensor_macs = [s.get('mac', '').upper() for s in sensors if s.get('mac')]

        _LOGGER.info(f"Configured sensors: {len(sensor_macs)}")
        for mac in sensor_macs:
            _LOGGER.info(f"  - {mac}")

        _LOGGER.info(
            f"Waiting for BLE advertisements from {len(sensor_macs)} sensor(s)... "
            f"(services will be created when first advertisement is received)"
        )

    def _handle_advertisement(self, adv_data: dict):
        """
        Process a BLE advertisement.

        Creates services on-demand when first advertisement is received.

        Args:
            adv_data: Advertisement data from AdvertisementAssembler
        """
        mac = adv_data.get('mac', '').upper()
        name = adv_data.get('name', '')

        # Check if this sensor is configured
        configured_macs = [s['mac'].upper() for s in self.config.get('sensors', [])]

        if mac not in self.services:
            # Check if this MAC is in our configuration
            if mac in configured_macs:
                # Configured sensor - create service on-demand with real BLE name
                try:
                    _LOGGER.info(f"Creating service for {mac} ({name})")
                    self.services[mac] = self._create_service_for_sensor(mac, ble_name=name)
                    _LOGGER.info(f"Service created successfully for {mac}")
                except Exception as e:
                    _LOGGER.error(f"Failed to create service for {mac}: {e}", exc_info=True)
                    return
            else:
                # Not configured - log as discovered (once per MAC)
                if not hasattr(self, '_discovered_sensors'):
                    self._discovered_sensors = set()

                if mac not in self._discovered_sensors and is_govee_device(name, adv_data.get('manufacturer_data', {})):
                    self._discovered_sensors.add(mac)
                    _LOGGER.info(f"Discovered Govee sensor not in sensors: {mac} ({name}) - "
                                f"Add to config.json sensors array to monitor")
                return

        # Parse the advertisement
        try:
            parsed = parse_advertisement(
                mac=adv_data.get('mac', mac),  # Use already-validated mac from line 242
                name=name,
                rssi=adv_data.get('rssi'),
                manufacturer_data=adv_data.get('manufacturer_data', {})
            )
            if not parsed:
                return

            # Update the D-Bus service
            service = self.services[mac]
            service.update(
                temperature=parsed['temperature_c'],
                humidity=parsed['humidity'],
                battery=parsed['battery'],
                rssi=adv_data.get('rssi', 0)
            )

        except Exception as e:
            _LOGGER.error(f"Error parsing advertisement from {mac}: {e}", exc_info=True)

    def _check_stale_sensors(self):
        """Check for stale sensors and mark them as disconnected."""
        threshold = self.config.get('stale_threshold_sec', 120)

        for mac, service in self.services.items():
            if service.check_stale(threshold):
                service.mark_disconnected()

        # Schedule next check
        return True  # Continue periodic check

    def _start_btmon(self):
        """Start btmon reader process."""
        import subprocess

        _LOGGER.info("Starting btmon reader")

        # Start btmon process
        self.btmon_process = subprocess.Popen(
            ['btmon', '-T'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )

        # Create assembler with allowlist filter and watchdog
        allowlist = self.config.get('allowlist', [])
        self.assembler = AdvertisementAssembler(allowlist=allowlist)
        self.watchdog = BtmonWatchdog(
            stall_timeout_sec=180,
            heartbeat_interval_sec=60
        )

        _LOGGER.info(f"Assembler configured to filter for {len(allowlist)} allowlisted MACs")

        _LOGGER.info("btmon reader started")

    def _read_btmon_output(self):
        """Read and process btmon output (called periodically by GLib)."""
        try:
            # Check if btmon is still running
            if self.btmon_process.poll() is not None:
                _LOGGER.error("btmon process died unexpectedly")
                self.mainloop.quit()
                return False

            # Read multiple lines per callback to clear backlog (up to 100 lines)
            lines_processed = 0
            max_lines_per_call = 100

            for _ in range(max_lines_per_call):
                line = self.btmon_process.stdout.readline()
                if not line:
                    # EOF - btmon died
                    break

                lines_processed += 1

                # Reset watchdog
                self.watchdog.reset()

                # Feed line to assembler
                adv = self.assembler.process_line(line.rstrip())
                if adv:
                    self._handle_advertisement(adv)

            # Check watchdog periodically (not every line)
            if lines_processed > 0:
                self.watchdog.check()

            return True  # Continue reading

        except SystemExit:
            # Watchdog triggered exit
            _LOGGER.error("Watchdog triggered - btmon stalled")
            self.mainloop.quit()
            return False
        except Exception as e:
            _LOGGER.error(f"Error reading btmon output: {e}", exc_info=True)
            self.mainloop.quit()
            return False

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        _LOGGER.info(f"Received signal {sig_name}, shutting down gracefully")
        self.shutdown_requested = True
        if self.mainloop:
            self.mainloop.quit()

    def run(self):
        """Main run loop with error recovery."""
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        while not self.shutdown_requested:
            try:
                # Reload config
                self.config = self.config_manager.read()

                # Initialize D-Bus mainloop
                DBusGMainLoop(set_as_default=True)

                # Create services for allowlisted sensors
                self._initialize_services()

                # Start btmon
                self._start_btmon()

                # Create GLib mainloop
                self.mainloop = GLib.MainLoop()

                # Schedule periodic btmon reading (every 100ms)
                GLib.timeout_add(100, self._read_btmon_output)

                # Schedule periodic stale sensor check (every 30s)
                GLib.timeout_add(30000, self._check_stale_sensors)

                # Mark successful start
                self.backoff.mark_success()

                _LOGGER.info("Service running - entering main loop")

                # Run the main loop
                self.mainloop.run()

                _LOGGER.info("Main loop exited")

                # Clean up
                self._cleanup()

                # Check if we should restart or shutdown
                if self.shutdown_requested:
                    _LOGGER.info("Shutdown complete")
                    break

                # Wait with backoff before restarting
                _LOGGER.warning("Service crashed, will restart with backoff")
                self.backoff.wait()

            except Exception as e:
                _LOGGER.error(f"Fatal error in main loop: {e}", exc_info=True)
                self._cleanup()

                if self.shutdown_requested:
                    break

                # Wait with backoff before restarting
                self.backoff.wait()

    def _cleanup(self):
        """Clean up resources."""
        _LOGGER.info("Cleaning up resources")

        # Stop btmon
        if self.btmon_process:
            try:
                self.btmon_process.terminate()
                self.btmon_process.wait(timeout=5)
            except Exception as e:
                _LOGGER.error(f"Error stopping btmon: {e}")
                try:
                    self.btmon_process.kill()
                except:
                    pass
            self.btmon_process = None

        # Close D-Bus services
        for mac, service in list(self.services.items()):
            try:
                service.close()
            except Exception as e:
                _LOGGER.error(f"Error closing service for {mac}: {e}")

        self.services.clear()
        self.assembler = None
        self.watchdog = None
        self.mainloop = None


def main():
    """Entry point."""
    # Determine config path
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])
    else:
        config_path = Path('/data/govee-ble/config.json')

    # Create and run service
    service = GoveeBLEService(config_path)
    service.run()


if __name__ == '__main__':
    main()
