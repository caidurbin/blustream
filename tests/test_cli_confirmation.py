"""Tests for CLI confirmation_message integration."""

from unittest.mock import MagicMock, patch

from bluestream.base.commands import Command, CommandRegistry
from bluestream.cli.main import check_and_confirm_command


def _make_device(registry):
    device = MagicMock()
    device.get_command = lambda name: registry.get(name)
    device.command_requires_confirmation = lambda name: (
        registry.get(name).requires_confirmation if registry.get(name) else False
    )
    return device


class TestCheckAndConfirmCommand:
    """Tests for check_and_confirm_command using Command.confirmation_message."""

    def test_static_string_message(self):
        """Static confirmation_message string is rendered verbatim."""
        registry = CommandRegistry()
        registry.register(
            Command(
                name="reboot",
                description="Reboot",
                parameters=[],
                handler=lambda **kw: "",
                requires_confirmation=True,
                confirmation_message="Reboot the device?",
            )
        )
        device = _make_device(registry)

        with patch("builtins.input", return_value="yes") as mock_input:
            result = check_and_confirm_command(device, "reboot", yes=False)
            assert result is True
            prompt = mock_input.call_args[0][0]
            assert "Reboot the device?" in prompt

    def test_callable_message_receives_kwargs(self):
        """Callable confirmation_message is invoked with parsed kwargs."""
        registry = CommandRegistry()
        registry.register(
            Command(
                name="preset_delete",
                description="Delete preset",
                parameters=[],
                handler=lambda **kw: "",
                requires_confirmation=True,
                confirmation_message=lambda kwargs: f"Delete preset {kwargs['preset']}?",
            )
        )
        device = _make_device(registry)

        with patch("builtins.input", return_value="yes") as mock_input:
            result = check_and_confirm_command(
                device, "preset_delete", yes=False, preset=3
            )
            assert result is True
            prompt = mock_input.call_args[0][0]
            assert "Delete preset 3?" in prompt

    def test_generic_fallback_when_message_unset(self):
        """Generic fallback applies when confirmation_message is None."""
        registry = CommandRegistry()
        registry.register(
            Command(
                name="danger_cmd",
                description="Dangerous",
                parameters=[],
                handler=lambda **kw: "",
                requires_confirmation=True,
            )
        )
        device = _make_device(registry)

        with patch("builtins.input", return_value="yes") as mock_input:
            result = check_and_confirm_command(device, "danger_cmd", yes=False)
            assert result is True
            prompt = mock_input.call_args[0][0]
            assert "danger_cmd" in prompt

    def test_yes_flag_bypasses_prompt(self):
        """--yes flag skips the confirmation prompt entirely."""
        registry = CommandRegistry()
        registry.register(
            Command(
                name="reboot",
                description="Reboot",
                parameters=[],
                handler=lambda **kw: "",
                requires_confirmation=True,
                confirmation_message="Reboot the device?",
            )
        )
        device = _make_device(registry)

        with patch("builtins.input") as mock_input:
            result = check_and_confirm_command(device, "reboot", yes=True)
            assert result is True
            mock_input.assert_not_called()

    def test_user_declines_confirmation(self):
        """User typing 'no' cancels the command."""
        registry = CommandRegistry()
        registry.register(
            Command(
                name="reboot",
                description="Reboot",
                parameters=[],
                handler=lambda **kw: "",
                requires_confirmation=True,
                confirmation_message="Reboot the device?",
            )
        )
        device = _make_device(registry)

        with patch("builtins.input", return_value="no"):
            result = check_and_confirm_command(device, "reboot", yes=False)
            assert result is False

    def test_no_confirmation_required(self):
        """Commands without requires_confirmation proceed without prompt."""
        registry = CommandRegistry()
        registry.register(
            Command(
                name="status",
                description="Get status",
                parameters=[],
                handler=lambda **kw: "",
                requires_confirmation=False,
            )
        )
        device = _make_device(registry)

        with patch("builtins.input") as mock_input:
            result = check_and_confirm_command(device, "status", yes=False)
            assert result is True
            mock_input.assert_not_called()

    def test_unknown_command_proceeds(self):
        """Unknown command name proceeds (returns True)."""
        registry = CommandRegistry()
        device = _make_device(registry)

        result = check_and_confirm_command(device, "nonexistent", yes=False)
        assert result is True
