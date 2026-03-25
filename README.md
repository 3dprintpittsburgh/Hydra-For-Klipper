# Hydra for Klipper

> Intelligent IDEX toolchange management with gcode lookahead preprocessing

## The Problem

IDEX toolchanges are blind. When a slicer inserts `T1`, the firmware has no idea where the nozzle needs to go next. Traditional approaches move the new nozzle to the *old* nozzle's last position, then the slicer moves it where it actually needs to be. This causes:

- **Wrong-color contamination**: New nozzle drags over the other color's part
- **Wasted travel**: Two moves instead of one
- **Ooze at the wrong spot**: Priming happens at the old position

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

**Toolchange Management:**
- Gcode lookahead preprocessing (Moonraker component)
- Smart park/restore with per-tool state tracking
- Collision avoidance between carriages
- Fan save/restore per tool
- LED effects during toolchange
- Temperature standby/restore (configurable standby percentage)
- Cold toolchange support (manual T0/T1 without heating)

**Calibration System:**
- T1 Z-offset calibration using MANUAL_PROBE (same KlipperScreen UI as PROBE_CALIBRATE)
- Auto-save on ACCEPT (no manual save step needed)
- XY visual alignment Phase 1: eyeball with live D-pad nudge over a reference point
- XY print test Phase 2: concentric squares with per-tool temperature control
- All offsets persist across restarts

**Print Lifecycle:**
- START_PRINT with smart T1 preheat (only when print uses toolchanges)
- END_PRINT with proper dual-tool shutdown
- PAUSE parks active tool, RESUME restores it
- User override hooks for custom actions (LEDs, notifications)

**Fan Routing:**
- M106/M107 overrides route to active tool's fan
- Explicit P parameter support (`M106 P1 S255`)
- Fan pin names configurable (not hardcoded)

**KlipperScreen Integration:**
- IDEX Dashboard: tool selection, offset status, navigation hub
- XY Alignment: Cairo visualization with adjustment preview
- Visual Calibration: D-pad live nudge interface
- Temperature dialog for calibration prints

## Requirements

- Klipper + Moonraker
- IDEX printer with `[dual_carriage]` configured
- Python 3.7+
- `[save_variables]` configured in Klipper (for offset persistence)

## Quick Start

```bash
cd ~
git clone https://github.com/thoughtspacedesigns/hydra-klipper.git
cd hydra-klipper
./scripts/install.sh
```

Then:
1. Add `[include hydra.cfg]` to your `printer.cfg`
2. Add `[hydra_idex]` section to `moonraker.conf`
3. Edit `hydra_variables.cfg` with your printer's values
4. Remove any existing T0/T1/PARK/RESTORE macros (Hydra replaces them)
5. Remove existing M106/M107 overrides (Hydra handles fan routing)
6. Remove existing START_PRINT/END_PRINT (or keep yours and skip `hydra_print.cfg`)
7. Restart Moonraker and Klipper

## Configuration

Edit `hydra_variables.cfg` - this is the **only file** you need to modify:

### Park Positions
| Variable | Default | Description |
|----------|---------|-------------|
| `park_x_t0` | -8.5 | T0 park X (typically stepper_x position_min) |
| `park_x_t1` | 497.5 | T1 park X (typically dual_carriage position_max) |
| `park_y` | 350.0 | Y position when parked |
| `safe_distance` | 80.0 | Minimum X gap between carriages (mm) |

### Toolchange Motion
| Variable | Default | Description |
|----------|---------|-------------|
| `z_hop` | 2.0 | Z lift during toolchange (mm) |
| `z_hop_speed` | 15 | Z hop speed (mm/s) |
| `travel_speed` | 200 | XY travel during toolchange (mm/s) |

### Filament Retract/Prime
| Variable | Default | Description |
|----------|---------|-------------|
| `retract_distance` | 20 | Filament retract on park (mm) |
| `retract_speed` | 30 | Retract speed (mm/s) |
| `prime_distance` | 20 | Filament prime on restore (mm) |
| `prime_speed` | 20 | Prime speed (mm/s) |

### Temperature
| Variable | Default | Description |
|----------|---------|-------------|
| `standby_temp_factor` | 0.9 | Standby temp = active × this (0.9 = 90%) |
| `min_toolchange_temp` | 170 | Minimum temp to allow retract/prime |
| `temp_restore_delta` | 10 | Wait until within this many °C of target |

