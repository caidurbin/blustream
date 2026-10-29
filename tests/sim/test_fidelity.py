"""The simulator answers byte for byte as the real DMP168 did on 2026-10-29."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from blustream.devices.dmp168 import status_parser
from blustream.devices.dmp168.parser import DMP168Parser
from tests.sim.matrix import (
    ERR_NOT_FOUND,
    IAC_NEGOTIATION,
    PROMPT,
    SimulatedMatrix,
    banner,
    corrupted_status,
    recording,
)

READ_IDLE = 0.2


async def _read_idle(reader: asyncio.StreamReader, idle: float = READ_IDLE) -> bytes:
    """Read until no byte arrives for ``idle`` seconds."""
    data = b""
    while True:
        try:
            chunk = await asyncio.wait_for(reader.read(65536), timeout=idle)
        except asyncio.TimeoutError:
            return data
        if not chunk:
            return data
        data += chunk


@dataclass
class Client:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    connect_bytes: bytes

    async def ask(self, command: str) -> bytes:
        self.writer.write(command.encode() + b"\r\n")
        await self.writer.drain()
        return await self.read()

    async def read(self) -> bytes:
        return await _read_idle(self.reader)


@pytest.fixture
async def sim():
    async with SimulatedMatrix() as matrix:
        yield matrix


@pytest.fixture
async def connect(sim):
    """Open a client on the telnet or raw port; closed at teardown.

    The writers are held here because a StreamWriter that is garbage
    collected closes its socket.
    """
    writers = []

    async def _connect(telnet: bool) -> Client:
        port = sim.telnet_port if telnet else sim.raw_port
        reader, writer = await asyncio.open_connection(sim.host, port)
        writers.append(writer)
        return Client(reader, writer, await _read_idle(reader))

    yield _connect
    for writer in writers:
        writer.close()


@pytest.mark.parametrize(
    ("command", "capture"),
    [
        ("STATUS", "STATUS_2"),
        ("UPTIME", "UPTIME_1"),
        ("TEMP", "TEMP_1"),
        ("HELP", "HELP_1"),
        ("PRESET 1 STATUS", "PRESET_1_STATUS_1"),
        ("PRESET 9 STATUS", "PRESET_9_STATUS_1"),
        ("FOO", "FOO_1"),
    ],
)
async def test_replies_match_capture_on_both_ports(connect, command, capture):
    raw = await connect(telnet=False)
    assert await raw.ask(command) == recording(f"p8000_A_{capture}.bin")

    telnet = await connect(telnet=True)
    await raw.read()  # the raw client got the banner broadcast
    reply = await telnet.ask(command)
    expected = recording(f"p23_A_{capture}.bin")
    # Port 23 wraps the same body in an echo and a prompt. UPTIME, TEMP and
    # STATUS carry live readings that differed between the two captures.
    assert reply.startswith(command.encode() + b"\r\n")
    assert reply.endswith(PROMPT)
    assert len(reply) == len(expected)
    if command not in ("UPTIME", "TEMP", "STATUS"):
        assert reply == expected


async def test_port_23_connect_sends_iac_then_banner(connect):
    client = await connect(telnet=True)
    assert client.connect_bytes == recording("p23_B_connect.bin")
    assert client.connect_bytes == IAC_NEGOTIATION + banner()


async def test_port_8000_connect_sends_nothing(connect):
    client = await connect(telnet=False)
    assert client.connect_bytes == recording("p8000_A_connect.bin") == b""


async def test_port_23_connect_broadcasts_banner_to_every_open_client(connect):
    raw = await connect(telnet=False)
    telnet = await connect(telnet=True)
    await raw.read()
    await connect(telnet=True)
    assert await raw.read() == banner()
    assert await telnet.read() == recording("p23_A_after-B-connect.bin")


async def test_every_reply_reaches_every_client(connect):
    asker = await connect(telnet=False)
    raw = await connect(telnet=False)
    telnet = await connect(telnet=True)
    await asker.read()
    await raw.read()

    reply = await asker.ask("FOO")
    assert reply == recording("p8000_A_FOO_1.bin")
    assert await raw.read() == reply
    assert await telnet.read() == recording("p23_A_FOO_1.bin")


async def test_interleave_foreign_puts_another_reply_first(sim, connect):
    client = await connect(telnet=False)
    sim.interleave_foreign("TEMP")
    assert await client.ask("UPTIME") == recording("p8000_A_TEMP_1.bin") + recording(
        "p8000_A_UPTIME_1.bin"
    )


async def test_reject_next_overrides_the_reply(sim, connect):
    client = await connect(telnet=False)
    sim.reject_next()
    assert await client.ask("UPTIME") == b"[ERROR]Command not found.\r\n"
    assert await client.ask("UPTIME") == recording("p8000_A_UPTIME_1.bin")


async def test_corrupt_next_status_sends_the_captured_corrupted_dump(sim, connect):
    client = await connect(telnet=False)
    sim.corrupt_next_status()
    reply = await client.ask("STATUS")
    assert reply == corrupted_status()
    assert b"\xaa\x54" in reply
    assert reply in recording("passive_p8000_180s.bin")
    assert await client.ask("STATUS") == recording("p8000_A_STATUS_2.bin")


async def test_silent_device_accepts_but_never_answers(sim, connect):
    sim.silent = True
    client = await connect(telnet=True)
    assert client.connect_bytes == b""
    assert await client.ask("STATUS") == b""
    assert sim.received == ["STATUS"]


async def test_drop_connections_closes_clients_and_keeps_listening(sim, connect):
    client = await connect(telnet=False)
    await sim.drop_connections()
    assert await client.reader.read(1) == b""
    assert await (await connect(telnet=False)).ask("FOO") == ERR_NOT_FOUND


async def test_telnet_negotiation_from_the_client_is_ignored(sim, connect):
    client = await connect(telnet=True)
    client.writer.write(b"\xff\xfd\x03\xff\xfa\x18\x00xterm\xff\xf0TEMP\r\n")
    await client.writer.drain()
    await client.read()
    assert sim.received == ["TEMP"]


def test_existing_parsers_accept_the_simulated_status():
    text = recording("p8000_A_STATUS_2.bin").decode("utf-8")
    status = DMP168Parser.parse_status(text)
    assert status.power == "On"
    assert len(status.routing) == 16
    assert status_parser.parse(text)["power"] == "On"
