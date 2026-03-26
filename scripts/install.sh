#!/bin/bash
# Hydra for Klipper - Installation Script

set -e

HYDRA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MOONRAKER_DIR="${HOME}/moonraker"
PRINTER_DATA="${HOME}/printer_data"
CONFIG_DIR="${PRINTER_DATA}/config"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[Hydra]${NC} $1"; }
warn() { echo -e "${YELLOW}[Hydra]${NC} $1"; }
error() { echo -e "${RED}[Hydra]${NC} $1"; }

# Detect Moonraker install
if [ ! -d "$MOONRAKER_DIR" ]; then
    MOONRAKER_DIR="${HOME}/moonraker-env/../moonraker"
    if [ ! -d "$MOONRAKER_DIR" ]; then
        error "Could not find Moonraker installation"
        error "Set MOONRAKER_DIR environment variable and try again"
        exit 1
    fi
fi
MOONRAKER_DIR="$(cd "$MOONRAKER_DIR" && pwd)"

# Detect printer_data
if [ ! -d "$PRINTER_DATA" ]; then
    PRINTER_DATA="${HOME}/printer_data"
    if [ ! -d "$PRINTER_DATA" ]; then
        error "Could not find printer_data directory"
        exit 1
    fi
fi

info "Hydra for Klipper Installer"
info "=============================="
info "Hydra dir:     $HYDRA_DIR"
info "Moonraker dir: $MOONRAKER_DIR"
info "Config dir:    $CONFIG_DIR"
echo ""

if [ "$1" = "--uninstall" ]; then
    info "Uninstalling Hydra..."

    # Remove symlink
    rm -f "${MOONRAKER_DIR}/moonraker/components/hydra_idex.py"
    info "Removed Moonraker component symlink"

    warn "Manual cleanup needed:"
    warn "  1. Remove [include hydra.cfg] from printer.cfg"
    warn "  2. Remove [hydra_idex] section from moonraker.conf"
    warn "  3. Remove [update_manager hydra] section from moonraker.conf"
    warn "  4. Optionally delete ${CONFIG_DIR}/hydra.cfg and hydra_variables.cfg"

    info "Uninstall complete. Restart Moonraker and Klipper."
    exit 0
fi

# Install Moonraker component
info "Installing Moonraker component..."
COMPONENT_DIR="${MOONRAKER_DIR}/moonraker/components"
if [ ! -d "$COMPONENT_DIR" ]; then
    error "Moonraker components directory not found: $COMPONENT_DIR"
    exit 1
fi

ln -sf "${HYDRA_DIR}/moonraker_component/hydra_idex.py" \
       "${COMPONENT_DIR}/hydra_idex.py"
info "Symlinked hydra_idex.py -> ${COMPONENT_DIR}/"

# Copy macro files
# hydra_variables.cfg is the only user-edited file - don't overwrite if exists
# All other macro files are always updated to latest version
info "Installing Klipper macros..."

for macro_file in hydra.cfg hydra_calibration.cfg hydra_fan.cfg hydra_print.cfg hydra_leds.cfg hydra_wipe.cfg; do
    cp "${HYDRA_DIR}/klipper_macros/${macro_file}" "${CONFIG_DIR}/${macro_file}"
    info "Installed ${macro_file}"
done

if [ ! -f "${CONFIG_DIR}/hydra_variables.cfg" ]; then
    cp "${HYDRA_DIR}/klipper_macros/hydra_variables.cfg" "${CONFIG_DIR}/hydra_variables.cfg"
    info "Installed hydra_variables.cfg (edit this with your printer's values)"
else
    warn "hydra_variables.cfg already exists - skipping (preserving your config)"
fi

# Install KlipperScreen panels (if KlipperScreen is installed)
KLIPPERSCREEN_DIR="${HOME}/KlipperScreen"
if [ -d "${KLIPPERSCREEN_DIR}/panels" ]; then
    info "Installing KlipperScreen panels..."
    for panel in hydra_dashboard hydra_align hydra_visual_cal hydra_settings hydra_cal_progress; do
        ln -sf "${HYDRA_DIR}/klipperscreen_panels/${panel}.py" \
               "${KLIPPERSCREEN_DIR}/panels/${panel}.py"
        info "  Symlinked ${panel}.py"
    done
    warn ""
    warn "Add Hydra menu entries to KlipperScreen.conf"
    warn "See: ${HYDRA_DIR}/examples/KlipperScreen.conf.example"
    warn ""
else
    warn "KlipperScreen not found at ${KLIPPERSCREEN_DIR} - skipping panel install"
fi

# Check for existing T0/T1 macros
if grep -q '\[gcode_macro T0\]' "${CONFIG_DIR}/printer.cfg" 2>/dev/null || \
   grep -q '\[gcode_macro T1\]' "${CONFIG_DIR}/printer.cfg" 2>/dev/null; then
    warn ""
    warn "EXISTING T0/T1 MACROS DETECTED in printer.cfg!"
    warn "Hydra provides its own T0/T1 macros. You must remove or comment out"
    warn "your existing T0/T1 macro definitions to avoid conflicts."
    warn ""
fi

echo ""
info "=============================="
info "Installation complete!"
info ""
info "Next steps:"
info ""
info "1. Add to your printer.cfg:"
info "   [include hydra.cfg]"
info ""
info "2. Add to your moonraker.conf:"
info "   [hydra_idex]"
info "   enabled: True"
info "   auto_preprocess: True"
info ""
info "3. Add update manager to moonraker.conf:"
info "   [update_manager hydra]"
info "   type: git_repo"
info "   path: ${HYDRA_DIR}"
info "   origin: https://github.com/3dprintpittsburgh/Hydra-For-Klipper.git"
info "   managed_services: moonraker klipper"
info ""
info "4. Edit hydra_variables.cfg with your printer's park positions and offsets"
info ""
info "5. Remove or comment out existing T0/T1 macros in your config"
info ""
info "6. Restart Moonraker and Klipper"
