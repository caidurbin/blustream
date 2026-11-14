"""``DMP168.reboot()`` confirms the restart against the simulated DMP168 (#78)."""

from __future__ import annotations

import math
from datetime import timedelta

import pytest

from blustream.base.exceptions import (
    CommandError,
    RebootNotConfirmedError,
    TimeoutError,
)
from blustream.connection.tcp import TCPConnection
from blustream.devices.dmp168 import device as device_module
from blustream.devices.dmp168.device import DMP168

# Keeps connect() quick on port 8000, which sends no banner.
BANNER_TIMEOUT = 0.1

RECORDED_UPTIME = timedelta(days=149, hours=4, minutes=17, seconds=56)


@pytest.fixture(autouse=True)
def fast_polls(monkeypatch):
    monkeypatch.setattr(device_module, "REBOOT_POLL_INTERVAL", 0.01)


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


async def test_acknowledged_reboot_without_restart_raises(sim, device):
    # The simulator acknowledges REBOOT and keeps running, like firmware
    # MCU V1.5.0 on the live unit.
    with pytest.raises(RebootNotConfirmedError, match="did not restart"):
        await device.reboot(timeout=5)

    # It fails on the first check, without waiting out the window.
    assert sim.received == ["UPTIME", "REBOOT", "UPTIME"]
    assert device.is_connected
    assert await device.get_uptime() == RECORDED_UPTIME


async def test_reboot_not_confirmed_is_a_command_error(sim, device):
    with pytest.raises(CommandError):
        await device.reboot(timeout=5)


async def test_reboot_returns_once_the_device_is_back_with_uptime_reset(sim, device):
    sim.restart_on_reboot(downtime=0.2)

    await device.reboot(timeout=5)

    assert device.is_connected
    assert await device.get_uptime() < timedelta(seconds=5)
    assert (await device.get_status()).power == "On"


async def test_restart_that_drops_the_link_before_acknowledging_is_confirmed(
    sim, device
):
    sim.restart_on_reboot(downtime=0.2, acknowledge=False)

    await device.reboot(timeout=5)

    assert await device.get_uptime() < timedelta(seconds=5)


async def test_device_that_never_comes_back_times_out(sim, device):
    sim.restart_on_reboot(downtime=math.inf)

    with pytest.raises(TimeoutError, match="did not answer within 0.3 s"):
        await device.reboot(timeout=0.3)

    assert not device.is_connected


async def test_reboot_without_confirm_sends_only_reboot(sim, device):
    await device.reboot(confirm=False)

    assert sim.received == ["REBOOT"]


async def test_execute_command_reboot_confirms_the_restart(sim, device):
    with pytest.raises(RebootNotConfirmedError):
        await device.execute_command("reboot")

    sim.restart_on_reboot(downtime=0.1)
    assert await device.execute_command("reboot") is None
