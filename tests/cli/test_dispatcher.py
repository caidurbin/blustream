"""Tests for CLI dispatcher orchestration and confirmation."""

import argparse
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bluestream.base.commands import Command, CommandRegistry, Parameter
from bluestream.cli.dispatcher import confirm_command, dispatch


def _registry(*commands):
    reg = CommandRegistry()
    for cmd in commands:
        reg.register(cmd)
    return reg


class TestConfirmCommand:
    """Tests for confirm_command."""

    def test_static_string_message(self):
        cmd = Command(
            name="reboot",
            description="Reboot",
            parameters=[],
            handler=lambda **kw: "",
            requires_confirmation=True,
            confirmation_message="Reboot the device?",
        )
        with patch("builtins.input", return_value="yes") as mock_input:
            assert confirm_command(cmd, yes=False, kwargs={}) is True
            assert "Reboot the device?" in mock_input.call_args[0][0]

    def test_callable_message_receives_kwargs(self):
        cmd = Command(
            name="preset_delete",
            description="Delete preset",
            parameters=[],
            handler=lambda **kw: "",
            requires_confirmation=True,
            confirmation_message=lambda kwargs: f"Delete preset {kwargs['preset']}?",
        )
        with patch("builtins.input", return_value="yes") as mock_input:
            assert confirm_command(cmd, yes=False, kwargs={"preset": 3}) is True
            assert "Delete preset 3?" in mock_input.call_args[0][0]

    def test_generic_fallback_when_message_unset(self):
        cmd = Command(
            name="danger_cmd",
            description="Dangerous",
            parameters=[],
            handler=lambda **kw: "",
            requires_confirmation=True,
        )
        with patch("builtins.input", return_value="yes") as mock_input:
            assert confirm_command(cmd, yes=False, kwargs={}) is True
            assert "danger_cmd" in mock_input.call_args[0][0]

    def test_yes_flag_bypasses_prompt(self):
        cmd = Command(
            name="reboot",
            description="Reboot",
            parameters=[],
            handler=lambda **kw: "",
            requires_confirmation=True,
            confirmation_message="Reboot?",
        )
        with patch("builtins.input") as mock_input:
            assert confirm_command(cmd, yes=True, kwargs={}) is True
            mock_input.assert_not_called()

    def test_user_declines(self):
        cmd = Command(
            name="reboot",
            description="Reboot",
            parameters=[],
            handler=lambda **kw: "",
            requires_confirmation=True,
            confirmation_message="Reboot?",
        )
        with patch("builtins.input", return_value="no"):
            assert confirm_command(cmd, yes=False, kwargs={}) is False

    def test_no_confirmation_required_proceeds(self):
        cmd = Command(
            name="status",
            description="Status",
            parameters=[],
            handler=lambda **kw: "",
            requires_confirmation=False,
        )
        with patch("builtins.input") as mock_input:
            assert confirm_command(cmd, yes=False, kwargs={}) is True
            mock_input.assert_not_called()


