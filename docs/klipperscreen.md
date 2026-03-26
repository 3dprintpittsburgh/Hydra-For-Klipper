# KlipperScreen Integration

Hydra includes three custom KlipperScreen panels for IDEX management and calibration.

## Installation

The install script automatically symlinks panels to `~/KlipperScreen/panels/` if KlipperScreen is detected. To install manually:

```bash
ln -sf ~/Hydra-For-Klipper/klipperscreen_panels/hydra_dashboard.py ~/KlipperScreen/panels/
ln -sf ~/Hydra-For-Klipper/klipperscreen_panels/hydra_align.py ~/KlipperScreen/panels/
ln -sf ~/Hydra-For-Klipper/klipperscreen_panels/hydra_visual_cal.py ~/KlipperScreen/panels/
```

## Menu Configuration

Add these to your `KlipperScreen.conf` **above** the `#~# --- Do not edit below this line` marker:

```ini
# Hydra Z calibrate in Z Calibrate dropdown
[printer Printer]
zcalibrate_custom_commands: CALIBRATE_IDEX_Z_OFFSET

# Hydra Dashboard - top-level menu item
[menu __main hydra]
name: Hydra IDEX
icon: extruder
panel: hydra_dashboard

# Sub-items under More menu
[menu __main more hydra_align]
name: XY Alignment
icon: move
panel: hydra_align

[menu __main more hydra_z_save]
name: Save Z Offset
icon: complete
method: printer.gcode.script
params: {"script":"SAVE_IDEX_Z_OFFSET"}
```

**Note:** The `[printer Printer]` section name must match how KlipperScreen identifies your printer. Default is "Printer".

## Panels

### Hydra Dashboard (`hydra_dashboard`)

The main hub for IDEX operations. Shows:
- Active tool indicator and current T1 offsets
- **T0 / T1** selection buttons (for manual tool switching)
- Navigation to: Z Calibrate, XY Eyeball, XY Fine-Tune, Temperature
- Quick actions: Print XY Test, Home All, Show Offsets, Hydra Status

### XY Alignment (`hydra_align`)

Fine-tune XY offsets after a calibration print test. Features:
- **Cairo visualization** of concentric squares (T0 blue, T1 red)
- Preview shows the **adjustment delta** - starts aligned, shifts as you adjust
- X/Y adjustment with step sizes (0.05 / 0.1 / 0.5mm)
- Reset returns to loaded values (doesn't wipe to zero)
- **Temperature dialog** when pressing Test - set T0, T1, and bed temps with +/- buttons
- Save persists offsets; loads current values each time the panel opens

### Visual Calibration (`hydra_visual_cal`)

Phase 1 eyeball alignment with live nozzle movement. Features:
- **Three-phase workflow**: Start (move T0) → Switch (move T1) → Save
- **D-pad with step sizes** (0.05 / 0.1 / 0.5 / 1.0mm) for live nudging
- Buttons enable/disable based on current phase
- Reset moves T1 back to the reference point
- Offset display updates in real-time

## Technical Notes

### Variable Access

KlipperScreen doesn't subscribe to `gcode_macro` variables by default. The panels use a workaround:

```python
# Subscribe to Hydra config for live updates
self._screen._ws.klippy.object_subscription({
    "objects": {"gcode_macro _HYDRA_CONFIG": None}
})

# Try runtime stat first, fall back to config defaults
stat = self._printer.get_stat("gcode_macro _HYDRA_CONFIG")
if stat:
    self.x_offset = float(stat.get("offset_x_t1", 0.0))
else:
    cfg = self._printer.get_config_section("gcode_macro _HYDRA_CONFIG")
    self.x_offset = float(cfg.get("variable_offset_x_t1", "0"))
```

### Screen Size

Panels are designed for 1024x600 (BTT Pad 7). Key layout rules:
- Use `Gtk.Grid` with tight spacing, not stacking `Gtk.Box`
- Keep control columns to 185px max width
- Avoid vertical overflow - it causes KlipperScreen rendering bugs with no recovery

### Z Calibrate Dropdown

The `zcalibrate_custom_commands` config adds Hydra's Z calibration to the existing Z Calibrate panel's dropdown selector. This reuses KlipperScreen's built-in TESTZ button interface.

**Important:** Klipper's gcode parser splits command names on digits. Never use digits in macro names (e.g., use `CALIBRATE_IDEX_Z_OFFSET` not `CALIBRATE_T1_Z_OFFSET`).
