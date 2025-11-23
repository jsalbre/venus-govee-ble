#!/usr/bin/env python3
"""
Govee BLE Service - Main Orchestrator.

Main daemon that:
- Manages btmon reader process
- Creates D-Bus services for each allowlisted sensor
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
        Calculate consistent device instance from MAC address.

        Uses last 4 bytes of MAC modulo 100.

        Args:
            mac_address: MAC address (e.g., "A4:C1:38:8E:0D:AF")

        Returns:
            Device instance (0-99)
        """
        # Get last 4 hex chars, convert to int, mod 100
        mac_hex = mac_address.replace(':', '')[-4:]
        instance = int(mac_hex, 16) % 100
        return instance

    def _create_service_for_sensor(self, mac_address: str) -> GoveeTemperatureService:
        """
        Create D-Bus service for a sensor.

        Args:
            mac_address: Sensor MAC address

        Returns:
            GoveeTemperatureService instance
        """
        # Get custom name from config, or use default
        device_name = self.config.get('names', {}).get(mac_address)
        if not device_name:
            # Default: GVH5101_XXXX (last 4 of MAC)
            mac_suffix = mac_address.replace(':', '')[-4:].upper()
            device_name = f"GVH5101_{mac_suffix}"

        # Get temperature type from config
        temp_type = self.config.get('temperature_type', {}).get(
            mac_address,
            self.config.get('temperature_type_default', 2)  # Default: generic
        )

        # Calculate device instance
        device_instance = self._calculate_device_instance(mac_address)

        # Create the service
        service = GoveeTemperatureService(
            mac_address=mac_address,
            device_name=device_name,
            device_instance=device_instance,
            temperature_type=temp_type
        )

        _LOGGER.info(
            f"Created service for {mac_address}: {device_name} "
            f"(instance={device_instance}, type={temp_type})"
        )

        return service

    def _initialize_services(self):
        """Create D-Bus services for all allowlisted sensors."""
        allowlist = self.config.get('allowlist', [])

        if not allowlist:
            _LOGGER.warning("Allowlist is empty - no sensors will be monitored")
            return

        _LOGGER.info(f"Initializing services for {len(allowlist)} sensor(s)")

        for mac in allowlist:
            mac = mac.upper()
            if mac not in self.services:
                try:
                    service = self._create_service_for_sensor(mac)
                    self.services[mac] = service
                except Exception as e:
                    _LOGGER.error(f"Failed to create service for {mac}: {e}", exc_info=True)

    def _handle_advertisement(self, adv_data: dict):
        """
        Process a BLE advertisement.

        Args:
            adv_data: Advertisement data from AdvertisementAssembler
        """
        mac = adv_data.get('address', '').upper()

        # Check if this sensor is allowlisted
        if mac not in self.services:
            return

        # Parse the advertisement
        try:
            parsed = parse_advertisement(adv_data)
            if not parsed:
                return

            # Update the D-Bus service
            service = self.services[mac]
            service.update(
                temperature=parsed['temperature'],
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

        # Create assembler and watchdog
        self.assembler = AdvertisementAssembler()
        self.watchdog = BtmonWatchdog(
            stall_timeout_sec=180,
            heartbeat_interval_sec=60
        )

        _LOGGER.info("btmon reader started")

    def _read_btmon_output(self):
        """Read and process btmon output (called periodically by GLib)."""
        try:
            # Check if btmon is still running
            if self.btmon_process.poll() is not None:
                _LOGGER.error("btmon process died unexpectedly")
                self.mainloop.quit()
                return False

            # Read line from btmon (non-blocking via timeout)
            line = self.btmon_process.stdout.readline()
            if not line:
                return True

            # Reset watchdog
            self.watchdog.reset()

            # Feed line to assembler
            adv = self.assembler.process_line(line.rstrip())
            if adv:
                self._handle_advertisement(adv)

            # Check watchdog
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
