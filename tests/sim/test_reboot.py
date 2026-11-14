"""``DMP168.reboot()`` confirms the restart against the simulated DMP168 (#78)."""

from __future__ import annotations

import math
import time
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


async def test_short_uptime_without_restart_raises(sim, device, monkeypatch):
    # A device up for only 3 s that keeps running reads about 3 s plus the
    # time since the press, which is no restart.
    monkeypatch.setattr(device_module, "REBOOT_GRACE", 0.1)
    sim.set_uptime(3)

    with pytest.raises(RebootNotConfirmedError, match="did not restart"):
        await device.reboot(timeout=5)

    assert device.is_connected


async def test_restart_from_a_short_uptime_is_confirmed(sim, device, monkeypatch):
    # Up for 3 s at the press; the restart and the boot take 10 s, and the
    # device comes back reporting 8 s, higher than before but well below the
    # 13 s a device that kept running would show. The clock jumps those 10 s
    # once the device has received REBOOT, instead of sleeping them.
    monkeypatch.setattr(
        device_module,
        "monotonic",
        lambda: time.monotonic() + (10 if "REBOOT" in sim.received else 0),
    )
    sim.set_uptime(3)
    sim.restart_on_reboot(downtime=0.05, uptime=8)

    await device.reboot(timeout=60)

    assert await device.get_uptime() > timedelta(seconds=3)


async def test_slow_uptime_reply_from_a_running_device_raises(sim, device, monkeypatch):
    # The device samples its uptime when UPTIME arrives, and the reply takes
    # 10 s to come back. The latency must not pass for a restart.
    monkeypatch.setattr(
        device_module,
        "monotonic",
        lambda: time.monotonic() + (10 if sim.received.count("UPTIME") > 1 else 0),
    )

    with pytest.raises(RebootNotConfirmedError, match="did not restart"):
        await device.reboot(timeout=60)


async def test_running_uptime_within_the_grace_keeps_checking(sim, device, monkeypatch):
    # A grace 30 times the poll interval leaves room for slow checks.
    monkeypatch.setattr(device_module, "REBOOT_GRACE", 0.3)

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


async def test_running_uptime_at_the_deadline_is_not_a_timeout(
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
