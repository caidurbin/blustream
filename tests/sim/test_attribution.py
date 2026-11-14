"""#109: our reply is found among the replies the device broadcasts.

The DMP168 sends every client's replies to every connected client. Each test
runs on the telnet port, where our reply starts at our own echo, and on the
raw port, where only the reply's shape identifies it. Writes on the raw port
have no shape: those tests pin today's best-effort behaviour and name the
limit.
"""

from __future__ import annotations

import asyncio

import pytest

from blustream.base.exceptions import CommandError
from blustream.connection.tcp import TCPConnection
from blustream.devices.dmp168 import device as device_module
from blustream.devices.dmp168.device import DMP168
from tests.sim.matrix import recording

# Long enough for the telnet port's negotiation and banner. Port 8000 sends
# neither, so its connect does not wait.
BANNER_TIMEOUT = 0.1
# Response budget for the tests where a reply is meant never to come.
QUICK_TIMEOUT = 0.3

RECORDED_UPTIME = "0149:04:17:56"
RECORDED_TEMP = "38.1C"
HELP_TITLE = "DMP168 Help Info"

UNATTRIBUTED = "may belong to another client"


@pytest.fixture
def echoing(sim, port) -> bool:
    return port == sim.telnet_port


@pytest.fixture
async def device(sim, port):
    """The shared device, with no banner wait on port 8000, which sends none."""
    banner_timeout = BANNER_TIMEOUT if port == sim.telnet_port else 0
    connection = TCPConnection(sim.host, port, banner_timeout=banner_timeout)
    dmp = DMP168(sim.host, port, connection=connection)
    await dmp.connect()
    yield dmp
    await dmp.disconnect()


@pytest.fixture
def quick(device, monkeypatch):
    """The device with a short response budget, for replies that never come."""
    monkeypatch.setattr(device, "_response_timeout", QUICK_TIMEOUT)
    monkeypatch.setattr(device_module, "STATUS_RESPONSE_TIMEOUT", QUICK_TIMEOUT)
    return device


@pytest.fixture
async def baseline_status(device):
    return await device.get_status()


