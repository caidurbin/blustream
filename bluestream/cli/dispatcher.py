"""CLI command dispatcher."""

import argparse
import sys
from typing import Any, Callable

from bluestream.base.commands import Command, CommandRegistry, RenderContext
from bluestream.base.exceptions import BluestreamError, ValidationError
from bluestream.base.validator import validate
from bluestream.cli.parser import extract_kwargs


def confirm_command(command: Command, yes: bool, kwargs: dict) -> bool:
    """Prompt for confirmation if command requires it.

    Returns True if command should proceed, False if cancelled.
    """
    if not command.requires_confirmation:
        return True
    if yes:
        return True

    msg = command.confirmation_message
    if msg is None:
        prompt = f"Execute {command.name}? (yes/no): "
    elif callable(msg):
        prompt = f"{msg(kwargs)} (yes/no): "
    else:
        prompt = f"{msg} (yes/no): "

    confirm = input(prompt)
    if confirm.lower() not in ("yes", "y"):
        print("Cancelled")
        return False
    return True


async def dispatch(
    args: argparse.Namespace,
    registry: CommandRegistry,
    device_factory: Callable[[], Any],
) -> int:
    """Orchestrate CLI command execution.

    Sequence: extract kwargs -> validate (pre-connect) -> confirm ->
    factory -> connect -> execute_command -> format -> print -> disconnect.

    Returns exit code (0 for success, non-zero for error).
    """
    command = registry.get(args.command)
    if command is None:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1

    kwargs = extract_kwargs(args, command)

    try:
        validate(registry, args.command, kwargs)
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    yes = getattr(args, "yes", False)
    if not confirm_command(command, yes, kwargs):
        return 0

    device = device_factory()
    try:
        await device.connect()
    except Exception as e:
        print(f"Error: Failed to connect: {e}", file=sys.stderr)
        return 1

    try:
        result = await device.execute_command(args.command, **kwargs)

        ctx = RenderContext(json=getattr(args, "json", False))
        if command.format_result:
            output = command.format_result(result, ctx)
        else:
            output = str(result)
        print(output)
        return 0
    except BluestreamError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1
    finally:
        await device.disconnect()
