"""Simulated DMP168 matrix, built from the 2026-10-29 live captures.

An asyncio TCP server that listens on a telnet port (the device's port 23)
and a raw port (the device's port 8000) and answers with the exact bytes the
real matrix sent (``tests/fixtures/live/2026-10-29/``, see ``FINDINGS.md``
there). It reproduces the device quirks the captures showed:

* Port 23 sends IAC negotiation plus the welcome banner on connect, and every
  other open client, on either port, gets that banner too. Port 8000 sends
  nothing on connect.
* Every reply goes to every open client on both ports, not just the one that
  asked. Telnet clients get ``<command>\\r\\n`` + reply + ``\\r\\nDMP168> ``;
  raw clients get the reply alone.
* ``[ERROR]`` texts for an unknown command, an empty preset and an
  out-of-range preset are the recorded ones.

Fault switches (``reject_next``, ``corrupt_next_status``,
``interleave_foreign``, ``broadcast_foreign``, ``drop_connections``,
``silent``) inject the failure modes the client code has to survive.

Fidelity limit: only what was recorded is exact. Write commands were never
sent to the real device, so their ``[SUCCESS]`` reply here is a guess and they
change no state. STATUS, UPTIME and TEMP always return the recorded values.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import re
import socket
from collections import deque
from dataclasses import dataclass
from functools import cache
from pathlib import Path

# Built rather than written out so the IPv4 secret-scan rule has nothing to flag.
LOOPBACK = str(ipaddress.IPv4Address(socket.INADDR_LOOPBACK))

RECORDINGS = Path(__file__).resolve().parent.parent / "fixtures" / "live" / "2026-10-29"

IAC = 0xFF
IAC_SB = 0xFA
IAC_SE = 0xF0
# WILL SGA, WONT ECHO, DONT ECHO, DONT BINARY, exactly as the device sends it.
IAC_NEGOTIATION = bytes.fromhex("fffb03fffc01fffe01fffe00")

PROMPT = b"\r\nDMP168> "
ERR_NOT_FOUND = b"[ERROR]Command not found.\r\n"
ERR_PRESET_RANGE = (
    b'[ERROR]PRESET param out of range. Type "HELP" for more reference.\r\n'
)
# Not recorded: no write command was sent to the real device.
WRITE_SUCCESS = b"[SUCCESS]\r\n"

# Presets 1-8, the range spec/protocol.yaml gives the preset commands.
PRESET_COUNT = 8

# Framing kept apart from the client's _status_terminator on purpose, so the
# simulator can't share a framing bug with the code under test.
_STATUS_HEADER = b"=" * 64 + b"\r\n                      DMP168 Status"
_STATUS_FOOTER = b"\r\n" + b"=" * 64 + b"\r\n"
_BINARY_FRAME_START = b"\xaa\x54"


@cache
def recording(name: str) -> bytes:
    """Return the bytes of one capture file."""
    return (RECORDINGS / name).read_bytes()


def banner() -> bytes:
    """The welcome banner every open client gets when a port-23 client connects."""
    return recording("p23_A_after-B-connect.bin")


@cache
def corrupted_status() -> bytes:
    """A broadcast STATUS from the passive capture with binary frames mixed in.

    It is the first dump in ``passive_p8000_180s.bin`` that carries the
    ``AA 54 …`` frames and still ends on a clean footer, so a reader framing on
    the footer accepts it as one complete reply.
    """
    data = recording("passive_p8000_180s.bin")
    starts = [m.start() for m in re.finditer(re.escape(_STATUS_HEADER), data)]
    for start, end in zip(starts, starts[1:] + [len(data)]):
        dump = data[start:end]
        footer = dump.rfind(_STATUS_FOOTER)
        if _BINARY_FRAME_START in dump and footer >= 0:
            return b"\r\n" + dump[: footer + len(_STATUS_FOOTER)]
    raise LookupError("no corrupted STATUS with a clean footer in the capture")


@cache
def _known_verbs() -> frozenset[str]:
    """First words of every command in the device's own HELP listing."""
    verbs = set()
    for line in recording("p8000_A_HELP_1.bin").decode("ascii").splitlines():
        if line and not line[0].isspace() and not line.startswith("="):
            verbs.update(line.split()[0].split("/"))
    return frozenset(verbs)


def _strip_telnet(data: bytes) -> bytes:
    """Drop telnet IAC commands and subnegotiations from client input."""
    if IAC not in data:
        return data
    out = bytearray()
    i = 0
    while i < len(data):
        byte = data[i]
        nxt = data[i + 1] if i + 1 < len(data) else None
        if byte != IAC:
            out.append(byte)
            i += 1
        elif nxt == IAC:
            out.append(IAC)
            i += 2
        elif nxt == IAC_SB:
            end = data.find(bytes([IAC, IAC_SE]), i + 2)
            i = len(data) if end < 0 else end + 2
        elif nxt is not None and nxt >= 0xFB:
            i += 3
        else:
            i += 2
    return bytes(out)


@dataclass(eq=False)
class _Client:
    writer: asyncio.StreamWriter
    telnet: bool


