"""Tests for the Blustream MAC-mismatch repair issue + fix flow."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.components.repairs import (  # noqa: E402
    DOMAIN as REPAIRS_DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.helpers import issue_registry as ir  # noqa: E402
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo  # noqa: E402
from homeassistant.setup import async_setup_component  # noqa: E402
from pytest_homeassistant_custom_component.common import (  # noqa: E402
    MockConfigEntry,
    mock_component,
)

from custom_components.blustream.const import DOMAIN  # noqa: E402
from custom_components.blustream.repairs import (  # noqa: E402
    _mac_mismatch_issue_id,
)

# ---------------------------------------------------------------------------
# DHCP trigger
# ---------------------------------------------------------------------------


async def test_dhcp_different_mac_for_existing_host_raises_repair_issue(
    hass: HomeAssistant,
) -> None:
    """A DHCP-discovered MAC differing from a stored MAC at the same host
    raises a fixable repair issue and does NOT rewrite the entry's
    ``unique_id`` (ADR 0010 -- no automatic identity upgrades)."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 23,
            CONF_MAC: "34:d0:b8:21:22:33",
        },
        unique_id="34:d0:b8:21:22:33",
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.0.2.10",
            hostname="dmp168",
            macaddress="34d0b8aabbcc",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mac_mismatch"
    # Stored identity untouched.
    assert existing.unique_id == "34:d0:b8:21:22:33"
    assert existing.data[CONF_MAC] == "34:d0:b8:21:22:33"
    assert existing.data[CONF_HOST] == "192.0.2.10"

    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue(DOMAIN, _mac_mismatch_issue_id(existing.entry_id))
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.translation_key == "mac_mismatch"
    assert issue.translation_placeholders == {
        "stored_mac": "34:d0:b8:21:22:33",
        "discovered_mac": "34:d0:b8:aa:bb:cc",
    }


async def test_dhcp_for_tier3_entry_at_same_host_raises_repair_issue(
    hass: HomeAssistant,
) -> None:
    """A Tier-3 (manual, no-MAC / entry-id identity) entry at this host
    must not be silently overridden by a later DHCP discovery (user
    story 16). The mismatch surfaces as a fixable repair issue."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 23,
        },
        unique_id=None,
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.0.2.10",
            hostname="dmp168",
            macaddress="34d0b8aabbcc",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mac_mismatch"
    assert existing.unique_id is None
    assert CONF_MAC not in existing.data

    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue(DOMAIN, _mac_mismatch_issue_id(existing.entry_id))
    assert issue is not None
    assert issue.translation_placeholders == {
        "stored_mac": "—",
        "discovered_mac": "34:d0:b8:aa:bb:cc",
    }


async def test_dhcp_same_mac_does_not_raise_issue(
    hass: HomeAssistant,
) -> None:
    """Regression: a DHCP-rediscovery with the same MAC must keep going
    through the silent IP-change update path -- not raise an issue."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 23,
            CONF_MAC: "34:d0:b8:21:22:33",
        },
        unique_id="34:d0:b8:21:22:33",
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.0.2.99",
            hostname="dmp168",
            macaddress="34d0b8212233",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert existing.data[CONF_HOST] == "192.0.2.99"

    issue_reg = ir.async_get(hass)
    assert (
        issue_reg.async_get_issue(DOMAIN, _mac_mismatch_issue_id(existing.entry_id))
        is None
    )


# ---------------------------------------------------------------------------
# Reconfigure trigger
# ---------------------------------------------------------------------------


async def test_reconfigure_to_conflicting_mac_raises_repair_issue(
    hass: HomeAssistant,
) -> None:
    """Reconfiguring entry A to use entry B's MAC raises a repair issue
    instead of silently rebinding A's identity onto B's MAC."""
    entry_a = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 23,
            CONF_MAC: "34:d0:b8:21:22:33",
        },
        unique_id="34:d0:b8:21:22:33",
    )
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.20",
            CONF_PORT: 23,
            CONF_MAC: "34:d0:b8:aa:bb:cc",
        },
        unique_id="34:d0:b8:aa:bb:cc",
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)

    # The mac-mismatch abort fires before _validate_connectivity, so no
    # DMP168 patch is needed -- the flow never reaches the network step.
    result = await entry_a.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 23,
            CONF_MAC: "34:D0:B8:AA:BB:CC",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mac_mismatch"
    assert entry_a.unique_id == "34:d0:b8:21:22:33"
    assert entry_a.data[CONF_MAC] == "34:d0:b8:21:22:33"

    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue(DOMAIN, _mac_mismatch_issue_id(entry_a.entry_id))
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.translation_placeholders["discovered_mac"] == "34:d0:b8:aa:bb:cc"
    assert issue.translation_placeholders["stored_mac"] == "34:d0:b8:21:22:33"


