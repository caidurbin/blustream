"""Command metadata and protocol interface."""

from dataclasses import dataclass
from typing import Any, Callable, Optional, Union

# Type alias for command handlers
CommandHandler = Callable[..., str]


@dataclass
class RenderContext:
    """Context passed to format_result callables."""

    json: bool = False


@dataclass
class Dependency:
    """Cross-parameter dependency rule."""

    on: str
    when: Optional[Callable[[Any], bool]] = None


@dataclass
class Parameter:
    """Command parameter metadata."""

    name: str
    type: type
    required: bool = True
    default: Any = None
    choices: Optional[list[Any]] = None
    help_text: str = ""
    validation: Optional[Callable[[Any], Optional[str]]] = None
    depends_on: Optional[Union[str, Dependency, list[Dependency]]] = None
    supports_relative: bool = False


@dataclass
class Command:
    """Command metadata."""

    name: str
    description: str
    parameters: list[Parameter]
    handler: CommandHandler
    return_type: type = str
    requires_confirmation: bool = False
    format_result: Optional[Callable[[Any, RenderContext], str]] = None
    confirmation_message: Optional[Union[str, Callable[[dict], str]]] = None


class CommandRegistry:
    """Registry for device commands."""

    def __init__(self):
        """Initialize empty registry."""
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> None:
        """Register a command.

        Args:
            command: Command metadata to register
        """
        self._commands[command.name] = command

    def get(self, name: str) -> Optional[Command]:
        """Get command by name.

        Args:
            name: Command name

        Returns:
            Command metadata or None if not found
        """
        return self._commands.get(name)

    def list_commands(self) -> list[str]:
        """List all registered command names.

        Returns:
            List of command names
        """
        return list(self._commands.keys())

    def get_all(self) -> list[Command]:
        """Get all registered commands.

        Returns:
            List of all command metadata
        """
        return list(self._commands.values())
