#!/bin/bash
# Govee BLE Venus OS - Installation Script
# Version: 1.1.0

set -e  # Exit on error

VERSION="1.1.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Color output (if supported)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

echo_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo
echo "==========================================="
echo "  Govee BLE Venus OS Bridge - Installer"
echo "  Version: $VERSION"
echo "==========================================="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo_error "This script must be run as root"
    echo "Please run: sudo $0"
    exit 1
fi

# Check if we're in the extracted tarball directory
if [ ! -f "$SCRIPT_DIR/data/govee-ble/govee_ble_service.py" ]; then
    echo_error "Installation files not found!"
    echo "Please extract govee-ble-deploy.tar.gz and run this script from the extracted directory."
    exit 1
fi

echo_info "Installing Govee BLE Service..."
echo

# Step 0: Stop service if running (before backup/update)
if [ -d /service/govee-ble ]; then
    echo_info "Stopping existing service..."
    svc -d /service/govee-ble 2>/dev/null || true
    sleep 2
    echo_success "Service stopped"
    echo
fi

# Step 1: Backup existing installation if present
BACKUP_DIR=""
if [ -d /data/govee-ble ]; then
    BACKUP_DIR="/data/govee-ble.backup.$(date +%Y%m%d_%H%M%S)"
    echo_info "Backing up existing installation..."
    cp -r /data/govee-ble "$BACKUP_DIR"
    echo_success "Backup saved to: $BACKUP_DIR"
    echo
fi

# Step 2: Create directories
echo_info "Creating directories..."
mkdir -p /data/govee-ble/logs
mkdir -p /data/govee-ble/ext
mkdir -p /service
echo_success "Directories created"