# ---------------------------------------------------------------------------
# Fix flow resolution
# ---------------------------------------------------------------------------


async def _start_fix_flow(hass: HomeAssistant, issue_id: str):
    """Initialize a repairs fix flow for the given issue id.

    Marks the ``blustream`` domain as loaded (``mock_component``) so the
    repairs platform loader picks up ``custom_components/blustream/
    repairs.py`` and routes the issue to our flow instead of the
    fallback ``ConfirmRepairFlow``.
    """
    if DOMAIN not in hass.config.components:
        mock_component(hass, DOMAIN)
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {})
    flow_manager = hass.data[REPAIRS_DOMAIN]["flow_manager"]
    return await flow_manager.async_init(DOMAIN, data={"issue_id": issue_id})


async def test_fix_flow_confirm_replacement_updates_identity_and_clears_issue(
    hass: HomeAssistant,
    mock_device: MagicMock,  # noqa: ARG001  scheduled reload would otherwise hit the real DMP168
) -> None:
    """Choosing 'confirm replacement' adopts the new MAC as the entry's
    identity (unique_id + CONF_MAC), preserves entry_id (history), and
    clears the issue from the registry."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 23,
            CONF_MAC: "34:d0:b8:21:22:33",
        },
        unique_id="34:d0:b8:21:22:33",
    )
    existing.add_to_hass(hass)
    original_entry_id = existing.entry_id

    # Drive the DHCP trigger to create the issue.
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.0.2.10",
            hostname="dmp168",
            macaddress="34d0b8aabbcc",
        ),
    )

    issue_id = _mac_mismatch_issue_id(original_entry_id)
    result = await _start_fix_flow(hass, issue_id)
    assert result["type"] is FlowResultType.MENU
    assert "confirm_replacement" in result["menu_options"]
    assert "restore" in result["menu_options"]

    result = await hass.data[REPAIRS_DOMAIN]["flow_manager"].async_configure(
        result["flow_id"], {"next_step_id": "confirm_replacement"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Entry id (history) preserved; identity adopted from discovery.
    assert existing.entry_id == original_entry_id
    assert existing.unique_id == "34:d0:b8:aa:bb:cc"
    assert existing.data[CONF_MAC] == "34:d0:b8:aa:bb:cc"

    issue_reg = ir.async_get(hass)
    assert issue_reg.async_get_issue(DOMAIN, issue_id) is None


async def test_fix_flow_restore_keeps_identity_and_clears_issue(
    hass: HomeAssistant,
    mock_device: MagicMock,  # noqa: ARG001  parity with the replacement test
) -> None:
    """Choosing 'restore' clears the issue but leaves the stored
    identity untouched -- the new MAC is treated as transient."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 23,
            CONF_MAC: "34:d0:b8:21:22:33",
        },
        unique_id="34:d0:b8:21:22:33",
    )
    existing.add_to_hass(hass)
    original_entry_id = existing.entry_id

    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.0.2.10",
            hostname="dmp168",
            macaddress="34d0b8aabbcc",
        ),
    )

    issue_id = _mac_mismatch_issue_id(original_entry_id)
    result = await _start_fix_flow(hass, issue_id)
    result = await hass.data[REPAIRS_DOMAIN]["flow_manager"].async_configure(
        result["flow_id"], {"next_step_id": "restore"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert existing.entry_id == original_entry_id
    assert existing.unique_id == "34:d0:b8:21:22:33"
    assert existing.data[CONF_MAC] == "34:d0:b8:21:22:33"

    issue_reg = ir.async_get(hass)
    assert issue_reg.async_get_issue(DOMAIN, issue_id) is None
