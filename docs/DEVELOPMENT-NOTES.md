# Hydra for Klipper - Development Notes

**Created**: 2026-03-19
**Primary Developer**: Eve (AI) + Jareth (Thought Space Designs / 3D Print Pittsburgh)
**Origin**: Ported from custom IDEX macros built for Ender IDEX XL 1 printer

---

## Project Origin

Hydra was born from a multi-day session (2026-03-17 through 2026-03-19) building custom IDEX toolchange macros for Jareth's Ender IDEX XL 1 printer. After solving numerous real-world IDEX challenges, we decided to generalize the solution into a distributable open-source Klipper plugin.

The core innovation is a **Moonraker gcode preprocessor** (inspired by Happy Hare's architecture) that scans uploaded gcode files and rewrites T0/T1 commands with lookahead positioning data, allowing the incoming nozzle to move directly to its next print position instead of the outgoing nozzle's last position.

---

## What's Been Built (v1.0.0)

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
- `_HYDRA_PARK`: Save position (gcode_position not toolhead.position!), retract, fan off, standby temp, Z hop, move to park
- `_HYDRA_RESTORE`: Switch carriage, apply offsets, restore temp with wait, collision-safe positioning, Z drop, prime, fan restore
- `T0`/`T1` overrides for non-preprocessed gcode
- `HYDRA_INIT`: State reset for print start
- `HYDRA_STATUS`: Debug output
- Cold toolchange support (no retract/prime/temp when nozzles are cold)
- Per-tool state tracking: position, retraction, temperature, fan speed

### Calibration (`hydra_calibration.cfg`)
- `CALIBRATE_IDEX_Z_OFFSET`: MANUAL_PROBE-based Z offset with auto-save watcher
- `CALIBRATE_IDEX_XY_VISUAL`: Phase 1 eyeball alignment with live nudge D-pad
- `IDEX_VISUAL_SWITCH` / `IDEX_VISUAL_NUDGE` / `SAVE_IDEX_XY_VISUAL`: Visual cal helpers
- `CALIBRATE_IDEX_XY_ALIGNMENT`: Phase 2 concentric square print test (9 squares, 10-60mm)
- `SHOW_IDEX_OFFSETS`: Display current offsets
- `_HYDRA_LOAD_OFFSETS`: Auto-load saved offsets on startup
- Offset persistence via `SAVE_VARIABLE` with `hydra_` prefix

### Configuration (`hydra_variables.cfg`)
- All tunables in one file: park positions, speeds, retract/prime distances, temp factors
- Fan pin names configurable (not hardcoded)
- LED effect names configurable (or disable with empty string)
- Calibration reference point configurable
- Runtime state variables (managed by macros, user doesn't touch)

### Infrastructure
- `install.sh`: Symlink moonraker component, copy macros, detect conflicts
- Examples for moonraker.conf and printer.cfg
- GPLv3 license
- README with full documentation

---

## What Still Needs To Be Done

### High Priority - Before First Public Release

#### 1. M106/M107 Fan Override Macros
**Status**: NOT in Hydra yet - lives in printer.cfg on IDEX XL 1
**Problem**: IDEX printers need M106/M107 to route fan commands to the correct tool's fan pin. The default Klipper M106 doesn't know which fan to activate on a dual-extruder setup.
**Solution**: Add configurable M106/M107 override macros to Hydra that:
- Read the active carriage to determine which fan pin to use
- Support `P` parameter for explicit tool selection (`M106 P1 S255`)
- Use the fan pin names from `_HYDRA_CONFIG` variables
- Make these optional (user can skip if they have their own M106/M107 or use Klipper's native multi-fan support)

#### 2. Generic START_PRINT / END_PRINT Macros
**Status**: NOT in Hydra - lives in custom_macros.cfg on IDEX XL 1
**Current IDEX XL 1 implementation**:
- START_PRINT: accepts BED_TEMP, EXTRUDER_TEMP, EXTRUDER_TEMP_T1, INITIAL_TOOL, TOTAL_TOOLCHANGES
- Smart T1 preheat: only preheats T1 if TOTAL_TOOLCHANGES > 0
- Stores T1 temp in variable for T1 macro to use on first toolchange
- Calls HYDRA_INIT after homing/meshing
- END_PRINT: turns off heaters/fans, parks if IDEX mode was active

**Design for Hydra**:
- Provide a `hydra_print.cfg` with generic START/END macros
- Accept standard slicer parameters
- Call `HYDRA_INIT` automatically
- Allow user overrides via `_HYDRA_USER_START` / `_HYDRA_USER_END` callback macros (like Happy Hare's `_MMU_ACTION_CHANGED` pattern)
- Document recommended slicer start gcode for PrusaSlicer, OrcaSlicer, Cura

**Slicer start gcode recommendation**:
```
START_PRINT BED_TEMP=[first_layer_bed_temperature] EXTRUDER_TEMP=[first_layer_temperature_0] EXTRUDER_TEMP_T1=[first_layer_temperature_1] INITIAL_TOOL=[initial_tool] TOTAL_TOOLCHANGES=[total_toolchanges]
```

#### 3. Nozzle Wipe/Purge System (Optional Module)
**Status**: Discussed, not implemented
**Concept**: Stationary wiper wall that each nozzle can prime against + drag across to knock off filament blob
**Bambu A1 inspiration**: Purge → fan blast to solidify → drag across wall → waste falls in tray
**Design for Hydra**:
- `hydra_wipe.cfg` optional include
- `_HYDRA_WIPE_NOZZLE`: Move to wiper position, extrude purge line, fan blast, wiggle across wall
- Configurable wiper positions per tool (or shared wiper)
- Called from `_HYDRA_RESTORE` after positioning, before priming (or as part of prime)
- User prints and mounts the mechanical wiper, enters coordinates in config

#### 4. KlipperScreen Integration
**Status**: Built for IDEX XL 1, not yet ported to Hydra
**Panels built**:
- `idex_dashboard.py` - Hub with tool selection, offset status, navigation
- `idex_align.py` - XY fine-tune with visualization (Cairo drawing of concentric squares)
- `idex_visual_cal.py` - Phase 1 eyeball alignment with D-pad
**Note on portability**:
- Panels reference `gcode_macro idex_config` - need to update to `_HYDRA_CONFIG`
- Need to handle the KlipperScreen subscription issue (gcode_macro vars not in default subscription)
- Panel used `object_subscription` workaround + config section fallback
- BTT Pad 7 screen is 1024x600 - panels must be compact (Gtk.Grid, not stacking Box)

### Medium Priority - Post-Release Enhancements

#### 5. Klipper TTS Notification Plugin
**Status**: Discussed, not started
**Concept**: Moonraker component + Klipper macros that use ElevenLabs API for voice notifications on printer events (print complete, toolchange, errors)
**Prerequisite**: BTT Pad 7 (or any host) has a speaker. Confirmed working with `speaker-test` on IDEX XL 1.
**Architecture**: Similar to Keith (UR10 robot arm) voice setup - ElevenLabs API, audio caching, event-driven

#### 6. Copy/Mirror Mode Support
**Status**: Not implemented
**Concept**: IDEX copy mode (both carriages print same thing) and mirror mode (mirrored)
**Klipper support**: `SET_DUAL_CARRIAGE MODE=COPY` and `MODE=MIRROR` exist
**Hydra needs**: Mode detection, skip toolchange logic in copy/mirror mode, preprocessor should detect and skip

#### 7. Automatic XY Calibration (Camera-Based)
**Status**: Concept only
**Concept**: Use a camera to visually detect alignment of calibration pattern, automatically calculate offsets
**Prerequisite**: Camera mounted on printer, computer vision processing

---

## Key Technical Lessons Learned (from IDEX XL 1 build)

### Klipper Gcode Parser
- **Digits split command names**: `CALIBRATE_T1_Z_OFFSET` → parsed as `CALIBRATE_T1` + param `Z_OFFSET`
- Regex: `([A-Z_]+|[A-Z*/])` - digits break tokens
- **Rule**: Never use digits in middle of macro names (use `IDEX` not `T1`)

### Position Tracking
- **`printer.toolhead.position`** gives raw stepper coordinates (includes bed mesh compensation)
- **`printer.gcode_move.gcode_position`** gives coordinates matching G1 expectations
- **Always use gcode_position** for save/restore to avoid Z mismatch

### Dual Carriage Behavior
- After `SET_DUAL_CARRIAGE CARRIAGE=1`, toolhead position jumps to carriage 1's physical position
- Klipper enforces **safe_dist** between carriages - must park one before moving the other to center
- `SET_DUAL_CARRIAGE` updates kinematic limits but `toolhead.axis_maximum` status doesn't reflect it
- After G28, carriage 0 is PRIMARY, carriage 1 is INACTIVE at its home position

### SAVE/RESTORE_GCODE_STATE
- `RESTORE_GCODE_STATE MOVE=0` (default) restores mode/state but NOT physical position
- E position counter is restored, which can cause confusion with retract/prime tracking
- Be explicit about M83 before any extrusion move after state changes

### KlipperScreen
- Custom panels go in `~/KlipperScreen/panels/`
- `activate()` runs every time panel is shown (not just first time)
- `gcode_macro` variables NOT in default subscription - must add via `object_subscription()` or read from config section as fallback
- BTT Pad 7: 1024x600, keep panels compact, Gtk.Grid not stacking Box
- KlipperScreen.conf: custom sections MUST be ABOVE the `#~# --- Do not edit below this line` marker
- `zcalibrate_custom_commands` adds to Z Calibrate dropdown
- Printer name in KlipperScreen is "Printer" by default for `[printer Printer]` section

### BTT Octopus v1.1
- Motor slot numbering doesn't match intuitive expectations - verify by pin mapping
- DIAG jumpers required for sensorless homing (unlike Manta M8P v2 which is hardwired)
- DIAG pin routes to corresponding STOP header when jumpered

### Temperature Management
- Slicer (PrusaSlicer) sends NO M104/M109 in gcode for multi-extruder - relies on start gcode and firmware
- `[total_toolchanges]` PrusaSlicer variable tells you if the print uses multiple tools
- Store T1 temp in START_PRINT variable so T1 macro can use it on first call
- Don't preheat T1 on single-color prints (wastes energy)

---

## File Mapping: IDEX XL 1 → Hydra

| IDEX XL 1 File | Hydra Equivalent | Status |
|---|---|---|
| `IDEX/custom_idex_macros.cfg` (T0/T1/PARK/RESTORE) | `hydra.cfg` | ✅ Ported |
| `IDEX/custom_idex_macros.cfg` (idex_config vars) | `hydra_variables.cfg` | ✅ Ported |
| `IDEX/custom_idex_macros.cfg` (DISABLE/RESTORE_FAN) | `hydra.cfg` (_HYDRA_PARK/_HYDRA_RESTORE) | ✅ Integrated |
| `IDEX/custom_idex_macros.cfg` (CALIBRATE_IDEX_XY_ALIGNMENT) | `hydra_calibration.cfg` | ✅ Ported |
| `IDEX/idex_t1_calibration.cfg` (Z cal, XY visual, offsets) | `hydra_calibration.cfg` | ✅ Ported |
| `IDEX/idex_led_effects.cfg` | User's own config (Hydra calls by name) | ✅ Configurable |
| `IDEX/idex_sensorless_homing.cfg` | NOT in Hydra (printer-specific) | N/A |
| `printer.cfg` (M106/M107 overrides) | TODO: `hydra_fan.cfg` | ❌ Not yet |
| `custom_macros.cfg` (START/END_PRINT) | TODO: `hydra_print.cfg` | ❌ Not yet |
| KlipperScreen panels (3 custom .py files) | TODO: port to Hydra | ❌ Not yet |

---

## Testing Checklist (for IDEX XL 1 installation)

- [ ] Install Hydra via install.sh on IDEX XL 1
- [ ] Configure hydra_variables.cfg with XL 1 values
- [ ] Remove old T0/T1/PARK/RESTORE from custom_idex_macros.cfg
- [ ] Keep sensorless homing, M106/M107, LED effects configs
- [ ] Update START_PRINT to call HYDRA_INIT
- [ ] Test manual T0/T1 switching (cold)
- [ ] Test manual T0/T1 switching (hot)
- [ ] Test single-color print (T1 should stay off)
- [ ] Test dual-color print with raw gcode (no preprocessing)
- [ ] Upload gcode to test preprocessing (verify IDEX_TOOL_CHANGE in file)
- [ ] Test dual-color print with preprocessed gcode (lookahead positioning)
- [ ] Test Z offset calibration
- [ ] Test XY visual calibration
- [ ] Test XY print test calibration
- [ ] Verify fan switching works correctly
- [ ] Verify LED effects fire correctly
- [ ] Verify temperature standby/restore works
- [ ] Test PAUSE/RESUME during dual-color print
- [ ] Test CANCEL during dual-color print

---

## Repository
- Local: `./`
- Future GitHub: `https://github.com/3dprintpittsburgh/Hydra-For-Klipper`
- Related printer notes: `N/A (printer-specific)`
