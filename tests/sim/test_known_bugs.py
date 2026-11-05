"""Known client bugs, reproduced against the simulated DMP168.

Every ``xfail(strict=True)`` test here asserts the CORRECT behaviour and fails
today because of the bug in its reason. When a fix lands the test starts
passing, strict xfail turns that into a failure, and the fix removes the
marker. The tests without a marker pin behaviour that already works against
the device quirks the live capture found.
"""

from __future__ import annotations

import asyncio

import pytest

from blustream.base.exceptions import CommandError, ParseError
from blustream.connection.tcp import TCPConnection
from blustream.devices.dmp168 import status_parser
from blustream.devices.dmp168.device import DMP168
from blustream.devices.dmp168.parser import DMP168Parser
from tests.sim.matrix import corrupted_status

# Keeps connect() quick on port 8000 and on a silent device, which send no banner.
BANNER_TIMEOUT = 0.1

RECORDED_UPTIME = "0149:04:17:56"


@pytest.fixture(params=["telnet", "raw"])
def port(request, sim) -> int:
    """Run each test once against port 23 and once against port 8000."""
    return sim.telnet_port if request.param == "telnet" else sim.raw_port


@pytest.fixture
async def device(sim, port):
    connection = TCPConnection(sim.host, port, banner_timeout=BANNER_TIMEOUT)
    dmp = DMP168(sim.host, port, connection=connection)
    await dmp.connect()
    yield dmp
    await dmp.disconnect()


# -- B1: [ERROR] replies are reported as success ----------------------------


@pytest.mark.xfail(
    strict=True,
    reason="B1: send_command returns an [ERROR] reply as a normal response, "
    "so a command the device rejects is reported as a success",
)
async def test_rejected_command_raises(sim, device):
    sim.reject_next()
    with pytest.raises(CommandError):
        await device.route_input_to_output(input_ch=1, output=8)


# -- B2: the client never reconnects after the link drops -------------------


@pytest.mark.xfail(
    strict=True,
    reason="B2: when the device closes the socket, is_connected stays True, "
    "so the poll never calls connect() again and fails until a restart",
)
async def test_poll_recovers_after_link_drop(sim, device):
    await device.get_status()
    await sim.drop_connections()
    with pytest.raises(CommandError):
        await device.get_status()

    # What the HA coordinator does on its next poll.
    if not device.is_connected:
        await device.connect()
    status = await device.get_status()
    assert status.power == "On"


# -- Broadcast replies and corrupted STATUS ----------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="Every reply is broadcast to every client, so a reader takes "
    "another client's reply that lands first as its own",
)
async def test_foreign_reply_is_not_taken_as_ours(sim, device):
    sim.interleave_foreign("TEMP")
    assert await device.execute_command("uptime") == RECORDED_UPTIME


@pytest.mark.xfail(
    strict=True,
    reason="A STATUS dump with binary frames mixed in and bytes missing is "
    "parsed as valid instead of being rejected",
)
async def test_corrupted_status_is_rejected(sim, device):
    sim.corrupt_next_status()
    with pytest.raises(CommandError):
        await device.get_status()


@pytest.mark.xfail(
    strict=True,
    reason="DMP168Parser.parse_status accepts the corrupted STATUS capture",
)
def test_dmp168_parser_rejects_corrupted_status():
    with pytest.raises(ParseError):
        DMP168Parser.parse_status(corrupted_status().decode("utf-8", "replace"))


@pytest.mark.xfail(
    strict=True,
    reason="status_parser.parse accepts the corrupted STATUS capture",
)
def test_status_parser_rejects_corrupted_status():
    with pytest.raises(ParseError):
        status_parser.parse(corrupted_status().decode("utf-8", "replace"))


# -- Quirks the library already copes with -----------------------------------


async def test_banner_from_a_port_23_peer_does_not_break_the_next_reply(sim, device):
    """The banner reaches port 8000 clients too; it must not frame as a reply."""
    _, peer = await asyncio.open_connection(sim.host, sim.telnet_port)
    await asyncio.sleep(0.1)
    try:
        assert await device.execute_command("uptime") == RECORDED_UPTIME
    finally:
        peer.close()


async def test_silent_device_times_out(sim, device):
    sim.silent = True
    with pytest.raises(CommandError, match="No matching line"):
        await device.send_command("UPTIME", timeout=0.2)
