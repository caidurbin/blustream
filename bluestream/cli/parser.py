"""Metadata-driven CLI parser generator."""

import argparse
from typing import Any, Dict, List, Optional

from bluestream.base.commands import Command, CommandRegistry, Parameter


def _snake_to_kebab(name: str) -> str:
    return name.replace("_", "-")


def build_parser(
    registry: CommandRegistry,
    parents: Optional[List[argparse.ArgumentParser]] = None,
) -> argparse.ArgumentParser:
    """Build an ArgumentParser from command registry metadata.

    Pure function — performs no I/O.
    """
    parser = argparse.ArgumentParser(
        description="Bluestream device control CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=parents or [],
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    for cmd in registry.get_all():
        kebab_name = _snake_to_kebab(cmd.name)
        sub = subparsers.add_parser(
            kebab_name,
            help=cmd.description,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        sub.set_defaults(command=cmd.name)

        for param in cmd.parameters:
            _add_parameter(sub, param)

    return parser


def _add_parameter(parser: argparse.ArgumentParser, param: Parameter) -> None:
    flag = f"--{_snake_to_kebab(param.name)}"

    if param.type is bool:
        parser.add_argument(
            flag,
            action=argparse.BooleanOptionalAction,
            required=param.required,
            default=param.default,
            help=param.help_text or None,
        )
    elif param.supports_relative:
        kebab_name = _snake_to_kebab(param.name)
        group = parser.add_mutually_exclusive_group(required=param.required)
        group.add_argument(
            flag,
            type=int,
            default=None,
            help=param.help_text or None,
        )
        group.add_argument(
            f"--increase-{kebab_name}",
            action="store_true",
            default=False,
            help=f"Increase {param.name} by one step",
        )
        group.add_argument(
            f"--decrease-{kebab_name}",
            action="store_true",
            default=False,
            help=f"Decrease {param.name} by one step",
        )
    else:
        kw: Dict[str, Any] = {}
        if param.required:
            kw["required"] = True
        else:
            kw["default"] = None
        if param.help_text:
            kw["help"] = param.help_text
        if param.choices:
            kw["choices"] = param.choices
        if param.type is not Any and param.type is not str:
            kw["type"] = param.type
        parser.add_argument(flag, **kw)


def extract_kwargs(namespace: argparse.Namespace, command: Command) -> Dict[str, Any]:
    """Extract command kwargs from a parsed argparse Namespace.

    Translates --increase-<name> / --decrease-<name> into kwargs[name] = "+" / "-".
    """
    kwargs: Dict[str, Any] = {}

    for param in command.parameters:
        if param.supports_relative and getattr(namespace, f"increase_{param.name}", False):
            kwargs[param.name] = "+"
        elif param.supports_relative and getattr(namespace, f"decrease_{param.name}", False):
            kwargs[param.name] = "-"
        else:
            value = getattr(namespace, param.name, None)
            if value is not None:
                kwargs[param.name] = value

    return kwargs
