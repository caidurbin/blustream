"""Centralized parameter validation."""

from typing import Any, Union

from blustream.base.commands import CommandRegistry, Dependency
from blustream.base.exceptions import CommandError, ValidationError


def _normalize_depends_on(
    depends_on: Union[str, Dependency, list[Dependency]],
) -> list[Dependency]:
    """Normalize depends_on field to a list of Dependency objects."""
    if isinstance(depends_on, str):
        return [Dependency(on=depends_on)]
    if isinstance(depends_on, Dependency):
        return [depends_on]
    return list(depends_on)


def validate(
    registry: CommandRegistry, command_name: str, kwargs: dict[str, Any]
) -> None:
    """Validate parameters for a command.

    Two-pass validation:
      Pass one: per-parameter checks (required, choices, validation callable),
        collecting all failures.
      Pass two: cross-parameter dependency checks, short-circuiting on first
        failure. Only runs when pass one collected zero failures.

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

    errors: list[tuple[str, str]] = []

    # Pass one: per-parameter checks
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

    # Pass two: cross-parameter dependency checks (short-circuits on first failure)
    for param in command.parameters:
        if param.depends_on is None:
            continue

        if param.name not in kwargs:
            continue

        value = kwargs[param.name]
        if value is None and not param.required:
            continue

        for dep in _normalize_depends_on(param.depends_on):
            dep_value = kwargs.get(dep.on)

            if dep.when is None:
                if dep_value is None:
                    errors.append((
                        param.name,
                        f"Parameter '{param.name}' requires "
                        f"'{dep.on}' to be provided.",
                    ))
                    break
            else:
                if dep_value is not None and dep.when(dep_value):
                    errors.append((
                        param.name,
                        f"Parameter '{param.name}' cannot be used "
                        f"with the current value of '{dep.on}'.",
                    ))
                    break

        if errors:
            messages = "; ".join(
                f"{name}: {msg}" for name, msg in errors
            )
            raise ValidationError(
                f"Validation failed for '{command_name}': {messages}",
                errors=errors,
            )
