#!/usr/bin/env bash
set -euo pipefail

# BlinkStick Health Monitor — Installer
# Run as root or with sudo. Safe to re-run (idempotent).
#
# Usage:
#   sudo ./install-monitor.sh              # install + detect baseline + enable service
#   sudo ./install-monitor.sh --reconfigure # re-detect current state as healthy baseline
#   sudo ./install-monitor.sh --uninstall   # stop service, remove files

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONITOR_SRC="${SCRIPT_DIR}/blinkstick-monitor.py"
MONITOR_DST="/usr/local/bin/blinkstick-monitor"
SERVICE_FILE="/etc/systemd/system/blinkstick-monitor.service"
CONFIG_FILE="/etc/blinkstick-monitor.conf"
PYTHON="$(command -v python3 || true)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; }
die()   { error "$@"; exit 1; }

# ---- Pre-flight checks ----

check_root() {
    if [[ $EUID -ne 0 ]]; then
        die "This script must be run as root (use sudo)"
    fi
}

check_source_files() {
    if [[ ! -f "$MONITOR_SRC" ]]; then
        die "Monitor script not found at ${MONITOR_SRC}"
    fi
    if [[ ! -f "${SCRIPT_DIR}/setup.py" ]]; then
        die "BlinkStick source repo not found at ${SCRIPT_DIR}"
    fi
}

# ---- Install dependencies ----

install_pip() {
    if $PYTHON -m pip --version &>/dev/null; then
        info "pip already installed"
        return
    fi

    info "Installing pip..."
    if command -v apt-get &>/dev/null; then
        apt-get update -qq
        apt-get install -y -qq python3-pip python3-setuptools python3-dev >/dev/null 2>&1
    elif command -v dnf &>/dev/null; then
        dnf install -y -q python3-pip python3-setuptools python3-devel
    elif command -v pacman &>/dev/null; then
        pacman -Sy --noconfirm python-pip python-setuptools
    elif command -v apk &>/dev/null; then
        apk add --no-cache py3-pip py3-setuptools
    else
        die "Unsupported package manager — install python3-pip manually"
    fi

    $PYTHON -m pip --version &>/dev/null || die "pip installation failed"
    info "pip installed"
}

install_blinkstick() {
    # Check if already installed from this source
    if $PYTHON -c "import blinkstick" 2>/dev/null; then
        info "blinkstick package already installed"
    else
        info "Installing blinkstick from source..."
    fi

    # Always reinstall to pick up any changes
    $PYTHON -m pip install --break-system-packages -e "${SCRIPT_DIR}" -q 2>/dev/null \
        || $PYTHON -m pip install -e "${SCRIPT_DIR}" -q
    $PYTHON -c "from blinkstick import blinkstick; print(f'  blinkstick {blinkstick.__version__} OK')" 2>/dev/null \
        || $PYTHON -c "from blinkstick import blinkstick; print('  blinkstick installed OK')"
}

install_libusb() {
    # Ensure libusb is available for pyusb
    local need_libusb=false
    local need_dev=false

    if ! ldconfig -p 2>/dev/null | grep -q libusb; then
        need_libusb=true
    fi

    # Also install dev headers in case pyusb needs to compile
    if [[ "$need_libusb" == "true" ]]; then
        info "Installing libusb..."
    else
        info "libusb already installed"
    fi

    if command -v apt-get &>/dev/null; then
        apt-get install -y -qq libusb-1.0-0 libusb-1.0-0-dev >/dev/null 2>&1 || true
    elif command -v dnf &>/dev/null; then
        dnf install -y -q libusb1 libusb1-devel 2>/dev/null || true
    elif command -v pacman &>/dev/null; then
        pacman -Sy --noconfirm libusb 2>/dev/null || true
    elif command -v apk &>/dev/null; then
        apk add --no-cache libusb libusb-dev 2>/dev/null || true
    fi
}

install_udev_rules() {
    # Install udev rules so non-root users (and the service) can access BlinkStick USB devices
    local UDEV_RULE="/etc/udev/rules.d/85-blinkstick.rules"

    if [[ -f "$UDEV_RULE" ]]; then
        info "udev rules already installed"
        return
    fi

    info "Installing udev rules for BlinkStick USB access"
    cat > "$UDEV_RULE" <<'UDEVEOF'
# BlinkStick USB LED devices
# Vendor: 0x20A0 (Clay Logic), Products: 0x41E5 (BlinkStick), 0x41E6 variants
SUBSYSTEM=="usb", ATTR{idVendor}=="20a0", ATTR{idProduct}=="41e5", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="20a0", ATTR{idProduct}=="41e6", MODE="0666"
# Catch-all for any Clay Logic HID device (covers all BlinkStick variants)
SUBSYSTEM=="usb", ATTR{idVendor}=="20a0", MODE="0666"
UDEVEOF

    # Reload udev rules
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger 2>/dev/null || true
    info "udev rules installed — BlinkStick accessible without sudo after re-plug"
}

# ---- Install monitor ----

install_monitor_script() {
    info "Installing monitor script to ${MONITOR_DST}"
    cp "$MONITOR_SRC" "$MONITOR_DST"
    chmod +x "$MONITOR_DST"
}

install_systemd_service() {
    # Determine if docker is present for the service dependency
    local docker_deps=""
    if command -v docker &>/dev/null; then
        docker_deps="docker.service"
    fi

    info "Installing systemd service"
    cat > "$SERVICE_FILE" <<SERVICEEOF
[Unit]
Description=BlinkStick Health Monitor
After=network-online.target local-fs.target${docker_deps:+ ${docker_deps}}
Wants=network-online.target${docker_deps:+ ${docker_deps}}

[Service]
Type=simple
ExecStart=${PYTHON} ${MONITOR_DST}
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=5
WatchdogSec=120
StandardOutput=journal
StandardError=journal
SyslogIdentifier=blinkstick-monitor

# Hardening
ProtectSystem=strict
ReadWritePaths=/etc/blinkstick-monitor.conf
PrivateTmp=true
NoNewPrivileges=false

[Install]
WantedBy=multi-user.target
SERVICEEOF

    systemctl daemon-reload
}

