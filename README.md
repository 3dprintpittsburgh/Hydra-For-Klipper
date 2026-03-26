<p align="center">
  <img src="assets/hydra-logo.svg" alt="Hydra for Klipper" width="480">
</p>

<p align="center">
  <em>Intelligent IDEX toolchange management with gcode lookahead preprocessing</em>
</p>

---

## The Problem

IDEX toolchanges are blind. When a slicer inserts `T1`, the firmware has no idea where the nozzle needs to go next. Traditional approaches move the new nozzle to the *old* nozzle's last position, then the slicer moves it where it actually needs to be. This causes wrong-color contamination, wasted travel, and ooze at the wrong spot.

## How Hydra Solves It

Hydra adds a **Moonraker preprocessor** that scans uploaded gcode files and finds the next XY position after each toolchange:

```gcode
; Before (raw slicer output):
T1

; After (Hydra preprocessed):
IDEX_TOOL_CHANGE T=1 NEXT_X=201.101 NEXT_Y=188.646 ; T1
```

The Klipper macros move the incoming nozzle **directly to where it's needed**, prime there, and start printing immediately. Falls back to saved-position mode for non-preprocessed files.

## Features

- **Gcode lookahead** - Moonraker preprocessor finds next print position after each toolchange
- **Smart toolchange** - Park, retract, standby temp, switch, restore temp, prime, fan management
- **Collision avoidance** - Safe distance enforcement between carriages
- **Calibration system** - Z-offset paper test with auto-save, two-phase XY alignment
- **Zone LED effects** - Per-tool LED zones with state-aware effects (printing, standby, preheating)
- **Fan routing** - M106/M107 overrides route to active tool's fan automatically
- **Print lifecycle** - START/END_PRINT with smart T1 preheat and user override hooks
- **KlipperScreen panels** - Dashboard, XY alignment visualization, visual calibration D-pad
- **Cold toolchange** - Manual T0/T1 switching without heating

## Requirements

- Klipper + Moonraker
- IDEX printer with `[dual_carriage]` configured
- Python 3.7+
- `[save_variables]` configured in Klipper

## Quick Start

```bash
cd ~
git clone https://github.com/3dprintpittsburgh/Hydra-For-Klipper.git
cd Hydra-For-Klipper
./scripts/install.sh
```

Then:
1. Add `[include hydra.cfg]` to your `printer.cfg`
2. Add `[hydra_idex]` section to `moonraker.conf`
3. Edit `hydra_variables.cfg` with your printer's values
4. Remove any existing T0/T1/M106/M107/START_PRINT macros
5. Restart Moonraker and Klipper

## Documentation

| Guide | Description |
|-------|-------------|
| [Configuration Reference](docs/configuration.md) | All variables, slicer setup, file structure |
| [Calibration Guide](docs/calibration.md) | Z-offset, XY visual alignment, XY print test |
| [LED Setup](docs/led-setup.md) | Zone-aware LED effects with per-tool states |
| [Preprocessor](docs/preprocessor.md) | How gcode lookahead works |
| [KlipperScreen](docs/klipperscreen.md) | Dashboard and calibration panels |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |
| [Development Notes](docs/DEVELOPMENT-NOTES.md) | Internal architecture and lessons learned |

## Toolchange Sequence

```
1. PARK outgoing tool
   ├── Save position, save/disable fan
   ├── Retract filament, drop to standby temp
   ├── Z hop, move to park position
   └── LED: zone → standby

2. RESTORE incoming tool
   ├── Switch carriage, apply offsets
   ├── Restore temp, wait for ready
   ├── Move to NEXT position (lookahead) or saved position
   ├── Drop Z, prime filament, restore fan
   └── LED: zone → printing
```

## Compatibility

- **Slicers**: PrusaSlicer, OrcaSlicer, Cura
- **Firmware**: Klipper with `[dual_carriage]`
- **Frontends**: Fluidd, Mainsail, KlipperScreen

## Contributing

Contributions welcome! Please open an issue or PR on GitHub.

## License

GPLv3 - See [LICENSE](LICENSE)

## Credits

- Inspired by [Happy Hare](https://github.com/moggieuk/Happy-Hare)'s gcode preprocessing architecture
- Built by [3D Print Pittsburgh](https://3dprintpgh.com)
