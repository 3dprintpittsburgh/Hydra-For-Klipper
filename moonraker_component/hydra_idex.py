"""
Hydra for Klipper - Moonraker IDEX Gcode Preprocessor

Automatically preprocesses uploaded gcode files to extract lookahead
positioning data for IDEX toolchanges. Rewrites T0/T1 commands as
IDEX_TOOL_CHANGE with NEXT_X/NEXT_Y parameters.

This module serves dual purpose:
  1. Moonraker component (loaded via [hydra_idex] config section)
  2. Standalone script (invoked by Moonraker's metadata pipeline)

The component replaces Moonraker's METADATA_SCRIPT with this file,
ensuring preprocessing runs synchronously BEFORE print start - the
same pattern used by Happy Hare for MMU preprocessing.

Copyright (C) 2026 Thought Space Designs
Licensed under GPLv3
"""
from __future__ import annotations

import logging
import os
import re
import sys
import json
import hashlib
import shutil
import tempfile
from typing import Optional, Dict, Any, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from moonraker.confighelper import ConfigHelper
    from moonraker.common import WebRequest

HYDRA_VERSION = "1.0.0"
FINGERPRINT_PREFIX = "; HYDRA_PREPROCESSED"

# Regex patterns for gcode parsing
T_PATTERN = re.compile(r'^T([01])\s*(?:;.*)?$')
G1_XY_PATTERN = re.compile(
    r'^G[01]\s+'
    r'(?=.*X(-?[\d.]+))'
    r'(?=.*Y(-?[\d.]+))',
    re.IGNORECASE
)
TEMP_PATTERN = re.compile(
    r'^M(?:104|109)\s+.*?S(\d+\.?\d*).*?T([01])',
    re.IGNORECASE
)
START_PRINT_PATTERN = re.compile(
    r'^START_PRINT\b', re.IGNORECASE
)

logger = logging.getLogger(__name__)


# =========================================================================
# Standalone preprocessing functions (used by both component and script)
# =========================================================================

def _read_standby_factor(filepath: str) -> float:
    """Read standby_temp_factor from hydra_variables.cfg on disk."""
    # Derive config dir from gcode path: .../printer_data/gcodes/file.gcode
    # -> .../printer_data/config/hydra_variables.cfg
    gcodes_dir = os.path.dirname(os.path.realpath(filepath))
    config_dir = os.path.join(os.path.dirname(gcodes_dir), 'config')
    var_file = os.path.join(config_dir, 'hydra_variables.cfg')
    try:
        if os.path.isfile(var_file):
            with open(var_file, 'r') as f:
                for line in f:
                    match = re.match(
                        r'^variable_standby_temp_factor\s*:\s*([\d.]+)', line
                    )
                    if match:
                        return float(match.group(1))
    except Exception:
        pass
    return 0.9  # default


def preprocess_file(filepath: str, backup: bool = False) -> Optional[Dict[str, Any]]:
    """
    Core preprocessing algorithm.
    Scans gcode for T0/T1 commands, finds next G0/G1 XY after each,
    rewrites as IDEX_TOOL_CHANGE with NEXT_X/NEXT_Y parameters.
    Returns metadata dict or None if skipped.
    """
    filepath = os.path.realpath(filepath)
    standby_factor = _read_standby_factor(filepath)

    with open(filepath, 'r') as f:
        lines = f.readlines()

    if not lines:
        return None

    # Check fingerprint - skip if already processed
    for line in lines[:5]:
        if line.startswith(FINGERPRINT_PREFIX):
            return None

    # First pass: find all toolchange positions
    toolchanges = _find_toolchanges(lines)

    if not toolchanges:
        return None

    # Second pass: rewrite toolchange lines with lookahead data
    output_lines, metadata = _rewrite_toolchanges(
        lines, toolchanges, standby_factor
    )

    if not output_lines:
        return None

    # Add fingerprint
    content_hash = hashlib.sha256(''.join(lines[:100]).encode()).hexdigest()[:16]
    fingerprint = (
        f"{FINGERPRINT_PREFIX} v{HYDRA_VERSION} "
        f"hash={content_hash} "
        f"toolchanges={metadata['total_toolchanges']} "
        f"tools={','.join(f'T{t}' for t in sorted(metadata['tools_used']))}\n"
    )

    # Backup original if requested
    if backup:
        backup_path = filepath + ".orig"
        if not os.path.exists(backup_path):
            shutil.copy2(filepath, backup_path)

    # Atomic write
    dir_name = os.path.dirname(filepath)
    with tempfile.NamedTemporaryFile(
        mode='w', dir=dir_name, suffix='.gcode.tmp', delete=False
    ) as tmp:
        tmp.write(fingerprint)
        tmp.writelines(output_lines)
        tmp_path = tmp.name

    os.replace(tmp_path, filepath)

    return metadata


