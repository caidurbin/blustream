"""End-to-end CLI tests via MockConnection-backed device factory."""

from typing import Callable
from unittest.mock import MagicMock, patch

import pytest

from blustream.base.connection import Connection
from blustream.base.exceptions import ConnectionError
from blustream.cli.dispatcher import dispatch
from blustream.cli.parser import build_parser
from blustream.devices.dmp168.device import DMP168


class MockConnection(Connection):
    """Mock connection that records sends and replays a canned reply.

    Each call to ``read_until`` plays the configured response back through
    the predicate exactly as the real TCPConnection would: lines are fed
    in order until one satisfies the predicate, at which point the
    accumulated text is returned. This means STATUS-shaped fixtures must
    actually end with the second ``=``-only line that the STATUS
    terminator expects.
    """

    def __init__(self):
        self._connected = False
        self._send_calls = []
        self._response = "[SUCCESS]ok\r\n"

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def send(self, data: bytes) -> None:
        if not self._connected:
            raise ConnectionError("Not connected")
        self._send_calls.append(data)

    async def read_until(self, predicate: Callable[[str], bool], timeout: float) -> str:
        if not self._connected:
            raise ConnectionError("Not connected")
        accumulated = ""
        for line in _split_keep_terminator(self._response):
            accumulated += line
            if predicate(line):
                return accumulated
        # Replay exhausted without satisfying the predicate.
        raise ConnectionError("mock response did not contain a satisfying line")

    def is_connected(self) -> bool:
        return self._connected


def _split_keep_terminator(text: str) -> list[str]:
    """Split on ``\\r\\n`` keeping each terminator attached to its line."""
    lines: list[str] = []
    pos = 0
    while True:
        idx = text.find("\r\n", pos)
        if idx < 0:
            if pos < len(text):
                lines.append(text[pos:])
            return lines
        lines.append(text[pos : idx + 2])
        pos = idx + 2


# Real STATUS shape: opener ===, body, footer ===. Two =-only lines total —
# the STATUS terminator fires on the second.
STATUS_RESPONSE = (
    "================================================================\r\n"
    "                      DMP168 Status\r\n"
    "      FW Version:MCU_Main V1.0.0/Web_GUI V1.0.0\r\n"
    "\r\n"
    "Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)\r\n"
    "On            57600   %             0                          36.79     Off     47.2C     0000:08:57:01\r\n"
    "\r\n"
    "Matrix Config Status\r\n"
    "Output        FromIn\r\n"
    "Out1 L        In1 L\r\n"
    "Out1 R        In1 R\r\n"
    "\r\n"
    "Input Settings Status\r\n"
    "Port    Lock   %       Mute\r\n"
    "        LR   L   R    L   R\r\n"
    "In1     Off  50  50   Off Off\r\n"
    "================================================================\r\n"
)


def _factory(response: str = "[SUCCESS]ok\r\n"):
    """Create a MockConnection-backed DMP168 factory."""
    conn = MockConnection()
    conn._response = response

    def factory():
        return DMP168(host="test", connection=conn)

    return factory, conn


def _parse(registry, argv):
    """Parse argv against a registry and return namespace."""
    parser = build_parser(registry)
    return parser.parse_args(argv)


class TestE2EStatus:
    """End-to-end: status command."""

    @pytest.mark.asyncio
    async def test_status_success(self):
        factory, conn = _factory(STATUS_RESPONSE)
        registry = DMP168.commands

        args = _parse(registry, ["status"])
        args.yes = False
        args.json = False

        with patch("builtins.print") as mock_print:
            exit_code = await dispatch(args, registry, factory)

        assert exit_code == 0
        output = mock_print.call_args[0][0]
        assert "Power" in output
        assert "On" in output

    @pytest.mark.asyncio
    async def test_status_json(self):
        factory, conn = _factory(STATUS_RESPONSE)
        registry = DMP168.commands

        args = _parse(registry, ["status"])
        args.yes = False
        args.json = True

        with patch("builtins.print") as mock_print:
            exit_code = await dispatch(args, registry, factory)

        assert exit_code == 0
        output = mock_print.call_args[0][0]
        assert '"power"' in output