class TestDispatchOrchestration:
    """Tests for dispatch function orchestration."""

    @pytest.mark.asyncio
    async def test_validation_runs_before_factory(self):
        """Factory should NOT be called when validation fails."""
        events = []

        def factory():
            events.append("factory")
            device = MagicMock()
            device.connect = AsyncMock()
            device.disconnect = AsyncMock()
            device.execute_command = AsyncMock(return_value="ok")
            return device

        reg = _registry(
            Command(
                name="test_cmd",
                description="Test",
                parameters=[Parameter("output", int, required=True, choices=[1, 2, 3])],
                handler=lambda **kw: "",
            )
        )

        args = argparse.Namespace(command="test_cmd", output=99, yes=False, json=False)
        exit_code = await dispatch(args, reg, factory)
        assert exit_code == 1
        assert "factory" not in events

    @pytest.mark.asyncio
    async def test_exit_code_zero_on_success(self):
        device = MagicMock()
        device.connect = AsyncMock()
        device.disconnect = AsyncMock()
        device.execute_command = AsyncMock(return_value="ok")

        reg = _registry(
            Command(name="status", description="Status", parameters=[], handler=lambda **kw: "")
        )

        args = argparse.Namespace(command="status", yes=False, json=False)
        exit_code = await dispatch(args, reg, lambda: device)
        assert exit_code == 0
        device.execute_command.assert_called_once_with("status")

    @pytest.mark.asyncio
    async def test_exit_code_one_on_validation_failure(self):
        reg = _registry(
            Command(
                name="test_cmd",
                description="Test",
                parameters=[Parameter("output", int, required=True)],
                handler=lambda **kw: "",
            )
        )
        args = argparse.Namespace(command="test_cmd", output=None, yes=False, json=False)
        exit_code = await dispatch(args, reg, lambda: None)
        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_confirmation_yes_flag_proceeds(self):
        device = MagicMock()
        device.connect = AsyncMock()
        device.disconnect = AsyncMock()
        device.execute_command = AsyncMock(return_value="ok")

        reg = _registry(
            Command(
                name="reboot",
                description="Reboot",
                parameters=[],
                handler=lambda **kw: "",
                requires_confirmation=True,
                confirmation_message="Reboot?",
            )
        )

        args = argparse.Namespace(command="reboot", yes=True, json=False)
        exit_code = await dispatch(args, reg, lambda: device)
        assert exit_code == 0
        device.execute_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirmation_declined_returns_zero(self):
        reg = _registry(
            Command(
                name="reboot",
                description="Reboot",
                parameters=[],
                handler=lambda **kw: "",
                requires_confirmation=True,
                confirmation_message="Reboot?",
            )
        )

        args = argparse.Namespace(command="reboot", yes=False, json=False)
        with patch("bluestream.cli.dispatcher.confirm_command", return_value=False):
            exit_code = await dispatch(args, reg, lambda: None)
        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_format_result_used_when_present(self):
        device = MagicMock()
        device.connect = AsyncMock()
        device.disconnect = AsyncMock()
        device.execute_command = AsyncMock(return_value={"temp": 42})

        def fmt(result, ctx):
            return f"formatted: {result}"

        reg = _registry(
            Command(
                name="status",
                description="Status",
                parameters=[],
                handler=lambda **kw: "",
                format_result=fmt,
            )
        )

        args = argparse.Namespace(command="status", yes=False, json=False)
        with patch("builtins.print") as mock_print:
            exit_code = await dispatch(args, reg, lambda: device)
        assert exit_code == 0
        mock_print.assert_called_once_with("formatted: {'temp': 42}")

    @pytest.mark.asyncio
    async def test_str_fallback_when_no_formatter(self):
        device = MagicMock()
        device.connect = AsyncMock()
        device.disconnect = AsyncMock()
        device.execute_command = AsyncMock(return_value="raw result")

        reg = _registry(
            Command(name="test_cmd", description="Test", parameters=[], handler=lambda **kw: "")
        )

        args = argparse.Namespace(command="test_cmd", yes=False, json=False)
        with patch("builtins.print") as mock_print:
            exit_code = await dispatch(args, reg, lambda: device)
        assert exit_code == 0
        mock_print.assert_called_once_with("raw result")

    @pytest.mark.asyncio
    async def test_disconnect_called_on_success(self):
        device = MagicMock()
        device.connect = AsyncMock()
        device.disconnect = AsyncMock()
        device.execute_command = AsyncMock(return_value="ok")

        reg = _registry(
            Command(name="test_cmd", description="Test", parameters=[], handler=lambda **kw: "")
        )

        args = argparse.Namespace(command="test_cmd", yes=False, json=False)
        await dispatch(args, reg, lambda: device)
        device.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_called_on_error(self):
        device = MagicMock()
        device.connect = AsyncMock()
        device.disconnect = AsyncMock()
        device.execute_command = AsyncMock(
            side_effect=Exception("boom")
        )

        reg = _registry(
            Command(name="test_cmd", description="Test", parameters=[], handler=lambda **kw: "")
        )

        args = argparse.Namespace(command="test_cmd", yes=False, json=False)
        await dispatch(args, reg, lambda: device)
        device.disconnect.assert_called_once()
