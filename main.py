#!/usr/bin/env python3
"""CLI entry point for Bluestream device control."""

from bluestream.cli.main import main

if __name__ == "__main__":
    import sys
    sys.exit(main())