def _find_toolchanges(
    lines: List[str]
) -> List[Tuple[int, int, Optional[float], Optional[float]]]:
    """Find all toolchange lines and their next XY positions."""
    toolchanges = []
    for i, line in enumerate(lines):
        match = T_PATTERN.match(line.strip())
        if not match:
            continue
        tool_num = int(match.group(1))
        next_x, next_y = _find_next_xy(lines, i + 1)
        toolchanges.append((i, tool_num, next_x, next_y))
    return toolchanges


def _find_next_xy(
    lines: List[str], start: int
) -> Tuple[Optional[float], Optional[float]]:
    """Scan forward for first G0/G1 with both X and Y."""
    for i in range(start, min(start + 200, len(lines))):
        line = lines[i].strip()
        if T_PATTERN.match(line):
            break
        match = G1_XY_PATTERN.match(line)
        if match:
            return float(match.group(1)), float(match.group(2))
    return None, None


def _extract_param(line: str, param: str) -> Optional[str]:
    """Extract a named parameter value from a gcode line."""
    match = re.search(rf'{param}=(\S+)', line, re.IGNORECASE)
    return match.group(1) if match else None


def _rewrite_toolchanges(
    lines: List[str],
    toolchanges: List[Tuple[int, int, Optional[float], Optional[float]]],
    standby_factor: float = 0.9
) -> Tuple[List[str], Dict[str, Any]]:
    """Rewrite toolchange lines with IDEX_TOOL_CHANGE commands."""
    tc_map = {tc[0]: tc for tc in toolchanges}

    output = []
    tools_used = set()
    lookahead_count = 0
    total_tc = len(toolchanges)
    start_print_injected = False

    for i, line in enumerate(lines):
        if i in tc_map:
            _, tool_num, next_x, next_y = tc_map[i]
            tools_used.add(tool_num)

            if next_x is not None and next_y is not None:
                output.append(
                    f"IDEX_TOOL_CHANGE T={tool_num} "
                    f"NEXT_X={next_x:.3f} NEXT_Y={next_y:.3f} "
                    f"; {line.strip()}\n"
                )
                lookahead_count += 1
            else:
                output.append(
                    f"IDEX_TOOL_CHANGE T={tool_num} "
                    f"; {line.strip()}\n"
                )
        elif (not start_print_injected
              and START_PRINT_PATTERN.match(line.strip())):
            # Inject TOTAL_TOOLCHANGES into START_PRINT if missing
            stripped = line.rstrip('\n')
            if 'TOTAL_TOOLCHANGES' not in stripped.upper():
                output.append(
                    f"{stripped} TOTAL_TOOLCHANGES={total_tc}\n"
                )
            else:
                output.append(line)
            # Inject T1 preheat if this is a multi-tool print
            if total_tc > 0:
                t1_temp = _extract_param(stripped, 'EXTRUDER_TEMP_T1')
                initial_tool = _extract_param(stripped, 'INITIAL_TOOL')
                if t1_temp and float(t1_temp) > 0:
                    t1_val = float(t1_temp)
                    # If T1 isn't the initial tool, preheat to standby temp
                    # (it'll reach full temp when first toolchange happens)
                    if initial_tool != '1':
                        t1_val = int(t1_val * standby_factor)
                    else:
                        t1_val = int(t1_val)
                    output.append(
                        f"M104 S{t1_val} T1"
                        f" ; Hydra: preheat T1 for {total_tc} toolchanges"
                        f" ({'standby' if initial_tool != '1' else 'active'})\n"
                    )
            start_print_injected = True
        else:
            output.append(line)

    # Extract temperature metadata
    temps = {}
    for line in lines:
        match = TEMP_PATTERN.match(line.strip())
        if match:
            temp = float(match.group(1))
            tool = int(match.group(2))
            if tool not in temps:
                temps[tool] = temp

    metadata = {
        "total_toolchanges": len(toolchanges),
        "lookahead_count": lookahead_count,
        "tools_used": list(tools_used),
        "tool_temps": temps,
        "hydra_version": HYDRA_VERSION,
    }

    return output, metadata


# =========================================================================
# Moonraker Component
# =========================================================================

