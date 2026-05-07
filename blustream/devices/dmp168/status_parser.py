"""Pure-function STATUS parser for the DMP168.

Returns a plain ``dict`` of primitives (str / int / float / bool / list / dict /
None) so the structured state is identical to what the Lua sibling parser
produces under
``control4/dmp168/src/status_parser.lua`` for the same shared fixtures under
``spec/vectors/fixtures/``.

This module is intentionally independent of :class:`blustream.devices.dmp168.parser.DMP168Parser`
(which produces dataclasses for legacy callers). Cross-language parity is the
contract here, not Python ergonomics.
"""

from __future__ import annotations

import re
from typing import Any

_INPUT_LINE_RE = re.compile(r"^In(\d+)\b")
_OUTPUT_LINE_RE = re.compile(r"^Out(\d+)\b")
_FROM_INPUT_RE = re.compile(r"^In(\d+)$")
_FW_VERSION_RE = re.compile(r"FW Version:\s*([^\r\n]+?)\s*$")


def parse(response_text: str) -> dict[str, Any]:
    """Parse a captured ``STATUS`` response into a structured-state dict.

    Missing sections degrade gracefully: a response that contains only the
    system-status header + data line yields ``inputs: []`` and ``routing: []``
    rather than raising. This mirrors the partial-response fixture under
    ``spec/vectors/fixtures/status_partial.txt``.
    """
    lines = response_text.splitlines()
    return {
        **_parse_system(lines),
        "firmware_version": _parse_firmware(lines),
        "inputs": _parse_inputs(lines),
        "routing": _parse_routing(lines),
    }


def _parse_system(lines: list[str]) -> dict[str, Any]:
    header_idx = None
    for i, line in enumerate(lines):
        if "Power" in line and "Baud" in line:
            header_idx = i
            break
    if header_idx is None or header_idx + 1 >= len(lines):
        raise ValueError("STATUS response missing Power/Baud header line")

    data_line = lines[header_idx + 1]
    parts = data_line.split()
    if len(parts) < 8:
        raise ValueError(
            f"STATUS data line has {len(parts)} fields; expected at least 8"
        )

    return {
        "power": parts[0],
        "baud": int(parts[1]),
        "level_unit": parts[2],
        "auto_standby_time": int(parts[3]),
        "dsp_usage": float(parts[4].rstrip("%")),
        "fade": parts[5] == "On",
        "temperature": float(parts[6].rstrip("C")),
        "uptime": parts[7],
    }


def _parse_firmware(lines: list[str]) -> str:
    for line in lines:
        match = _FW_VERSION_RE.search(line)
        if not match:
            continue
        candidate = match.group(1).strip()
        # The welcome banner emits a bare "FW Version: 1.1.0"; the status block
        # emits the structured "FW Version:MCU_Main Vx.y.z/Web_GUI Vx.y.z".
        # Require "/" or "_" to skip the banner and prefer the structured form.
        if "/" in candidate or "_" in candidate:
            return candidate
    return "Unknown"


def _parse_inputs(lines: list[str]) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    in_section = False
    for line in lines:
        if "Input Settings Status" in line:
            in_section = True
            continue
        if not in_section:
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        # The "Port Lock % Mute" header row and the L/R sub-header don't start
        # with "In<digit>" and so are skipped here.
        port_match = _INPUT_LINE_RE.match(parts[0])
        if not port_match:
            continue
        inputs.append(
            {
                "port": int(port_match.group(1)),
                "lock": parts[1] == "On",
                "gain_l": int(parts[2]),
                "gain_r": int(parts[3]),
                "mute_l": parts[4] == "On",
                "mute_r": parts[5] == "On",
            }
        )
    return inputs


def _parse_routing(lines: list[str]) -> list[dict[str, Any]]:
    routing: list[dict[str, Any]] = []
    in_section = False
    for line in lines:
        if "Matrix Config Status" in line:
            in_section = True
            continue
        if not in_section:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        output_match = _OUTPUT_LINE_RE.match(parts[0])
        if not output_match:
            continue
        from_input: int | None = None
        for token in parts[2:]:
            in_match = _FROM_INPUT_RE.match(token)
            if in_match:
                from_input = int(in_match.group(1))
                break
        routing.append(
            {
                "output": int(output_match.group(1)),
                "channel": parts[1] if parts[1] in ("L", "R") else "L",
                "from_input": from_input,
            }
        )
    return routing
