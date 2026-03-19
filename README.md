# Hydra for Klipper

> Intelligent IDEX toolchange management with gcode lookahead preprocessing

## The Problem

IDEX toolchanges are blind. When a slicer inserts `T1`, the firmware has no idea where the nozzle needs to go next. Traditional approaches move the new nozzle to the *old* nozzle's last position, then the slicer moves it to where it actually needs to be. This causes:

- **Wrong-color contamination**: The new nozzle drags over the other color's part
- **Wasted travel time**: Two moves (to old position, then to new) instead of one
- **Ooze at the wrong spot**: Priming happens at the old position, not where printing resumes

## How Hydra Solves It

Hydra adds a **Moonraker preprocessor** that scans uploaded gcode files and finds the next XY position after each toolchange. It rewrites `T0`/`T1` commands as:

```gcode
; Before (raw slicer output):
T1

; After (Hydra preprocessed):
IDEX_TOOL_CHANGE T=1 NEXT_X=201.101 NEXT_Y=188.646 ; T1
```

The Klipper macros use `NEXT_X`/`NEXT_Y` to move the incoming nozzle **directly to where it's needed**, prime there, and start printing immediately.

## Features

- **Gcode lookahead** - Preprocessor finds the next print position after each toolchange
- **Smart park/restore** - Park outgoing tool, position incoming tool at the next print location
- **Collision avoidance** - Safe distance enforcement between carriages
- **Configurable everything** - Retract, prime, speeds, park positions, offsets
- **Fallback mode** - Works with non-preprocessed gcode (uses saved positions)
- **Cold toolchange support** - Manual T0/T1 switching without heating
- **Moonraker API** - Status, file info, and reprocess endpoints
- **Update manager** - Automatic updates via Fluidd/Mainsail

## Requirements

- Klipper + Moonraker
- IDEX printer with `[dual_carriage]` configured
- Python 3.7+

## Quick Start

```bash
cd ~
git clone https://github.com/thoughtspacedesigns/hydra-klipper.git
cd hydra-klipper
./scripts/install.sh
```

Then follow the post-install instructions to:
1. Add `[include hydra.cfg]` to `printer.cfg`
2. Add `[hydra_idex]` to `moonraker.conf`
3. Edit `hydra_variables.cfg` with your printer's values
4. Remove existing T0/T1 macros
5. Restart Moonraker and Klipper

## Configuration

Edit `hydra_variables.cfg` - this is the only file you need to modify:

| Variable | Default | Description |
|----------|---------|-------------|
| `park_x_t0` | -8.5 | T0 park X position |
| `park_x_t1` | 497.5 | T1 park X position |
| `park_y` | 350.0 | Y position when parked |
| `safe_distance` | 80.0 | Min X gap between carriages |
| `z_hop` | 2.0 | Z lift during toolchange (mm) |
| `retract_distance` | 20 | Filament retract on park (mm) |
| `prime_distance` | 20 | Filament prime on restore (mm) |
| `offset_x_t1` | 0.0 | T1 X gcode offset |
| `offset_y_t1` | 0.0 | T1 Y gcode offset |
| `offset_z_t1` | 0.0 | T1 Z gcode offset |

See [docs/configuration.md](docs/configuration.md) for the full reference.

## How the Preprocessor Works

1. You upload a gcode file via Fluidd/Mainsail
2. Moonraker triggers Hydra's preprocessor
3. Hydra scans for `T0`/`T1` commands
4. For each toolchange, it looks ahead (up to 200 lines) for the first `G0`/`G1` with XY coordinates
5. Rewrites the `Tn` as `IDEX_TOOL_CHANGE T=n NEXT_X=x NEXT_Y=y`
6. Adds a fingerprint to prevent double-processing
7. File is ready to print with intelligent toolchanges

## Toolchange Sequence

```
1. PARK outgoing tool
   - Save current position
   - Retract filament
   - Z hop
   - Move to park position
   - Drop to standby temperature

2. RESTORE incoming tool
   - Switch carriage
   - Apply gcode offsets
   - Move to NEXT position (lookahead) or saved position (fallback)
   - Wait for temperature if needed
   - Drop Z back to print height
   - Prime filament at the print position
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/server/hydra/status` | GET | Version, stats, enabled state |
| `/server/hydra/file_info?filename=X` | GET | Preprocessing metadata for a file |
| `/server/hydra/reprocess?filename=X` | POST | Force reprocess a file |

## Slicer Setup

No slicer changes required for basic operation. Hydra intercepts standard `T0`/`T1` commands.

For optimal integration, use this PrusaSlicer start gcode:
```
START_PRINT BED_TEMP=[first_layer_bed_temperature] EXTRUDER_TEMP=[first_layer_temperature_0] EXTRUDER_TEMP_T1=[first_layer_temperature_1] INITIAL_TOOL=[initial_tool] TOTAL_TOOLCHANGES=[total_toolchanges]
```

## Compatibility

- **Slicers**: PrusaSlicer, OrcaSlicer, Cura (any slicer that outputs `T0`/`T1` commands)
- **Firmware**: Klipper with `[dual_carriage]` support
- **Frontends**: Fluidd, Mainsail, KlipperScreen

## Contributing

Contributions welcome! Please open an issue or PR on GitHub.

## License

GPLv3 - See [LICENSE](LICENSE)

## Credits

- Inspired by [Happy Hare](https://github.com/moggieuk/Happy-Hare)'s gcode preprocessing architecture
- Built by [Thought Space Designs](https://thoughtspacedesigns.com)