class HydraIdex:
    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.file_manager = self.server.lookup_component("file_manager")

        # Configuration
        self.enabled = config.getboolean("enabled", True)
        self.auto_preprocess = config.getboolean("auto_preprocess", True)
        self.backup_original = config.getboolean("backup_original", False)

        # Replace METADATA_SCRIPT so preprocessing runs synchronously
        # in the upload pipeline BEFORE print starts (same pattern as
        # Happy Hare). This file runs as both a component and a script.
        if self.enabled and self.auto_preprocess:
            from .file_manager import file_manager as fm_module
            self._original_metadata_script = fm_module.METADATA_SCRIPT
            fm_module.METADATA_SCRIPT = os.path.abspath(__file__)
            logger.info(
                f"Hydra: Replaced METADATA_SCRIPT for synchronous preprocessing"
            )

        # Register API endpoints
        self.server.register_endpoint(
            "/server/hydra/status",
            ["GET"],
            self._handle_status
        )
        self.server.register_endpoint(
            "/server/hydra/file_info",
            ["GET"],
            self._handle_file_info
        )
        self.server.register_endpoint(
            "/server/hydra/reprocess",
            ["POST"],
            self._handle_reprocess
        )

        # Stats
        self.files_processed = 0
        self.last_file = ""

        logger.info(f"Hydra IDEX preprocessor v{HYDRA_VERSION} loaded"
                     f" (enabled={self.enabled}, auto={self.auto_preprocess})")

    async def _handle_status(self, web_request: WebRequest) -> Dict[str, Any]:
        return {
            "version": HYDRA_VERSION,
            "enabled": self.enabled,
            "auto_preprocess": self.auto_preprocess,
            "files_processed": self.files_processed,
            "last_file": self.last_file,
        }

    async def _handle_file_info(self, web_request: WebRequest) -> Dict[str, Any]:
        filename = web_request.get_str("filename", "")
        if not filename:
            raise self.server.error("Missing 'filename' parameter")

        gc_path = self.file_manager.get_directory()
        full_path = os.path.join(gc_path, filename)

        if not os.path.isfile(full_path):
            raise self.server.error(f"File not found: {filename}")

        with open(full_path, 'r') as f:
            first_line = f.readline()

        if not first_line.startswith(FINGERPRINT_PREFIX):
            return {"processed": False}

        parts = first_line.strip().split()
        info: Dict[str, Any] = {"processed": True}
        for part in parts:
            if "=" in part:
                k, v = part.split("=", 1)
                info[k] = v

        return info

    async def _handle_reprocess(self, web_request: WebRequest) -> Dict[str, Any]:
        filename = web_request.get_str("filename", "")
        if not filename:
            raise self.server.error("Missing 'filename' parameter")

        gc_path = self.file_manager.get_directory()
        full_path = os.path.join(gc_path, filename)

        if not os.path.isfile(full_path):
            raise self.server.error(f"File not found: {filename}")

        # Strip fingerprint if present
        with open(full_path, 'r') as f:
            lines = f.readlines()

        if lines and lines[0].startswith(FINGERPRINT_PREFIX):
            with open(full_path, 'w') as f:
                f.writelines(lines[1:])

        metadata = await self.server.event_loop.run_in_thread(
            preprocess_file, full_path
        )

        return {
            "success": metadata is not None,
            "metadata": metadata,
        }


def load_component(config: ConfigHelper) -> HydraIdex:
    return HydraIdex(config)


# =========================================================================
# Standalone script mode - invoked by Moonraker metadata pipeline
# =========================================================================

def main():
    """
    When invoked as a script by Moonraker's metadata pipeline,
    preprocess the gcode file first, then run the original metadata
    extraction script.
    """
    # Find the gcode file from args (-f flag)
    filepath = None
    gcodes_path = None
    args = sys.argv[1:]

    for i, arg in enumerate(args):
        if arg == '-f' and i + 1 < len(args):
            filepath = args[i + 1]
        elif arg == '-p' and i + 1 < len(args):
            gcodes_path = args[i + 1]

    if filepath and gcodes_path:
        full_path = os.path.join(gcodes_path, filepath)
        if os.path.isfile(full_path):
            try:
                result = preprocess_file(full_path)
                if result:
                    print(
                        f"Hydra: Preprocessed {filepath} - "
                        f"{result['total_toolchanges']} toolchanges, "
                        f"{result['lookahead_count']} with lookahead",
                        file=sys.stderr
                    )
            except Exception as e:
                print(f"Hydra: Preprocessing error: {e}", file=sys.stderr)

    # Now run the original metadata script.
    # Our symlink lives at moonraker/components/hydra_idex.py ->
    # so metadata.py is at moonraker/components/file_manager/metadata.py
    # (sibling directory of where the symlink points from)
    symlink_dir = os.path.dirname(os.path.abspath(
        os.path.realpath(sys.argv[0])  # resolve the symlink target
    ))
    # From the symlink location in moonraker/components/, go to file_manager/
    components_dir = os.path.dirname(symlink_dir)
    # But if we're in the hydra repo dir, walk from the symlink source instead
    metadata_script = ""
    for candidate in [
        # Relative to symlink source (moonraker/components/hydra_idex.py)
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                     'file_manager', 'metadata.py'),
        # Relative to real file (hydra repo)
        os.path.join(components_dir, '..', '..', 'moonraker',
                     'components', 'file_manager', 'metadata.py'),
        # Standard install paths
        os.path.expanduser(
            '~/moonraker/moonraker/components/file_manager/metadata.py'),
    ]:
        if os.path.isfile(candidate):
            metadata_script = os.path.abspath(candidate)
            break

    if metadata_script:
        # Run original metadata.py - it reads the same args and outputs JSON
        metadata_dir = os.path.dirname(metadata_script)
        sys.path.insert(0, metadata_dir)
        os.chdir(metadata_dir)
        import importlib.util
        spec = importlib.util.spec_from_file_location("metadata", metadata_script)
        metadata_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(metadata_mod)
        metadata_mod.main()
    else:
        print(
            f"Hydra: Could not find original metadata.py",
            file=sys.stderr
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
