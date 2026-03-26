# Calibration Guide

Hydra includes a complete calibration system for aligning T1 to T0 in X, Y, and Z.

## Z-Offset Calibration

Calibrates how far T1's nozzle tip is from T0's, using Klipper's MANUAL_PROBE with the same KlipperScreen/Fluidd TESTZ interface as PROBE_CALIBRATE.

### Prerequisites
- T0 must be calibrated first using standard `PROBE_CALIBRATE` → `SAVE_CONFIG`
- Printer must be homed

### Procedure

1. Run `CALIBRATE_IDEX_Z_OFFSET` from:
   - KlipperScreen Z Calibrate dropdown
   - Hydra Dashboard → Z Calibrate
   - Fluidd/Mainsail console
2. The macro homes (if needed), parks T0, switches to T1 with no offset applied
3. Use the TESTZ buttons (same UI as PROBE_CALIBRATE) to paper-test T1's nozzle
4. Hit **ACCEPT** - the offset auto-saves (no manual save step needed)

### How It Works
- T1 is positioned at bed center with zero offset
- When T1's nozzle touches the bed (paper test), the Z value is the offset
- Positive offset = T1 nozzle is longer than T0 (needs to print higher)
- Negative offset = T1 nozzle is shorter (needs to print lower)
- A `delayed_gcode` watcher detects when you hit ACCEPT and saves automatically

## XY Alignment - Phase 1: Visual Eyeball

Rough alignment (~0.5mm accuracy) by visually aligning T1 over a reference point on the bed.

### Prerequisites
- A visible reference point on the bed (marker, screw head, tape mark)
- Configure the reference point coordinates in `hydra_variables.cfg`:
  ```ini
  variable_cal_ref_x: 200.0
  variable_cal_ref_y: 200.0
  variable_cal_ref_z: 5.0
  ```

### Procedure

1. Run `CALIBRATE_IDEX_XY_VISUAL` or open KlipperScreen → Hydra Dashboard → XY Eyeball
2. T0 moves to the reference point - verify it's over your marker
3. Press **Switch to T1** - T0 parks, T1 moves to the same gcode coordinates (no offset)
4. Use the **D-pad nudge buttons** to physically move T1 until it's aligned with the marker
5. Step sizes: 0.05 / 0.1 / 0.5 / 1.0mm
6. Press **Save & Done** - the total nudge distance becomes the XY offset

## XY Alignment - Phase 2: Print Test

Precision alignment using concentric squares printed by alternating T0 and T1.

### Procedure

1. Run `CALIBRATE_IDEX_XY_ALIGNMENT` from:
   - Hydra Dashboard → Print XY Test
   - XY Alignment panel → Test button (with temperature dialog)
   - Console: `CALIBRATE_IDEX_XY_ALIGNMENT BED_TEMP=60 NOZZLE_TEMP=200 NOZZLE_TEMP_T1=200`
2. The macro heats both nozzles, homes, and prints 9 concentric squares alternating T0/T1
3. After printing, measure misalignment with calipers
4. Open the XY Alignment panel in KlipperScreen:
   - The visualization shows T0 squares (blue) and T1 squares (red)
   - Adjust X and Y until the preview matches what you see on the bed
   - The preview shows the **adjustment delta** (starts aligned, shifts as you adjust)
5. Press **Save** to persist the offsets

### Print Test Details
- 9 squares from 10mm to 60mm sides, centered at bed position (200, 200)
- Odd squares = T1 (red), even squares = T0 (blue)
- 5mm spacing between squares
- After printing, bed moves forward for easy access
- Configurable temperatures via KlipperScreen dialog or macro parameters

## Offset Persistence

All calibrated offsets are saved persistently using Klipper's `SAVE_VARIABLE`:
- `hydra_offset_x_t1`
- `hydra_offset_y_t1`
- `hydra_offset_z_t1`

On startup, `_HYDRA_LOAD_OFFSETS` (delayed_gcode, 2s after boot) loads saved values into `_HYDRA_CONFIG` runtime variables.

Run `SHOW_IDEX_OFFSETS` to see current active and saved offsets.
Run `HYDRA_RESET` to clear all offsets back to zero.
