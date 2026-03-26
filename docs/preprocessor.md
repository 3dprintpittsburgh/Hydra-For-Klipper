# Gcode Preprocessor

Hydra's core innovation is a Moonraker component that adds lookahead positioning data to toolchange commands before printing starts.

## How It Works

1. You upload a gcode file via Fluidd, Mainsail, or the Moonraker API
2. Moonraker triggers Hydra's `filelist_changed` event handler
3. Hydra scans the file for `T0`/`T1` commands
4. For each toolchange, it looks ahead (up to 200 lines) for the first `G0`/`G1` move with both X and Y coordinates
5. Rewrites the `Tn` line as `IDEX_TOOL_CHANGE T=n NEXT_X=x NEXT_Y=y ; Tn`
6. Adds a fingerprint comment at the top to prevent double-processing
7. The file is ready to print with intelligent lookahead toolchanges

### Before and After

**Raw slicer output:**
```gcode
T1
; Filament gcode
G1 E-2
G1 X201.101 Y188.646 F15000
G1 E2 F2100
```

**After Hydra preprocessing:**
```gcode
IDEX_TOOL_CHANGE T=1 NEXT_X=201.101 NEXT_Y=188.646 ; T1
; Filament gcode
G1 E-2
G1 X201.101 Y188.646 F15000
G1 E2 F2100
```

The original `G1 X201.101 Y188.646` line is preserved. After Hydra moves the nozzle there via `NEXT_X/NEXT_Y`, the slicer's move becomes a zero-distance move (harmless).

## Fallback Mode

Non-preprocessed files (printed via USB SD card, or uploaded without the Moonraker component running) still work. When `NEXT_X`/`NEXT_Y` aren't provided, the T0/T1 macros fall back to the tool's last saved position.

## Fingerprint

The preprocessor adds a comment on the first line:
```
; HYDRA_PREPROCESSED v1.0.0 hash=abc123... toolchanges=15 tools=T0,T1
```

This prevents re-processing if the file is uploaded again or the event fires multiple times.

## Moonraker Configuration

Add to `moonraker.conf`:
```ini
[hydra_idex]
enabled: True
auto_preprocess: True
backup_original: False    # Set True to keep .orig backups
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/server/hydra/status` | GET | Version, enabled state, files processed, last file |
| `/server/hydra/file_info?filename=X` | GET | Preprocessing metadata for a file |
| `/server/hydra/reprocess?filename=X` | POST | Force reprocess (strips fingerprint first) |

## Metadata

After preprocessing, Hydra stores metadata:
- `total_toolchanges` - number of T commands found
- `lookahead_count` - how many had a NEXT_X/NEXT_Y (some may not if no XY move follows)
- `tools_used` - which tools appear in the file (e.g., [0, 1])
- `tool_temps` - any M104/M109 temperature commands found per tool

## Technical Details

- **Regex patterns**: `T0`/`T1` on their own line, `G0`/`G1` with both X and Y parameters
- **Lookahead limit**: 200 lines (configurable in source) - if no XY move found within 200 lines of a toolchange, NEXT_X/NEXT_Y are omitted
- **Atomic writes**: Uses temp file + `os.replace()` to prevent corruption
- **Slicer compatibility**: Works with any slicer that outputs standard `Tn` commands (PrusaSlicer, OrcaSlicer, Cura, etc.)
