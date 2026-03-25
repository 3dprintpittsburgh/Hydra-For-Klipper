# Hydra for Klipper - Development Notes

**Created**: 2026-03-19
**Last Updated**: 2026-03-25
**Primary Developer**: Eve (AI) + Jareth (Thought Space Designs / 3D Print Pittsburgh)
**Origin**: Ported from custom IDEX macros built for an Ender IDEX XL 1 printer
**Repository**: https://github.com/3dprintpittsburgh/Hydra-For-Klipper

---

## Project Origin

Hydra was born from a multi-day session (2026-03-17 through 2026-03-25) building custom IDEX toolchange macros for a heavily modified Ender-based IDEX printer. After solving numerous real-world IDEX challenges (sensorless homing, dual-carriage calibration, toolchange sequencing, EBB42 toolhead boards), we generalized the solution into a distributable open-source Klipper plugin.

The core innovation is a **Moonraker gcode preprocessor** (inspired by Happy Hare's architecture) that scans uploaded gcode files and rewrites T0/T1 commands with lookahead positioning data, allowing the incoming nozzle to move directly to its next print position instead of the outgoing nozzle's last position.

---

## Current State (v1.0.0) - Feature Complete

### Moonraker Component (`hydra_idex.py`)
- Hooks into file_manager's filelist_changed event
- Single-pass gcode scanner: finds T0/T1 commands, looks ahead for next G0/G1 XY
- Rewrites `Tn` → `IDEX_TOOL_CHANGE T=n NEXT_X=x NEXT_Y=y`
- Fingerprint system prevents double-processing
- Atomic file writes (temp file + rename)
- API endpoints: /server/hydra/status, /server/hydra/file_info, /server/hydra/reprocess
- Extracts metadata: total toolchanges, tools used, per-tool temps

### Core Macros (`hydra.cfg`)
- `IDEX_TOOL_CHANGE`: Main entry point, handles both preprocessed and raw gcode
- `_HYDRA_PARK`: Save position (gcode_position), retract, fan save/off, standby temp, Z hop, move to park
- `_HYDRA_RESTORE`: Switch carriage, apply offsets, restore temp with wait, collision-safe positioning, Z drop, prime, fan restore
- `T0`/`T1` overrides for non-preprocessed gcode
- `HYDRA_INIT`: State reset for print start
- `HYDRA_STATUS`: Full configuration and state dump
- `HYDRA_RESET`: Clear all saved offsets and runtime state
- Cold toolchange support (no retract/prime/temp when nozzles are cold)
- Per-tool state tracking: position, retraction, temperature, fan speed
- LED effects: configurable toolchange effect + printing macro

### Fan Routing (`hydra_fan.cfg`)
- M106/M107 overrides route to active tool's fan pin
- Explicit P parameter support (`M106 P0 S255`, `M106 P1 S255`)
- Fan pin names read from `_HYDRA_CONFIG` variables (not hardcoded)
- M107 without P turns off both fans

### Print Lifecycle (`hydra_print.cfg`)
- `START_PRINT`: Accepts BED_TEMP, EXTRUDER_TEMP, EXTRUDER_TEMP_T1, INITIAL_TOOL, TOTAL_TOOLCHANGES
- Smart T1 preheat: only preheats T1 when TOTAL_TOOLCHANGES > 0
- Calls `HYDRA_INIT` automatically after homing/meshing
- `END_PRINT`: Turns off heaters/fans, presents bed, resets state
- `PAUSE`: Parks active tool via `_HYDRA_PARK`
- `RESUME`: Restores active tool via `_HYDRA_RESTORE`
- `CANCEL_PRINT`: Calls END_PRINT then CANCEL_PRINT_BASE
- User override hooks: `_HYDRA_USER_START_PRINT`, `_HYDRA_USER_END_PRINT`

### Calibration System (`hydra_calibration.cfg`)
- `CALIBRATE_IDEX_Z_OFFSET`: MANUAL_PROBE-based Z offset with auto-save watcher
- `CALIBRATE_IDEX_XY_VISUAL`: Phase 1 eyeball alignment with live nudge D-pad
- `IDEX_VISUAL_SWITCH` / `IDEX_VISUAL_NUDGE` / `SAVE_IDEX_XY_VISUAL`: Visual cal helpers
- `CALIBRATE_IDEX_XY_ALIGNMENT`: Phase 2 concentric square print test (9 squares, 10-60mm, configurable temps)
- `SHOW_IDEX_OFFSETS`: Display current and saved offsets
- `SAVE_IDEX_Y_OFFSET`: Used by KlipperScreen alignment panel
- `_HYDRA_LOAD_OFFSETS`: Auto-load saved offsets on startup (2s delayed_gcode)
- `_HYDRA_Z_CAL_WATCHER`: Polls for MANUAL_PROBE completion, auto-saves
- Offset persistence via `SAVE_VARIABLE` with `hydra_` prefix

### Configuration (`hydra_variables.cfg`)
All tunables in one file - zero hardcoded values in macro logic:
- Park positions (per-tool X, shared Y)
- Safe distance (collision avoidance)
- Z hop height and speed
- Travel speed
- Retract/prime distance and speed
- Standby temperature factor
- Min toolchange temperature
- Temperature restore delta
- Fan pin names (T0/T1 output_pin names)
- LED effect names (or empty to disable)
- Calibration reference point (X/Y/Z)
- T1 gcode offsets (X/Y/Z, updated by calibration macros)
- Runtime state (managed by macros)

### KlipperScreen Panels (`klipperscreen_panels/`)
- `hydra_dashboard.py`: Hub with tool selection, offset status, navigation to calibration/temperature
- `hydra_align.py`: XY fine-tune with Cairo visualization, delta-based preview, temperature dialog for print test
- `hydra_visual_cal.py`: Phase 1 eyeball alignment with D-pad live nudge, step sizes, reset
- All panels use `object_subscription` workaround for `_HYDRA_CONFIG` variable access
- Config section fallback when runtime stats unavailable
- Compact Gtk.Grid layouts tested on 1024x600 (BTT Pad 7)

### Infrastructure
- `install.sh`: Symlinks moonraker component + KlipperScreen panels, copies macros, detects conflicts, supports `--uninstall`
- Examples for moonraker.conf, printer.cfg, and KlipperScreen.conf
- GPLv3 license
- Comprehensive README with full configuration reference
- SVG logo

---

## What Still Needs To Be Done

### High Priority

#### 1. Nozzle Wipe/Purge System (Optional Module)
**Status**: Discussed, not implemented
**Concept**: Stationary wiper wall that each nozzle can prime against + drag across to knock off filament blob
**Bambu A1 inspiration**: Purge → fan blast to solidify → drag across wall → waste falls in tray
**Design for Hydra**:
- `hydra_wipe.cfg` optional include
- `_HYDRA_WIPE_NOZZLE`: Move to wiper position, extrude purge line, fan blast, wiggle across wall
- Configurable wiper positions per tool (or shared wiper)
- Called from `_HYDRA_RESTORE` after positioning, before priming
- User prints and mounts the mechanical wiper, enters coordinates in config

#### 2. Real-World Testing
- Preprocessor has not been tested end-to-end on a real print yet
- Need to verify lookahead positioning works correctly with actual slicer output
- Need to test edge cases: first/last toolchange, sequential printing mode, cancelled prints

### Medium Priority

#### 3. Klipper TTS Notification Plugin
**Status**: Discussed, not started
**Concept**: Moonraker component that uses ElevenLabs API for voice notifications on printer events
**Prerequisite**: Host with a speaker (BTT Pad 7 confirmed working)

#### 4. Copy/Mirror Mode Support
**Status**: Not implemented
**Concept**: IDEX copy mode (both carriages print same thing) and mirror mode (mirrored)
**Klipper support**: `SET_DUAL_CARRIAGE MODE=COPY` and `MODE=MIRROR` exist
**Hydra needs**: Mode detection, skip toolchange logic in copy/mirror mode, preprocessor should detect and skip

#### 5. Automatic XY Calibration (Camera-Based)
**Status**: Concept only
**Concept**: Use a camera to visually detect alignment of calibration pattern, automatically calculate offsets

#### 6. Multi-Tool Support (>2 extruders)
**Status**: Not planned yet
**Concept**: Extend beyond T0/T1 for future multi-carriage or tool-changer setups

---

## Key Technical Lessons Learned

### Klipper Gcode Parser
- **Digits split command names**: `CALIBRATE_T1_Z_OFFSET` → parsed as `CALIBRATE_T1` + param `Z_OFFSET`
- Klipper regex: `([A-Z_]+|[A-Z*/])` treats digits as token delimiters
- **Rule**: Never use digits in the middle of macro names (use `IDEX` not `T1`)

### Position Tracking
- **`printer.toolhead.position`** gives raw stepper coordinates (includes bed mesh compensation)
- **`printer.gcode_move.gcode_position`** gives coordinates matching G1 expectations
- **Always use gcode_position** for save/restore to avoid Z mismatch (we learned this the hard way - Z was off by ~10mm due to bed mesh compensation being included in the saved position)

### Dual Carriage Behavior
- After `SET_DUAL_CARRIAGE CARRIAGE=1`, toolhead position jumps to carriage 1's physical position
- Klipper enforces **safe_dist** between carriages - must park one before moving the other to center
- `SET_DUAL_CARRIAGE` updates kinematic limits but `toolhead.axis_maximum` status doesn't reflect the change
- After G28, carriage 0 is PRIMARY, carriage 1 is INACTIVE at its home position
- Gcode offsets applied to T1 can push positions past axis limits - must clamp X and Y after applying offsets

### SAVE/RESTORE_GCODE_STATE
- `RESTORE_GCODE_STATE MOVE=0` (default) restores mode/state but NOT physical position
- E position counter is restored, which can cause confusion with retract/prime tracking
- Be explicit about M83 before any extrusion move after state changes

### Toolchange Sequencing
- Park outgoing tool BEFORE heating incoming tool (prevents ooze at print position)
- Don't restore to the outgoing tool's last position - let the slicer position the incoming tool
- The slicer sends travel moves after every T command - Hydra doesn't need to position XY
- Save position using `gcode_position` not `toolhead.position` (bed mesh compensation issue)

### KlipperScreen Development
- Custom panels go in `~/KlipperScreen/panels/`
- `activate()` runs every time panel is shown (not just first time)
- `gcode_macro` variables NOT in default subscription - must add via `object_subscription()` or read from config section as fallback
- BTT Pad 7: 1024x600, keep panels compact using Gtk.Grid (not stacking Gtk.Box)
- KlipperScreen.conf: custom sections MUST be ABOVE the `#~# --- Do not edit below this line` marker
- `zcalibrate_custom_commands` in `[printer Printer]` section adds to Z Calibrate dropdown
- Printer name in KlipperScreen defaults to "Printer" for config section naming

### EBB42 Gen 2 v1.0 Toolhead Boards
- Gen 2 v1.0 has COMPLETELY different pins from the v1.2 sample config in Klipper's repo
- Key pins: thermistor=PA1 (pullup 2200), heater=PB0, part fan=PB8, hotend fan=PB15, TMC UART=PB3
- BLTouch requires `pin_up_touch_mode_reports_triggered: False` and `probe_with_touch_mode: True`
- Two identical boards on USB have the same serial string - must use `by-path` identification
- Onboard temp sensor on PA0 (pullup 2200) useful for board monitoring
- ADC reading max value (32760) = open circuit = physical connection problem, NOT config issue

### Temperature Management
- PrusaSlicer sends NO M104/M109 in gcode for multi-extruder - relies entirely on start gcode and firmware
- `[total_toolchanges]` PrusaSlicer variable tells you if the print uses multiple tools
- Don't preheat T1 on single-color prints (wastes energy, confusing)
- Store T1 temp from slicer so the toolchange macro can use the correct temp on first call

### Homing with Dual Carriage
- `[safe_z_home]` + G28 macro causes repeated Z hops (once per axis homed)
- `[homing_override]` is cleaner - single Z lift at start, then home each axis
- Sensorless homing needs TMC driver mode switch (StealthChop → SpreadCycle) and current bump

---

## Port Status: Original IDEX Macros → Hydra

| Original Component | Hydra Equivalent | Status |
|---|---|---|
| T0/T1 macros | `IDEX_TOOL_CHANGE` / `T0` / `T1` | ✅ Complete |
| idex_config variables | `_HYDRA_CONFIG` | ✅ Complete |
| PARK_TOOLHEAD | `_HYDRA_PARK` | ✅ Complete |
| RESTORE_TOOLHEAD | `_HYDRA_RESTORE` | ✅ Complete |
| SAVE_ACTIVE_TOOLHEAD_POSITION | Inline in `_HYDRA_PARK` | ✅ Complete |
| RETRACT/PRIME_ACTIVE_FILAMENT | Inline in `_HYDRA_PARK` / `_HYDRA_RESTORE` | ✅ Complete |
| DISABLE_FAN / RESTORE_FAN | Inline in `_HYDRA_PARK` / `_HYDRA_RESTORE` | ✅ Complete |
| SET_MIN/STANDBY/RESTORE_TEMP | Inline in `_HYDRA_PARK` / `_HYDRA_RESTORE` | ✅ Complete |
| M106/M107 overrides | `hydra_fan.cfg` | ✅ Complete |
| START/END_PRINT | `hydra_print.cfg` | ✅ Complete |
| PAUSE/RESUME/CANCEL | `hydra_print.cfg` | ✅ Complete |
| CALIBRATE_IDEX_Z_OFFSET | `hydra_calibration.cfg` | ✅ Complete |
| CALIBRATE_IDEX_XY_VISUAL | `hydra_calibration.cfg` | ✅ Complete |
| CALIBRATE_IDEX_XY_ALIGNMENT | `hydra_calibration.cfg` | ✅ Complete |
| SHOW_IDEX_OFFSETS | `hydra_calibration.cfg` | ✅ Complete |
| SAVE_IDEX_Y_OFFSET | `hydra_calibration.cfg` | ✅ Complete |
| CLEAR_IDEX_VARS | `HYDRA_RESET` | ✅ Complete |
| _LOAD_T1_CALIBRATION | `_HYDRA_LOAD_OFFSETS` | ✅ Complete |
| _IDEX_Z_CAL_WATCHER | `_HYDRA_Z_CAL_WATCHER` | ✅ Complete |
| KlipperScreen dashboard | `hydra_dashboard.py` | ✅ Complete |
| KlipperScreen XY alignment | `hydra_align.py` | ✅ Complete |
| KlipperScreen visual cal | `hydra_visual_cal.py` | ✅ Complete |
| LED effects | User-defined, called by configurable name | ✅ Complete |
| Sensorless homing | NOT in Hydra (printer-specific) | N/A |

---

## Testing Checklist

- [ ] Install Hydra via install.sh
- [ ] Configure hydra_variables.cfg
- [ ] Remove old T0/T1/PARK/RESTORE/M106/M107/START_PRINT/END_PRINT macros
- [ ] Test manual T0/T1 switching (cold)
- [ ] Test manual T0/T1 switching (hot)
- [ ] Test single-color print (T1 should stay off)
- [ ] Test dual-color print with raw gcode (no preprocessing)
- [ ] Upload gcode to verify preprocessing (check for IDEX_TOOL_CHANGE in file)
- [ ] Test dual-color print with preprocessed gcode (lookahead positioning)
- [ ] Test Z offset calibration (CALIBRATE_IDEX_Z_OFFSET)
- [ ] Test XY visual calibration (CALIBRATE_IDEX_XY_VISUAL)
- [ ] Test XY print test (CALIBRATE_IDEX_XY_ALIGNMENT)
- [ ] Verify fan switching between tools
- [ ] Verify LED effects during toolchange
- [ ] Verify temperature standby/restore
- [ ] Test PAUSE/RESUME during dual-color print
- [ ] Test CANCEL during dual-color print
- [ ] Test KlipperScreen panels (dashboard, align, visual cal)
- [ ] HYDRA_STATUS shows correct config
- [ ] HYDRA_RESET clears everything
