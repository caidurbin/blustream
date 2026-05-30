"""Identity-source resolution for the Blustream integration.

Per ADR 0010, a config entry's ``unique_id`` is chosen from one of three
sources at entry-creation time and never silently rewritten:

* **Discovered** (DHCP) -- ``format_mac(mac)`` from the DHCP service info.
* **Manual** -- user-entered MAC, also ``format_mac``-normalized.
* **Entry-id** -- ``config_entry.entry_id`` as last-resort fallback.

v0.1 implements the manual and entry-id tiers only; the DHCP path lands
with the discovery slice.
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
