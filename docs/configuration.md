# Configuration Reference

All Hydra configuration lives in `hydra_variables.cfg` - this is the **only file** you need to edit.

## Park Positions

| Variable | Default | Description |
|----------|---------|-------------|
| `park_x_t0` | -8.5 | T0 park X (typically stepper_x position_min) |
| `park_x_t1` | 497.5 | T1 park X (typically dual_carriage position_max) |
| `park_y` | 350.0 | Y position when parked |
| `safe_distance` | 80.0 | Minimum X gap between carriages (mm) |

## Toolchange Motion

| Variable | Default | Description |
|----------|---------|-------------|
| `z_hop` | 2.0 | Z lift during toolchange (mm) |
| `z_hop_speed` | 15 | Z hop speed (mm/s) |
| `travel_speed` | 200 | XY travel during toolchange (mm/s) |

## Filament Retract/Prime

| Variable | Default | Description |
|----------|---------|-------------|
| `retract_distance` | 20 | Filament retract on park (mm) |
| `retract_speed` | 30 | Retract speed (mm/s) |
| `prime_distance` | 20 | Filament prime on restore (mm) |
| `prime_speed` | 20 | Prime speed (mm/s) |

## Temperature

| Variable | Default | Description |
|----------|---------|-------------|
| `standby_temp_factor` | 0.9 | Standby temp = active × this (0.9 = 90%) |
| `min_toolchange_temp` | 170 | Minimum temp to allow retract/prime |
| `temp_restore_delta` | 10 | Wait until within this many °C of target |

## T1 Offsets

These are typically set by the calibration macros, not edited manually.

| Variable | Default | Description |
|----------|---------|-------------|
| `offset_x_t1` | 0.0 | T1 X gcode offset |
| `offset_y_t1` | 0.0 | T1 Y gcode offset |
| `offset_z_t1` | 0.0 | T1 Z gcode offset |

## Fan Pins

| Variable | Default | Description |
|----------|---------|-------------|
| `fan_pin_t0` | "extruder_fan" | T0 part cooling `[output_pin]` name |
| `fan_pin_t1` | "extruder1_fan" | T1 part cooling `[output_pin]` name |

Your `printer.cfg` must have matching `[output_pin]` sections:
```ini
[output_pin extruder_fan]
pin: PA8      # Your T0 fan pin
pwm: true

[output_pin extruder1_fan]
pin: PE5      # Your T1 fan pin
pwm: true
```

## LED Configuration

See [LED Setup](led-setup.md) for full details.

| Variable | Default | Description |
|----------|---------|-------------|
| `led_strip_name` | "main_leds" | Your `[neopixel]` section name ("" to disable) |
| `led_zone_left_start` | 1 | First pixel for T0 zone |
| `led_zone_left_end` | 12 | Last pixel for T0 zone |
| `led_zone_right_start` | 13 | First pixel for T1 zone |
| `led_zone_right_end` | 24 | Last pixel for T1 zone |
| `led_effect_toolchange` | "hydra_toolchange" | Global toolchange effect |
| `led_effect_printing` | "hydra_printing" | Zone: tool actively printing |
| `led_effect_standby` | "hydra_standby" | Zone: tool parked, holding temp |
| `led_effect_preheating` | "hydra_preheating" | Zone: tool heating up |
| `led_effect_idle` | "" | Zone: tool cold (blank = off) |

## Calibration Reference Point

Used by the visual XY alignment (Phase 1 eyeball calibration).

| Variable | Default | Description |
|----------|---------|-------------|
| `cal_ref_x` | 200.0 | Reference point X |
| `cal_ref_y` | 200.0 | Reference point Y |
| `cal_ref_z` | 5.0 | Reference point Z |

## Slicer Setup

### PrusaSlicer / OrcaSlicer

**Start G-code:**
```
START_PRINT BED_TEMP=[first_layer_bed_temperature] EXTRUDER_TEMP=[first_layer_temperature_0] EXTRUDER_TEMP_T1=[first_layer_temperature_1] INITIAL_TOOL=[initial_tool] TOTAL_TOOLCHANGES=[total_toolchanges]
```

**End G-code:**
```
END_PRINT
```

**Tool Change G-code:** Leave empty. Hydra intercepts T0/T1 automatically.

**Filament Settings:**
- Retract on tool change: 0 (Hydra handles retraction)
- Extra length on restart: 0

## User Override Hooks

Define these in your `printer.cfg` for custom behavior without editing Hydra:

```ini
[gcode_macro _HYDRA_USER_START_PRINT]
gcode:
    # Your custom start actions (LEDs, notifications, etc.)

[gcode_macro _HYDRA_USER_END_PRINT]
gcode:
    # Your custom end actions
```

## Available Macros

| Macro | Description |
|-------|-------------|
| `IDEX_TOOL_CHANGE T=n` | Main toolchange (with optional NEXT_X/NEXT_Y) |
| `T0` / `T1` | Shorthand overrides |
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
│   ├── hydra_print.cfg            # START/END_PRINT, PAUSE/RESUME
│   └── hydra_leds.cfg             # Zone-aware LED effects
├── klipperscreen_panels/
│   ├── hydra_dashboard.py         # IDEX dashboard hub
│   ├── hydra_align.py             # XY fine-tune visualization
│   └── hydra_visual_cal.py        # Phase 1 eyeball D-pad
├── scripts/
│   └── install.sh
├── examples/
│   ├── moonraker.conf.example
│   ├── printer.cfg.example
│   └── KlipperScreen.conf.example
└── docs/
```