detect_baseline() {
    if [[ -f "$CONFIG_FILE" && "${1:-}" != "--force" ]]; then
        info "Config already exists at ${CONFIG_FILE} — keeping it"
        info "  (use --reconfigure to re-detect)"
        return
    fi

    info "Detecting current system state as healthy baseline..."
    $PYTHON "$MONITOR_DST" --reconfigure
}

enable_service() {
    info "Enabling and starting blinkstick-monitor service"
    systemctl enable blinkstick-monitor.service
    systemctl restart blinkstick-monitor.service
    sleep 2
    if systemctl is-active --quiet blinkstick-monitor.service; then
        info "Service is running"
    else
        error "Service failed to start — check: journalctl -u blinkstick-monitor -n 30"
        return 1
    fi
}

verify_blinkstick() {
    info "Checking for BlinkStick device..."

    # First check if we can even see USB devices
    if ! lsusb &>/dev/null; then
        warn "lsusb not found — installing usbutils"
        if command -v apt-get &>/dev/null; then
            apt-get install -y -qq usbutils >/dev/null 2>&1
        elif command -v dnf &>/dev/null; then
            dnf install -y -q usbutils 2>/dev/null
        elif command -v pacman &>/dev/null; then
            pacman -Sy --noconfirm usbutils 2>/dev/null
        fi
    fi

    # Check if BlinkStick is visible on the USB bus at all
    if lsusb 2>/dev/null | grep -qi "20a0"; then
        info "BlinkStick detected on USB bus"
    else
        warn "No BlinkStick detected on USB bus — is it plugged in?"
        warn "  The service will keep retrying until a BlinkStick is connected"
        return
    fi

    # Try to open it via the library
    local result
    result=$($PYTHON -c "
from blinkstick import blinkstick
s = blinkstick.find_first()
if s:
    print(f'FOUND:{s.get_serial()}:{s.get_description()}')
else:
    print('NOTFOUND')
" 2>&1) || true

    case "$result" in
        FOUND:*)
            local serial desc
            serial=$(echo "$result" | cut -d: -f2)
            desc=$(echo "$result" | cut -d: -f3-)
            info "BlinkStick ready: ${serial} (${desc})"
            ;;
        NOTFOUND)
            warn "BlinkStick on USB bus but can't open — try unplugging and re-plugging"
            warn "  (udev rules were just installed; re-plug triggers them)"
            ;;
        *"Access denied"*|*"Permission"*)
            warn "BlinkStick found but permission denied — re-plug the device"
            warn "  (udev rules were just installed; re-plug triggers them)"
            ;;
        *)
            warn "Could not probe BlinkStick: ${result}"
            ;;
    esac
}

show_status() {
    echo ""
    echo "============================================"
    echo " BlinkStick Monitor — Installation Complete"
    echo "============================================"
    echo ""
    echo " Config:      ${CONFIG_FILE}"
    echo " Script:      ${MONITOR_DST}"
    echo " Service:     blinkstick-monitor.service"
    echo ""
    echo " Commands:"
    echo "   sudo blinkstick-monitor --status         # check health now"
    echo "   sudo blinkstick-monitor --reconfigure    # re-detect baseline"
    echo "   sudo systemctl restart blinkstick-monitor # restart service"
    echo "   sudo systemctl kill -s HUP blinkstick-monitor  # reload config"
    echo "   journalctl -u blinkstick-monitor -f      # tail logs"
    echo ""
    echo " Colors: GREEN=ok  RED=critical  YELLOW=warning  BLUE=starting"
    echo ""
}

# ---- Uninstall ----

do_uninstall() {
    info "Stopping and disabling service..."
    systemctl stop blinkstick-monitor.service 2>/dev/null || true
    systemctl disable blinkstick-monitor.service 2>/dev/null || true

    info "Removing files..."
    rm -f "$SERVICE_FILE" "$MONITOR_DST"
    systemctl daemon-reload

    echo ""
    info "Uninstalled. Config preserved at ${CONFIG_FILE}"
    info "  (delete manually if you don't need it: sudo rm ${CONFIG_FILE})"
}

# ---- Main ----

main() {
    check_root

    case "${1:-}" in
        --uninstall)
            do_uninstall
            exit 0
            ;;
        --reconfigure)
            check_source_files
            install_monitor_script
            detect_baseline --force
            if systemctl is-active --quiet blinkstick-monitor.service 2>/dev/null; then
                systemctl restart blinkstick-monitor.service
                info "Service restarted with new config"
            fi
            exit 0
            ;;
        --help|-h)
            echo "Usage: $0 [--reconfigure|--uninstall|--help]"
            echo ""
            echo "  (no args)       Full install: deps, blinkstick, monitor, systemd"
            echo "  --reconfigure   Re-detect current state as healthy baseline"
            echo "  --uninstall     Stop service and remove installed files"
            exit 0
            ;;
        "")
            ;;
        *)
            die "Unknown option: $1 (try --help)"
            ;;
    esac

    check_source_files

    echo "============================================"
    echo " BlinkStick Health Monitor — Installer"
    echo "============================================"
    echo ""

    install_libusb
    install_udev_rules
    install_pip
    install_blinkstick
    install_monitor_script
    install_systemd_service
    detect_baseline
    verify_blinkstick
    enable_service
    show_status
}

main "$@"
