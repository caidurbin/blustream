"""Main CLI entry point."""

import argparse
import asyncio
import logging
import sys

from blustream.cli.dispatcher import dispatch
from blustream.cli.parser import build_parser
from blustream.devices.dmp168.device import DMP168

DEVICES: dict[str, type] = {
    "dmp168": DMP168,
}


def suppress_telnetlib3_errors(loop, context):
    """Suppress harmless telnetlib3 'feed_data after feed_eof' errors."""
    exception = context.get("exception")
    if exception and isinstance(exception, AssertionError):
        if "feed_data after feed_eof" in str(exception):
            return
    loop.default_exception_handler(context)


def setup_logging(verbose: bool = False, debug: bool = False) -> None:
    level = logging.WARNING
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _create_global_parser() -> argparse.ArgumentParser:
    """Create parser with global options only (no subcommands)."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--device",
        choices=list(DEVICES.keys()),
        default="dmp168",
        help="Device type (default: dmp168)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Device hostname or IP address (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=23,
        help="TCP port (default: 23)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Connection timeout in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmations",
    )
    parser.add_argument(
        "--command-log",
        metavar="PATH",
        default=None,
        help=(
            "Append each command sent to the device to PATH with a UTC timestamp, "
            "using the same '==== <ts> ====' format as monitor_dmp168.sh."
        ),
    )
    return parser


async def main_async() -> int:
    """Main CLI entry point (async)."""
    global_parser = _create_global_parser()
    global_args, _ = global_parser.parse_known_args()

    device_cls = DEVICES.get(global_args.device)
    if device_cls is None:
        print(f"Unknown device: {global_args.device}", file=sys.stderr)
        return 1

    registry = device_cls.commands
    full_parser = build_parser(registry, parents=[global_parser])
    args = full_parser.parse_args()

    if not args.command:
        full_parser.print_help()
        return 1

    setup_logging(verbose=args.verbose, debug=args.debug)

    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(suppress_telnetlib3_errors)
    except RuntimeError:
        pass

    def device_factory():
        return device_cls(
            host=args.host,
            port=args.port,
            timeout=args.timeout,
            command_log_path=args.command_log,
        )

    try:
        return await dispatch(args, registry, device_factory)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.debug:
            import traceback

            traceback.print_exc()
        return 1


def main() -> int:
    """Main CLI entry point (synchronous wrapper)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(suppress_telnetlib3_errors)
    try:
        return loop.run_until_complete(main_async())
    finally:
        loop.close()


if __name__ == "__main__":
    sys.exit(main())
