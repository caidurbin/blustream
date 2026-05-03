"""Centralized parameter validation."""

from typing import Any, Dict, List, Tuple

from bluestream.base.commands import CommandRegistry
from bluestream.base.exceptions import CommandError, ValidationError


def validate(
    registry: CommandRegistry, command_name: str, kwargs: Dict[str, Any]
) -> None:
    """Validate parameters for a command.

    Runs per-parameter checks (required, choices, validation callable),
    collecting all failures into a single ValidationError.

    Args:
        registry: Command registry to look up the command.
        command_name: Name of the command to validate.
        kwargs: Parameter values to validate.

    Raises:
        CommandError: If the command is not found.
        ValidationError: If any parameter fails validation, with all
            failures collected in the ``errors`` attribute.
    """
    command = registry.get(command_name)
    if not command:
        raise CommandError(
            f"Unknown command '{command_name}'. "
            "Use 'get_commands()' to see available commands."
        )

    errors: List[Tuple[str, str]] = []

    for param in command.parameters:
        if param.required and param.name not in kwargs:
            errors.append((
                param.name,
                f"Missing required parameter '{param.name}' for command "
                f"'{command_name}'.",
            ))
            continue

        if param.name not in kwargs:
            continue

        value = kwargs[param.name]

        if value is None and not param.required:
            continue

        if param.choices and value not in param.choices:
            choices_str = ", ".join(str(c) for c in param.choices[:5])
            if len(param.choices) > 5:
                choices_str += f", ... (total {len(param.choices)} options)"
            errors.append((
                param.name,
                f"Invalid value '{value}' for parameter '{param.name}'. "
                f"Valid options are: {choices_str}.",
            ))

        if param.validation is not None:
            result = param.validation(value)
            if result is not None:
                errors.append((param.name, result))

    if errors:
        messages = "; ".join(
            f"{name}: {msg}" for name, msg in errors
        )
        raise ValidationError(
            f"Validation failed for '{command_name}': {messages}",
            errors=errors,
        )
