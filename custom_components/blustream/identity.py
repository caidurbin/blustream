"""Identity-source resolution for the Blustream integration.

Per ADR 0010, a config entry's ``unique_id`` is chosen from one of three
sources at entry-creation time and never silently rewritten:

* **Discovered** (DHCP) -- ``format_mac(mac)`` from the DHCP service info.
* **Manual** -- user-entered MAC, also ``format_mac``-normalized.
* **Entry-id** -- ``config_entry.entry_id`` as last-resort fallback.

Both the discovered and manual tiers normalize through ``format_mac``, so
``resolve_identity`` covers both -- the caller hands in whichever MAC it
has (DHCP-supplied or user-entered) and the discriminator is the source,
not the resolver. The DHCP source lives in ``config_flow.async_step_dhcp``;
the manual source lives in ``config_flow.async_step_user``.
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import format_mac


def resolve_identity(mac: str | None, entry_id: str) -> str:
    """Return the unique_id for an entry given the resolvable inputs.

    Args:
        mac: A well-formed MAC string (any common separator) or ``None``
            if no MAC was supplied.
        entry_id: The config entry's ``entry_id``, used when ``mac`` is
            ``None``.

    Returns:
        ``format_mac(mac)`` if ``mac`` is non-empty, else ``entry_id``.
    """
    if mac:
        return format_mac(mac)
    return entry_id
