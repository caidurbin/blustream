---
applies_to: [ha-integration]
---

# HA integration: three identity sources, no automatic upgrades

The DMP168 exposes no programmatic identity over its TCP protocol — a live-hardware spike against firmware MCU 1.5.0 / Web 1.4.0 / DSP 1.5.9 ruled out 52 candidate undocumented commands (`docs/adr/draft-dmp168-identity-spike.md`). The integration constructs the config-entry `unique_id` from one of three sources, chosen at entry creation and **never silently rewritten** thereafter.

**Discovered identity (preferred).** HA's `dhcp` discovery surface delivers `DhcpServiceInfo.macaddress` for any device whose MAC matches Blustream's 28-bit IEEE MA-M prefix `34:D0:B8:2*`. The manifest declares `dhcp: [{macaddress: "34D0B82*", registered_devices: true}]`. The 7-hex-digit prefix is required — the parent 24-bit OUI `34:D0:B8` is a shared MA-M block and would over-match. `registered_devices: true` is required for HA to dispatch DHCP callbacks to already-configured entries so IP changes update `CONF_HOST` via `_abort_if_unique_id_configured(updates={CONF_HOST: ip})`. MAC is `format_mac`-normalized, used as `unique_id`, and placed in `connections={(CONNECTION_NETWORK_MAC, mac)}` on the device-registry entry for cross-integration device merging.

**Manual identity (fallback).** `async_step_user` includes an optional MAC field; if filled, the value is `format_mac`-normalized and used as `unique_id`. The form description points to the web GUI's Information page so users know where to read the MAC. Manual identity outranks discovered identity for the same entry — a later DHCP discovery does not overwrite it.

**Entry-id identity (last resort).** When neither DHCP discovery nor a user-entered MAC is available, `config_entry.entry_id` is the `unique_id`, per HA's documented last-resort pattern (the same shape `minecraft_server` uses since PR #97837).

`zeroconf` discovery is declared in the manifest (`_http._tcp.local.` with `name: dmp168*`) as a **discovery-UX assist only**. The DMP168's mDNS hostname is fixed (`DMP168.local`, not MAC-derived) and TXT records carry no identity, so zeroconf cannot supply a stable identifier. A zeroconf hit routes the user into `async_step_user`, where the manual or entry-id path takes over.

**No automatic identity upgrades.** Once an entry's `unique_id` is set, it is rewritten only by explicit user action through the reconfiguration flow — never by the coordinator, never silently by a later DHCP discovery firing for the same host. A MAC mismatch on a previously-stable entry raises a fixable repair issue (`homeassistant.helpers.issue_registry.async_create_issue(is_fixable=True)`) rather than auto-rewriting. Rationale: HA's canonical stance is that manual identity outranks discovered identity, and silent rewrites hide configuration errors. Migration is gated on explicit user intent. Should a user need to migrate from entry-id to MAC-based identity, the path is reconfigure-flow or delete-and-re-add — both well-understood by HA users and both preserve no entity history across the transition, which is honest given the integration cannot prove the post-migration device is the same physical unit.

**Rejected alternatives.** `getmac` / ARP-cache resolution is explicitly disallowed by HA (PR #97837); web-GUI HTML scraping for the MAC is a code-review smell in HA core and brittle to firmware UI changes; IP-as-unique-id is CI-blocked by a pylint plugin (PR #168822). A Blustream firmware feature request for a `NET MAC?` getter remains worth filing independently — if granted, that path becomes the canonical identity source (HA's preferred "MAC from device API") and supersedes the discovered/manual fallback chain in a future revision of this ADR.