def _status_cut_at_line_end() -> int:
    """A length that ends a STATUS dump about half way, after a whole line."""
    dump = recording("p8000_A_STATUS_2.bin")
    return dump.rfind(b"\r\n", 0, len(dump) // 2) + 2


# Ten bytes short of the footer: the dump ends inside its "=" rule, with no
# line end, as the live unit's torn dump did.
STATUS_CUT_IN_FOOTER = len(recording("p8000_A_STATUS_2.bin")) - 10


async def test_echo_mode_follows_the_telnet_negotiation(device, echoing):
    """The simulator's telnet port is not 23, so only SGA can tell."""
    assert device._connection.echoes_commands is echoing


# -- Another client's reply lands just before ours ---------------------------


@pytest.mark.parametrize(
    "foreign", ["TEMP", "STATUS", "HELP", "UPTIME", "PON", "FOO", "PRESET 9 STATUS"]
)
async def test_foreign_reply_ahead_of_our_uptime(sim, device, foreign):
    sim.interleave_foreign(foreign)
    assert await device.get_uptime_raw() == RECORDED_UPTIME


@pytest.mark.parametrize("foreign", ["UPTIME", "STATUS", "FOO"])
async def test_foreign_reply_ahead_of_our_temp(sim, device, foreign):
    sim.interleave_foreign(foreign)
    assert await device.get_temperature() == RECORDED_TEMP


@pytest.mark.parametrize("foreign", ["TEMP", "STATUS", "HELP", "PON", "FOO"])
async def test_foreign_reply_ahead_of_our_status(sim, device, baseline_status, foreign):
    sim.interleave_foreign(foreign)
    assert await device.get_status() == baseline_status


def _listing(help_text: str) -> str:
    """The HELP listing from its title on; what precedes it is our echo."""
    return help_text[help_text.index(HELP_TITLE) :]


@pytest.mark.parametrize("foreign", ["STATUS", "HELP", "UPTIME", "FOO"])
async def test_foreign_reply_ahead_of_our_help(sim, device, echoing, foreign):
    baseline = await device.get_help()
    sim.interleave_foreign(foreign)
    help_text = await device.get_help()
    assert _listing(help_text) == _listing(baseline)
    first_line = help_text.partition("\r\n")[0]
    if echoing:
        assert first_line.endswith("HELP")
    else:
        assert HELP_TITLE in first_line


async def test_foreign_success_ahead_of_our_write(sim, device):
    # On port 8000 this passes on the foreign [SUCCESS], not ours (the limit
    # named in test_foreign_success_ahead_of_our_rejected_write); our own
    # [SUCCESS] is left for the next send's drain.
    sim.interleave_foreign("PON")
    await device.set_output_mute(8, True)


async def test_foreign_error_ahead_of_our_write(sim, device, echoing):
    sim.interleave_foreign("FOO")
    if echoing:
        await device.set_output_mute(8, True)
    else:
        # Limit: a raw-port write has no reply shape, so the first marker
        # line ends the read, whoever it came from.
        with pytest.raises(CommandError, match=UNATTRIBUTED):
            await device.set_output_mute(8, True)


async def test_foreign_success_ahead_of_our_rejected_write(sim, device, echoing):
    sim.interleave_foreign("PON")
    sim.reject_next()
    if echoing:
        with pytest.raises(CommandError, match="Command not found"):
            await device.set_output_mute(8, True)
    else:
        # Limit: the foreign [SUCCESS] is taken as ours and our [ERROR] is
        # dropped by the next send's drain.
        await device.set_output_mute(8, True)


async def test_rejected_uptime_raises_on_port_23_and_times_out_on_port_8000(
    sim, quick, echoing
):
    """After our echo an [ERROR] is ours; on the raw port nothing marks it ours."""
    sim.reject_next()
    if echoing:
        with pytest.raises(CommandError, match="Command not found"):
            await quick.get_uptime_raw()
    else:
        with pytest.raises(CommandError, match="No matching line"):
            await quick.get_uptime_raw()


# -- Another client's reply arrived while we were idle ------------------------


@pytest.mark.parametrize("foreign", ["TEMP", "STATUS", "FOO"])
async def test_foreign_reply_while_idle_is_not_taken_as_ours(sim, device, foreign):
    await sim.broadcast_foreign(foreign)
    await asyncio.sleep(0.05)
    assert await device.get_uptime_raw() == RECORDED_UPTIME


async def test_foreign_error_while_idle_does_not_fail_our_write(sim, device):
    await sim.broadcast_foreign("FOO")
    await asyncio.sleep(0.05)
    await device.set_output_mute(8, True)


# -- A foreign dump torn part way ----------------------------------------------


async def test_torn_foreign_status_ahead_of_our_status(
    request, sim, device, echoing, baseline_status
):
    if not echoing:
        request.applymarker(
            pytest.mark.xfail(
                strict=True,
                reason="On port 8000 the torn dump armed the STATUS terminator, "
                "and our dump's top = rule ends the read one line before our "
                "title can restart it, so the torn dump is returned",
            )
        )
    sim.interleave_torn("STATUS", _status_cut_at_line_end())
    assert await device.get_status() == baseline_status


async def test_torn_foreign_status_ahead_of_our_uptime(sim, device):
    sim.interleave_torn("STATUS", _status_cut_at_line_end())
    assert await device.get_uptime_raw() == RECORDED_UPTIME


async def test_our_echo_glued_to_a_torn_line(sim, device):
    """The torn rule and our echo share a line: ``=======UPTIME``."""
    sim.interleave_torn("STATUS", STATUS_CUT_IN_FOOTER)
    assert await device.get_uptime_raw() == RECORDED_UPTIME


async def test_our_status_echo_glued_to_a_torn_line(sim, device, baseline_status):
    sim.interleave_torn("STATUS", STATUS_CUT_IN_FOOTER)
    assert await device.get_status() == baseline_status


# -- A reply that stalls --------------------------------------------------------


async def test_late_reply_is_not_taken_as_the_next_commands(sim, quick, echoing):
    """A write times out; its [ERROR] arrives while the next write is in flight."""
    sim.reject_next()
    sim.stall_next_reply()
    with pytest.raises(CommandError, match="No matching line"):
        await quick.set_output_mute(8, True)

    if echoing:
        # The late [ERROR] arrives before our echo, so it is skipped.
        await quick.set_output_mute(8, False)
    else:
        # Limit: on the raw port the late [ERROR] ends the next write's read.
        with pytest.raises(CommandError, match=UNATTRIBUTED):
            await quick.set_output_mute(8, False)


async def test_stalled_status_dump_arriving_during_our_query(
    sim, quick, baseline_status
):
    """Our STATUS times out; its dump then lands while UPTIME is in flight."""
    sim.stall_next_reply()
    with pytest.raises(CommandError, match="No matching line"):
        await quick.get_status()

    assert await quick.get_uptime_raw() == RECORDED_UPTIME
    assert await quick.get_status() == baseline_status


async def test_late_reply_ahead_of_our_query(sim, quick):
    sim.reject_next()
    sim.stall_next_reply()
    with pytest.raises(CommandError, match="No matching line"):
        await quick.set_output_mute(8, True)

    assert await quick.get_uptime_raw() == RECORDED_UPTIME


async def test_echo_less_stall_times_out(sim, quick):
    """Only an earlier stalled reply arrives after our command: no echo, no reply."""
    sim.reject_next()
    sim.stall_next_reply(replace_following=True)
    with pytest.raises(CommandError, match="No matching line"):
        await quick.set_output_mute(8, True)

    with pytest.raises(CommandError, match="No matching line"):
        await quick.get_uptime_raw()
    assert await quick.get_uptime_raw() == RECORDED_UPTIME
