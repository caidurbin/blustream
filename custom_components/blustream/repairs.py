"""Repair flows for the Blustream integration.

Implements the MAC-mismatch repair issue path called out in ADR 0010:
identity is never silently rewritten -- when the DHCP discovery surface or
the reconfigure form observes a MAC that disagrees with the entry's
stored identity, ``config_flow.py`` raises a fixable issue here, and the
user resolves it through either "confirm replacement" (adopt the new MAC
on the existing entry, preserving entry_id / entity history) or "restore"
(treat the observed MAC as transient and keep the stored identity).
"""

from __future__ import annotations

from typing import Any

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


def _mac_mismatch_issue_id(entry_id: str) -> str:
    """Per-entry issue id so multiple entries can each carry one."""
    return f"mac_mismatch_{entry_id}"


@callback
def async_create_mac_mismatch_issue(
    hass: HomeAssistant,
    entry_id: str,
    *,
    stored_mac: str | None,
    discovered_mac: str,
) -> None:
    """Surface a fixable MAC-mismatch repair issue for ``entry_id``.

    ``stored_mac`` is the entry's currently configured MAC; ``None`` for
    a Tier-3 (entry-id identity) entry. ``discovered_mac`` is the
    ``format_mac``-normalized MAC just observed by DHCP / typed into the
    reconfigure form.
    """
    ir.async_create_issue(
        hass=hass,
        domain=DOMAIN,
        issue_id=_mac_mismatch_issue_id(entry_id),
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="mac_mismatch",
        translation_placeholders={
            "stored_mac": stored_mac or "—",
            "discovered_mac": discovered_mac,
        },
        data={
            "entry_id": entry_id,
            "stored_mac": stored_mac,
            "discovered_mac": discovered_mac,
        },
    )


class MacMismatchRepairFlow(RepairsFlow):
    """Two-choice repair flow: confirm device replacement, or restore."""

    def __init__(
        self,
        entry_id: str,
        stored_mac: str | None,
        discovered_mac: str,
    ) -> None:
        super().__init__()
        self._entry_id = entry_id
        self._stored_mac = stored_mac
        self._discovered_mac = discovered_mac

    @property
    def _placeholders(self) -> dict[str, str]:
        return {
            "stored_mac": self._stored_mac or "—",
            "discovered_mac": self._discovered_mac,
        }

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["confirm_replacement", "restore"],
            description_placeholders=self._placeholders,
        )

    async def async_step_confirm_replacement(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Adopt the discovered MAC as the entry's identity in place.

        Updates ``unique_id`` and ``CONF_MAC`` on the existing entry --
        ``entry_id`` (and therefore entity history) is preserved. The
        entry is reloaded so the coordinator picks up the new identity.
        """
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is not None:
            new_data = {**entry.data, CONF_MAC: self._discovered_mac}
            self.hass.config_entries.async_update_entry(
                entry, data=new_data, unique_id=self._discovered_mac
            )
            self.hass.config_entries.async_schedule_reload(self._entry_id)
        return self.async_create_entry(data={})

    async def async_step_restore(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Keep the stored identity; treat the observed MAC as transient.

        Returning ``async_create_entry`` triggers the repairs flow
        manager to delete the issue from the registry.
        """
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,  # noqa: ARG001
    issue_id: str,  # noqa: ARG001
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Build the per-issue fix flow from the issue's stashed ``data``.

    Called by HA's repairs platform loader when the user clicks "Fix" on
    a ``blustream`` issue.
    """
    assert data is not None
    entry_id = data["entry_id"]
    assert isinstance(entry_id, str)
    discovered_mac = data["discovered_mac"]
    assert isinstance(discovered_mac, str)
    stored_mac = data.get("stored_mac")
    assert stored_mac is None or isinstance(stored_mac, str)
    return MacMismatchRepairFlow(
        entry_id=entry_id,
        stored_mac=stored_mac,
        discovered_mac=discovered_mac,
    )