class TestE2EOutputVolume:
    """End-to-end: output-volume command."""

    @pytest.mark.asyncio
    async def test_absolute_volume(self):
        factory, conn = _factory()
        registry = DMP168.commands

        args = _parse(registry, ["output-volume", "--output", "1", "--level", "75"])
        args.yes = False
        args.json = False

        exit_code = await dispatch(args, registry, factory)
        assert exit_code == 0
        sent = conn._send_calls[-1].decode()
        assert "OUT 1" in sent
        assert "VOL" in sent
        assert "75" in sent

    @pytest.mark.asyncio
    async def test_increase_level(self):
        factory, conn = _factory()
        registry = DMP168.commands

        args = _parse(registry, ["output-volume", "--output", "1", "--increase-level"])
        args.yes = False
        args.json = False

        exit_code = await dispatch(args, registry, factory)
        assert exit_code == 0
        sent = conn._send_calls[-1].decode()
        assert "OUT 1" in sent
        assert "VOL" in sent
        assert "+" in sent

    @pytest.mark.asyncio
    async def test_decrease_level(self):
        factory, conn = _factory()
        registry = DMP168.commands

        args = _parse(registry, ["output-volume", "--output", "1", "--decrease-level"])
        args.yes = False
        args.json = False

        exit_code = await dispatch(args, registry, factory)
        assert exit_code == 0
        sent = conn._send_calls[-1].decode()
        assert "-" in sent


class TestE2EPresetSave:
    """End-to-end: preset-save with --yes."""

    @pytest.mark.asyncio
    async def test_preset_save_with_yes(self):
        factory, conn = _factory()
        registry = DMP168.commands

        args = _parse(registry, ["preset-save", "--preset", "3"])
        args.yes = True
        args.json = False

        exit_code = await dispatch(args, registry, factory)
        assert exit_code == 0
        sent = conn._send_calls[-1].decode()
        assert "PRESET 3 SAVE" in sent


class TestE2EReboot:
    """End-to-end: reboot with confirmation declined."""

    @pytest.mark.asyncio
    async def test_reboot_declined(self):
        factory, conn = _factory()
        registry = DMP168.commands

        args = _parse(registry, ["reboot"])
        args.yes = False
        args.json = False

        with patch("blustream.cli.dispatcher.confirm_command", return_value=False):
            exit_code = await dispatch(args, registry, factory)

        assert exit_code == 0
        assert len(conn._send_calls) == 0

    @pytest.mark.asyncio
    async def test_reboot_confirmed(self):
        factory, conn = _factory()
        registry = DMP168.commands

        args = _parse(registry, ["reboot"])
        args.yes = True
        args.json = False

        exit_code = await dispatch(args, registry, factory)
        assert exit_code == 0
        sent = conn._send_calls[-1].decode()
        assert "REBOOT" in sent


class TestE2EValidation:
    """End-to-end: invalid combinations trigger pre-connect validation."""

    @pytest.mark.asyncio
    async def test_invalid_output_fails_preconnect(self):
        """Invalid parameter value rejected before any connection."""
        factory_called = []

        def factory():
            factory_called.append(True)
            return MagicMock()

        registry = DMP168.commands
        args = _parse(registry, ["output-volume", "--output", "1", "--level", "75"])
        args.output = 99
        args.yes = False
        args.json = False

        exit_code = await dispatch(args, registry, factory)
        assert exit_code == 1
        assert len(factory_called) == 0

    @pytest.mark.asyncio
    async def test_unit_with_relative_rejected(self):
        """--unit dB with --increase-level rejected pre-connect."""
        factory_called = []

        def factory():
            factory_called.append(True)
            return MagicMock()

        registry = DMP168.commands
        args = _parse(registry, ["output-volume", "--output", "1", "--increase-level"])
        args.unit = "dB"
        args.yes = False
        args.json = False

        exit_code = await dispatch(args, registry, factory)
        assert exit_code == 1
        assert len(factory_called) == 0


class TestE2EBooleanCommands:
    """End-to-end: boolean parameter commands."""

    @pytest.mark.asyncio
    async def test_output_mute_on(self):
        factory, conn = _factory()
        registry = DMP168.commands

        args = _parse(registry, ["output-mute", "--output", "1", "--mute"])
        args.yes = False
        args.json = False

        exit_code = await dispatch(args, registry, factory)
        assert exit_code == 0
        sent = conn._send_calls[-1].decode()
        assert "MUTE" in sent
        assert "ON" in sent

    @pytest.mark.asyncio
    async def test_output_mute_off(self):
        factory, conn = _factory()
        registry = DMP168.commands

        args = _parse(registry, ["output-mute", "--output", "1", "--no-mute"])
        args.yes = False
        args.json = False

        exit_code = await dispatch(args, registry, factory)
        assert exit_code == 0
        sent = conn._send_calls[-1].decode()
        assert "MUTE" in sent
        assert "OFF" in sent
