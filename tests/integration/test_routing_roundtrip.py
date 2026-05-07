"""Routing round-trip against a live DMP168.

Issues a route command, polls STATUS, and asserts the change is observable.
Captures the prior routing for the test output and restores it on teardown
so re-running the suite is idempotent against the dealer's installed config.
"""

from __future__ import annotations

import pytest

from blustream.devices.dmp168.device import DMP168
from tests.integration._helpers import output_l_input

# Pick the highest output and input channels — least likely to collide with a
# room a homeowner is actually listening to during a test run. Adjust via
# environment if the live setup makes these unsafe.
TEST_OUTPUT = 8
TEST_INPUT = 16
ALT_INPUT = 15


@pytest.mark.asyncio
async def test_route_change_appears_in_status(device: DMP168) -> None:
    baseline = await device.execute_command("status")
    prior_input = output_l_input(baseline, TEST_OUTPUT)

    target_input = ALT_INPUT if prior_input == TEST_INPUT else TEST_INPUT

    await device.route_input_to_output(input_ch=target_input, output=TEST_OUTPUT)
    try:
        new_status = await device.execute_command("status")
        observed = output_l_input(new_status, TEST_OUTPUT)
        assert observed == target_input, (
            f"expected output {TEST_OUTPUT} to be routed from input "
            f"{target_input}; STATUS reported {observed}"
        )
    finally:
        if prior_input is not None and prior_input != target_input:
            await device.route_input_to_output(input_ch=prior_input, output=TEST_OUTPUT)
        elif prior_input is None:
            await device.remove_input_from_output(
                output=TEST_OUTPUT, input_ch=target_input
            )
