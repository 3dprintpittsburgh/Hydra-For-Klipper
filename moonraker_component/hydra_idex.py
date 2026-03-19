"""
Hydra for Klipper - Moonraker IDEX Gcode Preprocessor

Automatically preprocesses uploaded gcode files to extract lookahead
positioning data for IDEX toolchanges. Rewrites T0/T1 commands as
IDEX_TOOL_CHANGE with NEXT_X/NEXT_Y parameters.

Copyright (C) 2026 Thought Space Designs
Licensed under GPLv3
"""
from __future__ import annotations

import logging
import os
import re
import json
import hashlib
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

logger = logging.getLogger(__name__)


class HydraIdex:
    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.file_manager = self.server.lookup_component("file_manager")

        # Configuration
        self.enabled = config.getboolean("enabled", True)
        self.auto_preprocess = config.getboolean("auto_preprocess", True)
        self.backup_original = config.getboolean("backup_original", False)

        # Register event handlers
        if self.enabled and self.auto_preprocess:
            self.server.register_event_handler(
                "file_manager:filelist_changed",
                self._on_filelist_changed
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

    async def _on_filelist_changed(self, response: Dict[str, Any]) -> None:
        """Handle file upload events."""
        if not self.enabled:
            return

        action = response.get("action", "")
        if action not in ("create_file", "upload_file"):
            return

        item = response.get("item", {})
        path = item.get("path", "")

        if not path.lower().endswith(".gcode"):
            return

        # Get full filesystem path
        gc_path = self.file_manager.get_directory()
        full_path = os.path.join(gc_path, path)

        if not os.path.isfile(full_path):
            return

        try:
            metadata = await self.server.event_loop.run_in_thread(
                self._preprocess_file, full_path
            )
            if metadata:
                self.files_processed += 1
                self.last_file = path
                logger.info(
                    f"Hydra: Preprocessed {path} - "
                    f"{metadata['total_toolchanges']} toolchanges, "
                    f"{metadata['lookahead_count']} with lookahead"
                )
            else:
                logger.debug(f"Hydra: Skipped {path} (already processed or no toolchanges)")
        except Exception as e:
            logger.error(f"Hydra: Error preprocessing {path}: {e}")

    def _preprocess_file(self, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Core preprocessing algorithm.
        Scans gcode for T0/T1 commands, finds next G0/G1 XY after each,
        rewrites as IDEX_TOOL_CHANGE with NEXT_X/NEXT_Y parameters.
        Returns metadata dict or None if skipped.
        """
        # Resolve symlinks
        filepath = os.path.realpath(filepath)

        # Read the file
        with open(filepath, 'r') as f:
            lines = f.readlines()

        if not lines:
            return None

        # Check fingerprint - skip if already processed
        if self._is_processed(lines):
            return None

        # First pass: find all toolchange positions
        toolchanges = self._find_toolchanges(lines)

        if not toolchanges:
            return None

        # Second pass: rewrite toolchange lines with lookahead data
        output_lines, metadata = self._rewrite_toolchanges(lines, toolchanges)

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

        # Backup original if configured
        if self.backup_original:
            backup_path = filepath + ".orig"
            if not os.path.exists(backup_path):
                with open(backup_path, 'w') as f:
                    f.writelines(lines)

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

    def _is_processed(self, lines: List[str]) -> bool:
        """Check if file has already been preprocessed."""
        for line in lines[:5]:
            if line.startswith(FINGERPRINT_PREFIX):
                return True
        return False

    def _find_toolchanges(
        self, lines: List[str]
    ) -> List[Tuple[int, int, Optional[float], Optional[float]]]:
        """
        Find all toolchange lines and their next XY positions.
        Returns list of (line_index, tool_number, next_x, next_y).
        """
        toolchanges = []

        for i, line in enumerate(lines):
            match = T_PATTERN.match(line.strip())
            if not match:
                continue

            tool_num = int(match.group(1))

            # Look ahead for next G0/G1 with XY
            next_x, next_y = self._find_next_xy(lines, i + 1)

            toolchanges.append((i, tool_num, next_x, next_y))

        return toolchanges

    def _find_next_xy(
        self, lines: List[str], start: int
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Scan forward from start to find the first G0/G1 move with both X and Y.
        Stop scanning if we hit another T command or end of file.
        """
        for i in range(start, min(start + 200, len(lines))):
            line = lines[i].strip()

            # Stop if we hit another toolchange
            if T_PATTERN.match(line):
                break

            # Check for G0/G1 with XY
            match = G1_XY_PATTERN.match(line)
            if match:
                return float(match.group(1)), float(match.group(2))

        return None, None

    def _rewrite_toolchanges(
        self,
        lines: List[str],
        toolchanges: List[Tuple[int, int, Optional[float], Optional[float]]]
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        Rewrite toolchange lines with IDEX_TOOL_CHANGE commands.
        Returns (modified_lines, metadata).
        """
        # Build a set of line indices to rewrite
        tc_map = {tc[0]: tc for tc in toolchanges}

        output = []
        tools_used = set()
        lookahead_count = 0

        for i, line in enumerate(lines):
            if i in tc_map:
                _, tool_num, next_x, next_y = tc_map[i]
                tools_used.add(tool_num)

                if next_x is not None and next_y is not None:
                    # Lookahead mode
                    output.append(
                        f"IDEX_TOOL_CHANGE T={tool_num} "
                        f"NEXT_X={next_x:.3f} NEXT_Y={next_y:.3f} "
                        f"; {line.strip()}\n"
                    )
                    lookahead_count += 1
                else:
                    # No lookahead available
                    output.append(
                        f"IDEX_TOOL_CHANGE T={tool_num} "
                        f"; {line.strip()}\n"
                    )
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
    # API Endpoints
    # =========================================================================

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

        # Parse fingerprint
        parts = first_line.strip().split()
        info = {"processed": True}
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
            self._preprocess_file, full_path
        )

        return {
            "success": metadata is not None,
            "metadata": metadata,
        }


def load_component(config: ConfigHelper) -> HydraIdex:
    return HydraIdex(config)
