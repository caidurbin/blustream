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
from blustream.devices.dmp168 import device as device_module

RECORDED_UPTIME = timedelta(days=149, hours=4, minutes=17, seconds=56)


@pytest.fixture(autouse=True)
def fast_polls(monkeypatch):
    monkeypatch.setattr(device_module, "REBOOT_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(device_module, "REBOOT_GRACE", 0)


async def test_acknowledged_reboot_without_restart_raises(sim, device):
    # The simulator acknowledges REBOOT and keeps running, like firmware
    # MCU V1.5.0 on the live unit.
    with pytest.raises(RebootNotConfirmedError, match="did not restart") as exc_info:
        await device.reboot(timeout=5)
    assert isinstance(exc_info.value, CommandError)

    # It fails on the first check, without waiting out the window.
    assert sim.received == ["UPTIME", "REBOOT", "UPTIME"]
    assert device.is_connected
    assert await device.get_uptime() == RECORDED_UPTIME


async def test_unreset_uptime_within_the_grace_keeps_checking(sim, device, monkeypatch):
    monkeypatch.setattr(device_module, "REBOOT_GRACE", 0.1)

    with pytest.raises(RebootNotConfirmedError):
        await device.reboot(timeout=5)

    assert sim.received[:2] == ["UPTIME", "REBOOT"]
    assert sim.received.count("UPTIME") > 2


async def test_restart_shortly_after_the_acknowledgement_is_confirmed(
    sim, device, monkeypatch
):
    # The device still answers with its old uptime for a moment after REBOOT,
    # then restarts within the grace.
    monkeypatch.setattr(device_module, "REBOOT_GRACE", 5)
    sim.restart_on_reboot(downtime=0.05, delay=0.1)

    await device.reboot(timeout=5)

    assert sim.received.count("UPTIME") > 2
    assert await device.get_uptime() < timedelta(seconds=5)


async def test_unreset_uptime_at_the_deadline_is_not_a_timeout(
    sim, device, monkeypatch
):
    monkeypatch.setattr(device_module, "REBOOT_GRACE", 60)

    with pytest.raises(RebootNotConfirmedError):
        await device.reboot(timeout=0.05)


async def test_reboot_returns_once_the_device_is_back_with_uptime_reset(sim, device):
    sim.restart_on_reboot(downtime=0.05)

    await device.reboot(timeout=5)

    assert device.is_connected
    assert await device.get_uptime() < timedelta(seconds=5)
    assert (await device.get_status()).power == "On"


async def test_restart_that_drops_the_link_before_acknowledging_is_confirmed(
    sim, device
):
    sim.restart_on_reboot(downtime=0.05, acknowledge=False)

    await device.reboot(timeout=5)

    assert await device.get_uptime() < timedelta(seconds=5)


async def test_device_that_never_comes_back_times_out(sim, device):
    sim.restart_on_reboot(downtime=math.inf)

    with pytest.raises(TimeoutError, match="did not report its uptime within 0.1 s"):
        await device.reboot(timeout=0.1)

    assert not device.is_connected


async def test_reboot_without_confirm_sends_only_reboot(sim, device):
    await device.reboot(confirm=False)

    assert sim.received == ["REBOOT"]


async def test_execute_command_reboot_confirms_the_restart(sim, device):
    with pytest.raises(RebootNotConfirmedError):
        await device.execute_command("reboot")

    sim.restart_on_reboot(downtime=0.05)
    assert await device.execute_command("reboot") is None
