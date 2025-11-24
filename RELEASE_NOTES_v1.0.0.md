# Release Notes - v1.0.0

**First Production Release** - Govee BLE Venus OS Bridge

Full integration of Govee H5101/H5102/H5104 temperature/humidity sensors with Victron Venus OS.

## 🎉 What's New

### Scripted Installation
- **install.sh** - One-command automated installation
- **add-sensor.sh** - Helper script to add sensors to allowlist
- No manual file copying or directory creation required
- Interactive service startup
- Automatic backup of existing installations

### Sensor Discovery
Critical feature: Govee H510x sensors do NOT display MAC addresses on the device or in the Govee mobile app. The service automatically discovers and logs Govee sensors, displaying their MAC addresses in the log output for easy identification and configuration.

### Native Venus OS Integration
- Sensors appear in **Settings → Temperature sensors**
- Full integration with VRM Portal
- Real-time updates in Device List
- Historical data graphing
- Temperature alarm support

### Configuration Persistence
GUI changes to sensor names and temperature types are automatically saved to `config.json` - a major improvement over earlier versions.

### Robust Operation
- Exponential backoff error recovery
- Watchdog for btmon process monitoring
- Log rotation (10MB × 7 files)
- Automatic reconnection on sensor dropout
- Graceful shutdown handling

## 📊 Performance

Validated on Victron Cerbo GX:

| Metric | Accuracy | Notes |
|--------|----------|-------|
| Temperature | ±0.5°C | Excellent match with Govee app |
| Battery | Exact | 100% match |
| Humidity | ~15-20% error | Known algorithm limitation |
| CPU Usage | <1% idle | 3-5% during BLE processing |
| Memory | 15-20 MB | Stable, no leaks |

## 🚀 Quick Start

```bash
# Transfer to Venus OS
scp govee-ble-deploy.tar.gz root@venus.local:/tmp/

# SSH and install
ssh root@venus.local
cd /tmp
tar xzf govee-ble-deploy.tar.gz
cd govee-ble-deploy
./install.sh

# Start service to discover sensors (MACs not visible on device!)
svc -u /service/govee-ble

# Monitor logs for discovered sensors
tail -f /data/govee-ble/logs/govee_ble.log

# Configure with discovered MAC addresses
vi /data/govee-ble/config.json

# Restart service
svc -t /service/govee-ble
```

## 📦 What's Included

- **govee_ble_service.py** - Main service orchestrator (v2.0.0)
- **govee_temperature_service.py** - D-Bus temperature service
- **parser_adapter.py** - BLE advertisement parser (v1.0.3)
- **btmon_reader.py** - btmon process manager with watchdog
- **config_manager.py** - Thread-safe configuration with atomic writes
- **install.sh** - Automated installation script with backup
- **add-sensor.sh** - Helper script to add sensors to allowlist
- **Service files** - Runit service for auto-start
- **Dependencies** - Victron velib_python library

## ✨ Key Features

- **Automatic Discovery** - Scans and monitors allowlisted sensors
- **Real-time Updates** - Temperature, humidity, battery, RSSI
- **Native Integration** - Standard Venus OS temperature sensors
- **Persistent Config** - GUI changes saved automatically
- **Low Resource** - Minimal CPU and memory usage
- **Self-Healing** - Automatic reconnection and error recovery

## 🐛 Known Limitations

1. **Humidity Accuracy** - Shows ~15-20% discrepancy vs Govee app
   - Using GoveeWatcher algorithm
   - Temperature (primary metric) is highly accurate
   - Acceptable for most use cases

2. **Model Support** - Only H510x family currently supported
   - H5075, H5074, B5178 parsers not implemented
   - Easy to extend by adding parser functions

3. **BLE Range** - Limited by Bluetooth adapter
   - Typical: 10-30 meters line of sight
   - Walls/metal significantly reduce range

## 📚 Documentation

- **README.md** - Overview and quick start
- **docs/INSTALL.md** - Detailed installation guide
- **docs/DEPLOYMENT.md** - Advanced deployment and troubleshooting
- **CHANGELOG.md** - Complete version history
- **dev-notes/** - Development notes and context

## 🔧 System Requirements

- Venus OS v2.80+ (Python 3.12+)
- Govee H5101, H5102, or H5104 sensors
- Bluetooth adapter (built-in on most Victron devices)
- Root SSH access

## 🙏 Credits

- **Parser Algorithm**: Based on [GoveeWatcher](https://github.com/Thrilleratplay/GoveeWatcher)
- **Venus OS Integration**: Victron's velib_python library
- **BLE Monitoring**: BlueZ btmon utility

## 📝 Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for complete details.

## 🐞 Reporting Issues

Found a bug? Have a feature request?

- Open an [Issue](https://github.com/jsalbre/govee-ble-venus-py/issues)
- Include Venus OS version, sensor model, and relevant logs
- Check troubleshooting section first

## ⬆️ Upgrading

If you previously deployed an earlier version:

```bash
# Stop service
svc -d /service/govee-ble

# Backup config
cp /data/govee-ble/config.json /tmp/config.backup

# Extract new release
cd /tmp
tar xzf govee-ble-deploy.tar.gz
cd govee-ble-deploy
./install.sh

# Config is preserved automatically
```

## 🎯 Next Steps After Installation

1. Verify sensors appear in Venus OS GUI
2. Configure temperature alarms if desired
3. Check VRM Portal integration
4. Monitor for 24 hours to ensure stability
5. Consider adding more sensors (just update config.json)

---

**This release marks the completion of full Venus OS integration with production-ready stability.**

Enjoy monitoring your refrigerators, freezers, and other temperature-sensitive environments with native Victron integration!
