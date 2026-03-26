# Troubleshooting

## Klipper Errors

### "Unknown command IDEX_TOOL_CHANGE"
- Ensure `[include hydra.cfg]` is in your `printer.cfg`
- Firmware restart after adding the include

### "Unknown command SET_LED_EFFECT"
- You have LED effects configured but don't have the [klipper-led_effect](https://github.com/julianschill/klipper-led_effect) plugin installed
- Either install the plugin or set `variable_led_strip_name: ""` in `hydra_variables.cfg`

### "Move out of range" during toolchange
- The target position exceeds axis limits after applying gcode offsets
- Hydra has built-in X and Y clamping, but check your `safe_distance` value
- Check T1 offsets aren't pushing positions past bed limits
- Run `HYDRA_STATUS` to see current saved positions

### "Cold extrusion" errors during toolchange
- `min_toolchange_temp` is set higher than the nozzle's current target
- Lower `min_toolchange_temp` in `hydra_variables.cfg`
- Or ensure the slicer sets nozzle temperatures before calling T commands

### Macro name conflicts
- Hydra defines T0, T1, M106, M107, START_PRINT, END_PRINT, PAUSE, RESUME, CANCEL_PRINT
- Remove any existing definitions of these from your config
- If you want to keep your own START_PRINT, don't include `hydra_print.cfg`

## Toolchange Issues

### T1 goes to wrong position
- Run `HYDRA_STATUS` to check saved positions and active tool
- If using lookahead, verify the file was preprocessed: check for `; HYDRA_PREPROCESSED` on the first line
- Check Moonraker logs for "Hydra" messages
- Look for "Clamped X" or "Clamped Y" messages indicating collision avoidance adjusted the position

### New nozzle drags over print
- This happens when the toolchange restores to the outgoing tool's position
- Ensure the preprocessor is running (check `[hydra_idex]` in moonraker.conf)
- With preprocessed files, the nozzle goes directly to the NEXT position

### Filament ooze during toolchange
- Increase `retract_distance` (default 20mm)
- Consider adding a nozzle wipe mechanism (see development notes)
- The `standby_temp_factor` (default 0.9) drops temp during park - lower it for less ooze

### T1 stays at park position on manual switch
- This is normal for cold manual switches - T1 moves to bed center
- If it doesn't move at all, check if homing is complete (`G28` first)

## Temperature Issues

### T1 doesn't preheat during START_PRINT
- Verify your slicer start gcode includes `TOTAL_TOOLCHANGES=[total_toolchanges]`
- T1 only preheats when `TOTAL_TOOLCHANGES > 0`
- Check `EXTRUDER_TEMP_T1` is being passed

### Nozzle heats unnecessarily on single-color print
- Verify `TOTAL_TOOLCHANGES=[total_toolchanges]` is in your start gcode
- For single-color prints, PrusaSlicer sets this to 0

### Temperature wait takes too long
- Increase `temp_restore_delta` (default 10°C) - higher value means less waiting
- Increase `standby_temp_factor` (default 0.9) - keeps standby temp closer to active

## Fan Issues

### Fan not switching between tools
- Verify `fan_pin_t0` and `fan_pin_t1` match your `[output_pin]` section names exactly
- Remove any existing M106/M107 overrides from your config
- Test manually: `SET_PIN PIN=extruder_fan VALUE=1` then `SET_PIN PIN=extruder1_fan VALUE=1`

### Both fans always on
- Check that `M107` isn't being called without a P parameter (turns off both)
- Verify the slicer isn't sending M106 to both tools

## Preprocessor Issues

### Files not being preprocessed
- Check `[hydra_idex]` section in moonraker.conf with `enabled: True`
- Check Moonraker logs: `grep Hydra ~/printer_data/logs/moonraker.log`
- Restart Moonraker after adding the config section
- Verify the file has `.gcode` extension

### File preprocessed but toolchange still wrong
- Check `/server/hydra/file_info?filename=yourfile.gcode` via API
- Verify `IDEX_TOOL_CHANGE` commands appear in the file
- Some toolchanges may not have NEXT_X/NEXT_Y if no XY move follows within 200 lines

## KlipperScreen Issues

### Panels don't appear
- Check symlinks exist in `~/KlipperScreen/panels/`
- Verify menu entries in `KlipperScreen.conf` are ABOVE the auto-generated line
- Restart KlipperScreen: `sudo systemctl restart KlipperScreen`

### Offset values show as 0 in panels
- The panels use `object_subscription` to read `_HYDRA_CONFIG` variables
- If values show 0 on first open, close and reopen the panel
- Check that `_HYDRA_LOAD_OFFSETS` ran on startup (look for "Hydra: Loaded" messages)

### Panel causes vertical overflow
- Keep panels compact - designed for 1024x600 (BTT Pad 7)
- If you have a different resolution, the Gtk.Grid layout should adapt
- Report issues if the layout breaks on your screen size

## Debug Commands

| Command | What it shows |
|---------|---------------|
| `HYDRA_STATUS` | Full state: active tool, positions, temps, fans, config |
| `SHOW_IDEX_OFFSETS` | Current and saved T1 XYZ offsets |
| `HYDRA_RESET` | Clears all offsets and state to defaults |