### T1 Offsets
| Variable | Default | Description |
|----------|---------|-------------|
| `offset_x_t1` | 0.0 | T1 X gcode offset (set by calibration) |
| `offset_y_t1` | 0.0 | T1 Y gcode offset (set by calibration) |
| `offset_z_t1` | 0.0 | T1 Z gcode offset (set by calibration) |

### Hardware
| Variable | Default | Description |
|----------|---------|-------------|
| `fan_pin_t0` | "extruder_fan" | T0 part cooling `[output_pin]` name |
| `fan_pin_t1` | "extruder1_fan" | T1 part cooling `[output_pin]` name |
| `led_toolchange_effect` | "toolchange_wait" | LED effect during toolchange ("" to disable) |
| `led_printing_macro` | "SET_PRINTING_LEDS" | Macro to call after toolchange ("" to disable) |

### Calibration
| Variable | Default | Description |
|----------|---------|-------------|
| `cal_ref_x` | 200.0 | Visual alignment reference point X |
| `cal_ref_y` | 200.0 | Visual alignment reference point Y |
| `cal_ref_z` | 5.0 | Visual alignment reference point Z |

## Slicer Setup

### PrusaSlicer / OrcaSlicer Start G-code
```
START_PRINT BED_TEMP=[first_layer_bed_temperature] EXTRUDER_TEMP=[first_layer_temperature_0] EXTRUDER_TEMP_T1=[first_layer_temperature_1] INITIAL_TOOL=[initial_tool] TOTAL_TOOLCHANGES=[total_toolchanges]
```

### End G-code
```
END_PRINT
```

### Tool Change G-code
Leave empty - Hydra intercepts T0/T1 commands automatically.

### Important Settings
- **Retract on tool change**: Set to 0 (Hydra handles retraction)
- **Extra length on restart**: Set to 0

## How the Preprocessor Works

1. Upload a gcode file via Fluidd/Mainsail
2. Moonraker triggers Hydra's preprocessor automatically
3. Hydra scans for `T0`/`T1` commands
4. For each toolchange, looks ahead (up to 200 lines) for the first `G0`/`G1` with XY
5. Rewrites `Tn` as `IDEX_TOOL_CHANGE T=n NEXT_X=x NEXT_Y=y`
6. Adds a fingerprint comment to prevent double-processing
7. Print starts with intelligent lookahead toolchanges

Non-preprocessed files (printed via USB, etc.) fall back to saved-position mode.

## Toolchange Sequence

```
1. PARK outgoing tool (_HYDRA_PARK)
   ├── Save current print position (gcode coordinates)
   ├── Save and disable part cooling fan
   ├── Retract filament (configurable distance/speed)
   ├── Drop to standby temperature
   ├── Z hop
   └── Move to park position

2. RESTORE incoming tool (_HYDRA_RESTORE)
   ├── Switch carriage (SET_DUAL_CARRIAGE)
   ├── Activate extruder and apply gcode offsets
   ├── Restore temperature and wait
   ├── Move to NEXT position (lookahead) or saved position (fallback)
   ├── Collision safety clamp
   ├── Drop Z to print height
   ├── Prime filament (configurable distance/speed)
   └── Restore part cooling fan
```

## Calibration

### Z-Offset (T1 relative to T0)
1. Calibrate T0 normally: `PROBE_CALIBRATE` → `SAVE_CONFIG`
2. Run `CALIBRATE_IDEX_Z_OFFSET` (available in KlipperScreen Z Calibrate dropdown)
3. Paper test T1 using the same TESTZ buttons
4. Hit ACCEPT - offset auto-saves

### XY Alignment (Two-Phase)

**Phase 1 - Eyeball:**
1. Run `CALIBRATE_IDEX_XY_VISUAL` (or use KlipperScreen panel)
2. Verify T0 is over reference point
3. Switch to T1, nudge with D-pad until aligned
4. Save (~0.5mm accuracy)

**Phase 2 - Print Test:**
1. Run `CALIBRATE_IDEX_XY_ALIGNMENT` (temperature dialog in KlipperScreen)
2. Measure squares with calipers
3. Adjust in XY Alignment panel
4. Save

## Available Macros

