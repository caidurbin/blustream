"""Constants for the Blustream integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "blustream"
DEFAULT_PORT = 23
SCAN_INTERVAL = timedelta(seconds=30)

# DMP168 channel counts (fixed hardware geometry; see ADR 0014).
OUTPUT_COUNT = 8
INPUT_COUNT = 16
BUS_COUNT = 8
