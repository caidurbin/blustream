"""Tests for CLI confirmation_message integration via DMP168 commands.

These tests verify that DMP168 command registrations wire confirmation_message
correctly and that the dispatcher's confirm_command function handles all three
message formats (string, callable, None fallback).

Detailed unit tests for confirm_command live in tests/cli/test_dispatcher.py.
"""

from unittest.mock import patch

from blustream.cli.dispatcher import confirm_command
from blustream.devices.dmp168.device import DMP168


class TestDMP168ConfirmationWiring:
    """Verify DMP168 command registrations wire confirmation_message correctly."""

    def test_reboot_static_message(self):
        cmd = DMP168.commands.get("reboot")
        assert cmd is not None
        assert cmd.requires_confirmation is True
        assert isinstance(cmd.confirmation_message, str)
        with patch("builtins.input", return_value="yes"):
            assert confirm_command(cmd, yes=False, kwargs={}) is True

    def test_preset_delete_callable_message(self):
        cmd = DMP168.commands.get("preset_delete")
        assert cmd is not None
        assert callable(cmd.confirmation_message)
        with patch("builtins.input", return_value="yes") as mock_input:
            assert confirm_command(cmd, yes=False, kwargs={"preset": 3}) is True
            assert "3" in mock_input.call_args[0][0]

    def test_output_remove_callable_message(self):
        cmd = DMP168.commands.get("output_remove")
        assert cmd is not None
        assert callable(cmd.confirmation_message)
        with patch("builtins.input", return_value="yes") as mock_input:
            assert confirm_command(cmd, yes=False, kwargs={"output": 2, "input": 5}) is True
            assert "2" in mock_input.call_args[0][0]
            assert "5" in mock_input.call_args[0][0]

    def test_status_no_confirmation(self):
        cmd = DMP168.commands.get("status")
        assert cmd is not None
        assert cmd.requires_confirmation is False
        assert confirm_command(cmd, yes=False, kwargs={}) is True
