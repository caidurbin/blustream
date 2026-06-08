#!/usr/bin/env python3
"""CLI entry point for Blustream device control."""

from blustream.cli.main import main

if __name__ == "__main__":
    import sys

    sys.exit(main())