# Step 3: Copy source files
echo_info "Copying application files..."
cp -f "$SCRIPT_DIR"/data/govee-ble/*.py /data/govee-ble/
chmod +x /data/govee-ble/govee_ble_service.py
echo_success "Application files installed"

# Step 4: Copy velib_python dependency
echo_info "Installing dependencies..."
cp -rf "$SCRIPT_DIR"/data/govee-ble/ext/velib_python /data/govee-ble/ext/
echo_success "Dependencies installed"

# Step 5: Handle configuration file
if [ -f /data/govee-ble/config.json ]; then
    echo_warning "Existing config.json found - keeping your configuration"
    echo_info "Backup saved to: /data/govee-ble/config.json.backup.$(date +%Y%m%d_%H%M%S)"
    cp /data/govee-ble/config.json /data/govee-ble/config.json.backup.$(date +%Y%m%d_%H%M%S)
else
    echo_info "Creating default configuration..."
    cp "$SCRIPT_DIR"/data/govee-ble/config.json /data/govee-ble/config.json
    echo_success "Default config created: /data/govee-ble/config.json"
    echo_warning "You must edit config.json and add your sensor MAC addresses!"
fi

# Step 6: Copy helper scripts
echo_info "Installing helper scripts..."
if [ -f "$SCRIPT_DIR"/data/govee-ble/add-sensor.sh ]; then
    cp -f "$SCRIPT_DIR"/data/govee-ble/add-sensor.sh /data/govee-ble/
    chmod +x /data/govee-ble/add-sensor.sh
    echo_success "Helper scripts installed"
fi

# Step 7: Install service (Venus OS style - persist across reboots)
echo_info "Installing runit service..."

# Copy service files to /data (persists across reboots)
echo_info "Installing service files to /data/govee-ble/service..."
mkdir -p /data/govee-ble/service
cp -rf "$SCRIPT_DIR"/service/govee-ble/* /data/govee-ble/service/
chmod +x /data/govee-ble/service/run

# Create symlink in /service
echo_info "Creating service symlink..."
rm -rf /service/govee-ble 2>/dev/null || true
ln -sf /data/govee-ble/service /service/govee-ble

# Add to rc.local to recreate symlink on boot
if [ -f /data/rc.local ]; then
    if ! grep -q '/service/govee-ble' /data/rc.local; then
        echo_info "Adding service to rc.local for boot persistence..."
        echo "" >> /data/rc.local
        echo "# Govee BLE Service" >> /data/rc.local
        echo "ln -sf /data/govee-ble/service /service/govee-ble" >> /data/rc.local
    else
        echo_info "Service already in rc.local"
    fi
else
    echo_warning "rc.local not found, creating it..."
    cat > /data/rc.local << 'RCEOF'
#!/bin/bash
# Govee BLE Service
ln -sf /data/govee-ble/service /service/govee-ble
RCEOF
    chmod +x /data/rc.local
fi

echo_success "Service installed and configured for boot persistence"

# Step 8: Check configuration
echo
echo "==========================================="
echo "  Installation Complete!"
echo "==========================================="
echo

if [ ! -s /data/govee-ble/config.json ] || ! grep -q '"sensors"' /data/govee-ble/config.json; then
    echo_warning "Configuration needed!"
    echo
    echo "Before starting the service, you must:"
    echo "  1. Find your Govee sensor MAC addresses"
    echo "  2. Add them to /data/govee-ble/config.json"
    echo
    echo "The service will log discovered sensors automatically."
    echo "Monitor logs to find sensor MAC addresses:"
    echo "  tail -f /data/govee-ble/logs/govee_ble.log"
    echo
    CONFIG_READY=false
else
    # Check if sensors array has any entries using Python for accurate JSON parsing
    SENSOR_COUNT=$(python3 -c "import json; f=open('/data/govee-ble/config.json'); c=json.load(f); print(len(c.get('sensors', [])))" 2>/dev/null || echo "0")
    if [ "$SENSOR_COUNT" -eq 0 ]; then
        echo_warning "No sensors configured!"
        echo
        echo "The service will log discovered sensors automatically."
        echo "Monitor logs to find sensor MAC addresses:"
        echo "  tail -f /data/govee-ble/logs/govee_ble.log"
        echo
        echo "Then use /data/govee-ble/add-sensor.sh to add them."
        echo
        CONFIG_READY=false
    else
        echo_success "Found $SENSOR_COUNT sensor(s) in configuration"
        CONFIG_READY=true
    fi
fi

# Notify if no sensors configured, but start service anyway
if [ "$CONFIG_READY" != true ]; then
    echo_warning "No sensors configured!"
    echo
    echo "The service will start and log any Govee sensors it discovers."
    echo "To monitor specific sensors, you need to add them to the sensors array."
    echo
    echo "How to find sensor MAC addresses:"
    echo "  1. Start the service: svc -u /service/govee-ble"
    echo "  2. Monitor logs: tail -f /data/govee-ble/logs/govee_ble.log"
    echo "  3. Look for: 'Discovered Govee sensor not in sensors: MAC (name)'"
    echo
    echo "After finding your sensor MAC addresses:"
    echo "  1. Use add-sensor script: /data/govee-ble/add-sensor.sh MAC [name] [type]"
    echo "  2. Or edit manually: /data/govee-ble/config.json (sensors array)"
    echo "  3. Restart service: svc -t /service/govee-ble"
    echo
fi

# Always offer to start the service
echo
read -p "Start the service now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo_info "Starting service..."
    svc -u /service/govee-ble
    sleep 2

    # Check status
    if svstat /service/govee-ble | grep -q "up"; then
        echo_success "Service started successfully!"
        echo
        echo "Monitor logs with:"
        echo "  tail -f /data/govee-ble/logs/govee_ble.log"
        echo
        echo "Check status with:"
        echo "  svstat /service/govee-ble"
    else
        echo_error "Service failed to start"
        echo "Check logs: tail -n 50 /data/govee-ble/logs/govee_ble.log"
    fi
else
    echo_info "Service not started"
    echo "Start manually with: svc -u /service/govee-ble"
fi

echo
if [ -n "$BACKUP_DIR" ]; then
    echo "==========================================="
    echo "  Backup Information"
    echo "==========================================="
    echo
    echo_success "Previous installation backed up to:"
    echo "  $BACKUP_DIR"
    echo
    echo "To restore backup if needed:"
    echo "  svc -d /service/govee-ble"
    echo "  rm -rf /data/govee-ble"
    echo "  mv $BACKUP_DIR /data/govee-ble"
    echo "  svc -u /service/govee-ble"
    echo
fi

echo "==========================================="
echo "  Useful Commands"
echo "==========================================="
echo
echo "Add sensor:       /data/govee-ble/add-sensor.sh <MAC> [name] [type]"
echo "Edit config:      vi /data/govee-ble/config.json"
echo "Start service:    svc -u /service/govee-ble"
echo "Stop service:     svc -d /service/govee-ble"
echo "Restart service:  svc -t /service/govee-ble"
echo "Check status:     svstat /service/govee-ble"
echo "View logs:        tail -f /data/govee-ble/logs/govee_ble.log"
echo "Find sensors:     Look for 'Discovered Govee sensor' in logs"
echo
echo "Documentation:    https://github.com/jsalbre/govee-ble-venus-py"
echo