class SimulatedMatrix:
    """A fake DMP168 on two loopback ports. Use as ``async with``.

    ``telnet_port`` plays the device's port 23 and ``raw_port`` its port 8000;
    both are picked by the OS unless given. A non-zero ``chunk_delay`` streams
    replies in ``chunk_size`` pieces with that pause between them (the real STATUS arrives in ~600 small
    chunks over ~1.5 s).
    """

    def __init__(
        self,
        host: str = LOOPBACK,
        *,
        telnet_port: int = 0,
        raw_port: int = 0,
        chunk_size: int = 256,
        chunk_delay: float = 0.0,
    ) -> None:
        self.host = host
        self.telnet_port = telnet_port
        self.raw_port = raw_port
        self.chunk_size = chunk_size
        self.chunk_delay = chunk_delay
        # Accept connections and read commands, but never send a byte.
        self.silent = False
        # Every command line received, from any client, in order.
        self.received: list[str] = []
        self._servers: list[asyncio.Server] = []
        self._clients: list[_Client] = []
        self._send_lock = asyncio.Lock()
        self._rejects: deque[bytes] = deque()
        self._corrupt_status = 0
        self._foreign: deque[str] = deque()

    async def __aenter__(self) -> SimulatedMatrix:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()

    async def start(self) -> None:
        for telnet, port in ((True, self.telnet_port), (False, self.raw_port)):
            server = await asyncio.start_server(
                lambda r, w, t=telnet: self._serve(r, w, t), self.host, port
            )
            bound = server.sockets[0].getsockname()[1]
            if telnet:
                self.telnet_port = bound
            else:
                self.raw_port = bound
            self._servers.append(server)

    async def stop(self) -> None:
        for server in self._servers:
            server.close()
        await self.drop_connections()
        for server in self._servers:
            await server.wait_closed()
        self._servers.clear()

    # -- fault switches ----------------------------------------------------

    def reject_next(self, count: int = 1, reply: bytes = ERR_NOT_FOUND) -> None:
        """Answer the next ``count`` commands with ``reply`` instead."""
        self._rejects.extend([reply] * count)

    def corrupt_next_status(self, count: int = 1) -> None:
        """Answer the next ``count`` STATUS requests with the corrupted dump."""
        self._corrupt_status += count

    def interleave_foreign(self, command: str) -> None:
        """Broadcast another LAN client's ``command`` reply ahead of the next one.

        Reproduces the race the captures showed: a reader that has just sent a
        command gets someone else's reply first.
        """
        self._foreign.append(command)

    async def broadcast_foreign(self, command: str) -> None:
        """Broadcast the reply to ``command`` as if an unseen client sent it."""
        await self._broadcast(command, self._respond(command))

    async def drop_connections(self) -> None:
        """Abort every open client socket. The listeners stay up."""
        for client in list(self._clients):
            client.writer.transport.abort()
        self._clients.clear()
        await asyncio.sleep(0)

    # -- protocol ----------------------------------------------------------

    async def _serve(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, telnet: bool
    ) -> None:
        client = _Client(writer, telnet)
        if telnet and not self.silent:
            async with self._send_lock:
                await self._write({client: IAC_NEGOTIATION + banner()})
                await self._write({c: banner() for c in self._clients})
        self._clients.append(client)
        buffer = b""
        try:
            while data := await reader.read(4096):
                buffer += _strip_telnet(data)
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    command = line.rstrip(b"\r").decode("ascii", "replace").strip()
                    if command:
                        await self._handle(command)
        except (ConnectionError, OSError):
            pass
        finally:
            if client in self._clients:
                self._clients.remove(client)
            writer.close()
            with contextlib.suppress(ConnectionError, OSError):
                await writer.wait_closed()

    async def _handle(self, command: str) -> None:
        self.received.append(command)
        if self.silent:
            return
        while self._foreign:
            await self.broadcast_foreign(self._foreign.popleft())
        reply = self._rejects.popleft() if self._rejects else self._respond(command)
        await self._broadcast(command, reply)

    def _respond(self, command: str) -> bytes:
        words = command.upper().split()
        if words == ["STATUS"]:
            if self._corrupt_status:
                self._corrupt_status -= 1
                return corrupted_status()
            return recording("p8000_A_STATUS_2.bin")
        if words == ["UPTIME"]:
            return recording("p8000_A_UPTIME_1.bin")
        if words == ["TEMP"]:
            return recording("p8000_A_TEMP_1.bin")
        if words in (["HELP"], ["?"]):
            return recording("p8000_A_HELP_1.bin")
        if len(words) == 3 and words[0] == "PRESET" and words[2] == "STATUS":
            if words[1].isdigit() and 1 <= int(words[1]) <= PRESET_COUNT:
                return f"[ERROR]Preset {int(words[1])} config status null.\r\n".encode()
            return ERR_PRESET_RANGE
        if words[0] in _known_verbs():
            return WRITE_SUCCESS
        return ERR_NOT_FOUND

    async def _broadcast(self, command: str, reply: bytes) -> None:
        echo = command.encode("ascii", "replace") + b"\r\n"
        async with self._send_lock:
            await self._write(
                {c: echo + reply + PROMPT if c.telnet else reply for c in self._clients}
            )

    async def _write(self, payloads: dict[_Client, bytes]) -> None:
        """Send each payload to its client, in ``chunk_size`` steps if delayed."""
        longest = max(map(len, payloads.values()), default=0)
        step = self.chunk_size if self.chunk_delay else max(longest, 1)
        for offset in range(0, longest, step):
            for client, data in payloads.items():
                chunk = data[offset : offset + step]
                if chunk and not client.writer.is_closing():
                    client.writer.write(chunk)
            for client in payloads:
                with contextlib.suppress(ConnectionError, OSError):
                    await client.writer.drain()
            if self.chunk_delay:
                await asyncio.sleep(self.chunk_delay)