| Macro | Description |
|-------|-------------|
| `IDEX_TOOL_CHANGE T=n` | Main toolchange (with optional NEXT_X/NEXT_Y) |
| `T0` / `T1` | Shorthand overrides (call IDEX_TOOL_CHANGE) |
| `HYDRA_INIT TOOL=n` | Initialize state (called by START_PRINT) |
| `HYDRA_STATUS` | Show full state and configuration |
| `HYDRA_RESET` | Clear all saved offsets and state |
| `START_PRINT` | Print start with smart T1 preheat |
| `END_PRINT` | Print end with cleanup |
| `PAUSE` / `RESUME` | Park/restore active tool |
| `CALIBRATE_IDEX_Z_OFFSET` | T1 Z-offset paper test |
| `CALIBRATE_IDEX_XY_VISUAL` | Phase 1 eyeball alignment |
| `CALIBRATE_IDEX_XY_ALIGNMENT` | Phase 2 square print test |
| `SHOW_IDEX_OFFSETS` | Display current offsets |

## KlipperScreen Panels

Three custom panels installed to `~/KlipperScreen/panels/`:

- **hydra_dashboard** - Hub with tool selection, status, navigation
- **hydra_align** - XY fine-tune with Cairo visualization
- **hydra_visual_cal** - Phase 1 eyeball with D-pad

Add menu entries from `examples/KlipperScreen.conf.example`.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/server/hydra/status` | GET | Version, enabled state, stats |
| `/server/hydra/file_info?filename=X` | GET | Preprocessing metadata |
| `/server/hydra/reprocess?filename=X` | POST | Force reprocess a file |

## File Structure

```
hydra-klipper/
├── moonraker_component/
│   └── hydra_idex.py              # Gcode preprocessor + API
├── klipper_macros/
│   ├── hydra.cfg                  # Core: toolchange, park, restore, init
│   ├── hydra_variables.cfg        # All user configuration
│   ├── hydra_calibration.cfg      # Z/XY calibration + offset persistence
│   ├── hydra_fan.cfg              # M106/M107 fan routing
│   └── hydra_print.cfg            # START/END_PRINT, PAUSE/RESUME
├── klipperscreen_panels/
│   ├── hydra_dashboard.py         # IDEX dashboard hub
│   ├── hydra_align.py             # XY fine-tune visualization
│   └── hydra_visual_cal.py        # Phase 1 eyeball D-pad
├── scripts/
│   └── install.sh                 # Install/uninstall
├── examples/
│   ├── moonraker.conf.example
│   ├── printer.cfg.example
│   └── KlipperScreen.conf.example
└── docs/
    └── DEVELOPMENT-NOTES.md       # Internal dev notes
```

## User Override Hooks

Define these macros in your own `printer.cfg` to add custom behavior without editing Hydra files:

```ini
[gcode_macro _HYDRA_USER_START_PRINT]
gcode:
    SET_PRINTING_LEDS
    # Your custom start actions

[gcode_macro _HYDRA_USER_END_PRINT]
gcode:
    # Your custom end actions (notifications, etc.)
```

## Troubleshooting

**Klipper says "Unknown command IDEX_TOOL_CHANGE":**
- Make sure `[include hydra.cfg]` is in your printer.cfg
- Firmware restart after adding the include

**Preprocessor not running on upload:**
- Check `[hydra_idex]` is in moonraker.conf with `enabled: True`
- Check Moonraker logs for "Hydra" messages
- Restart Moonraker

**T1 goes to wrong position:**
- Run `HYDRA_STATUS` to check saved positions
- If using lookahead, verify file was preprocessed (`/server/hydra/file_info`)
- Check collision safety isn't clamping (look for "Clamped X" messages)

**Temperature issues during toolchange:**
- Adjust `standby_temp_factor` (higher = warmer standby)
- Adjust `temp_restore_delta` (lower = wait longer for full temp)
- Adjust `min_toolchange_temp` if getting "cold extrusion" errors

**Fan not switching between tools:**
- Verify `fan_pin_t0` and `fan_pin_t1` match your `[output_pin]` names
- Remove any existing M106/M107 overrides from your config

## Compatibility

- **Slicers**: PrusaSlicer, OrcaSlicer, Cura (any slicer that outputs T0/T1)
- **Firmware**: Klipper with `[dual_carriage]` support
- **Frontends**: Fluidd, Mainsail, KlipperScreen
- **Tested on**: BTT Octopus v1.1 + BTT EBB42 Gen 2 + BTT Pad 7

## Contributing

Contributions welcome! Please open an issue or PR on GitHub.

## License

GPLv3 - See [LICENSE](LICENSE)

## Credits

- Inspired by [Happy Hare](https://github.com/moggieuk/Happy-Hare)'s gcode preprocessing architecture
- Built by [Thought Space Designs](https://thoughtspacedesigns.com) / [3D Print Pittsburgh](https://3dprintpgh.com)
