# Sample Data

This directory contains sample data collected during testing and validation.

## Files

### btmon Captures
- `btmon_raw_60sec.txt` - 60-second capture of raw btmon output
  - Contains ~989 HCI events
  - Used for testing HCI event pattern detection
  - Demonstrates btmon event name truncation behavior

### Validation Samples
- `samples_YYYYMMDD_HHMM.json` - Collected BLE advertisement samples
  - Format: `{"MAC": [{"timestamp": "...", "temperature_c": ..., ...}, ...]}`
  - Used for comparing against Govee app exports
  - Typically 15-minute collections

## Collecting New Samples

```bash
# 15-minute collection from both sensors
python3 ../src/validate_parsing_v2.py --collect \
  --macs A4:C1:38:B8:DF:A1 A4:C1:38:8E:0D:AF \
  --duration 900 \
  --output samples_$(date +%Y%m%d_%H%M).json
```

## Sample Structure

### JSON Sample Format
```json
{
  "A4:C1:38:B8:DF:A1": [
    {
      "timestamp": "2025-11-19T03:06:42.798565",
      "mac": "A4:C1:38:B8:DF:A1",
      "model": "H5101",
      "rssi": -70,
      "temperature_c": 5.3,
      "humidity": 58.7,
      "battery": 100
    }
  ]
}
```

## Validation Process

1. Collect samples using validation script
2. Export data from Govee app during same timeframe
3. Compare using 1-minute windowing strategy
4. Analyze temperature and humidity accuracy

## Known Issues

- Humidity readings show ~15-20% discrepancy from app
- Temperature readings are accurate within ±0.5°C
- Battery readings are exact matches

## Notes

- Samples collected in UTC timezone
- App exports are in local timezone (requires conversion)
- Govee app exports at 1-minute resolution
- Our samples can be higher frequency (every 2-3 seconds)
