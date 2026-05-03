"""Command metadata and protocol interface."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type

# Type alias for command handlers
CommandHandler = Callable[..., str]


@dataclass
class Parameter:
    """Command parameter metadata."""

    name: str
    type: Type
    required: bool = True
    default: Any = None
    choices: Optional[List[Any]] = None
    help_text: str = ""
    validation: Optional[Callable[[Any], Optional[str]]] = None
    depends_on: Optional[str] = None  # Parameter name this depends on


@dataclass
class Command:
    """Command metadata."""

    name: str
    description: str
    parameters: List[Parameter]
    handler: CommandHandler
    return_type: Type = str
    requires_confirmation: bool = False


class CommandRegistry:
    """Registry for device commands."""

    def __init__(self):
        """Initialize empty registry."""
        self._commands: Dict[str, Command] = {}

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

    def list_commands(self) -> List[str]:
        """List all registered command names.

        Returns:
            List of command names
        """
        return list(self._commands.keys())

    def get_all(self) -> List[Command]:
        """Get all registered commands.

        Returns:
            List of all command metadata
        """
        return list(self._commands.values())

