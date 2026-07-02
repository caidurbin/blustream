---
applies_to: [ha-integration]
date: 2026-05-29
---

# HA integration: three identity sources, no automatic upgrades

The config-entry `unique_id` comes from one of three sources — a MAC discovered via DHCP (preferred), a user-entered MAC (fallback), or the config-entry id (last resort) — chosen at entry creation and **never silently rewritten** thereafter. The DMP168 exposes no programmatic identity over its TCP protocol (a live-hardware spike ruled out undocumented identity commands; `docs/dmp168-identity-spike.md` is the canonical record of the probe evidence), so identity must arrive from the network or the user.

**Discovered identity (preferred).** HA's `dhcp` discovery surface delivers the device MAC for anything matching the manifest's `dhcp: [{macaddress: "34D0B82*", registered_devices: true}]`. The 7-hex-digit prefix is required — the parent 24-bit OUI `34:D0:B8` is a shared IEEE MA-M block and would over-match (see `docs/dmp168-identity-spike.md` for the MA-M block analysis). `registered_devices: true` is required so HA dispatches DHCP callbacks to already-configured entries and IP changes update the host.

**Manual identity (fallback).** The user setup form includes an optional MAC field, with a pointer to the web GUI's Information page so users know where to read the MAC. Manual identity outranks discovered identity for the same entry — a later DHCP discovery does not overwrite it.

**Entry-id identity (last resort).** When neither DHCP discovery nor a user-entered MAC is available, the config-entry id is the `unique_id`, per HA's documented last-resort pattern (the same shape `minecraft_server` uses since PR #97837).

`zeroconf` discovery is declared in the manifest (`_http._tcp.local.` with `name: dmp168*`) as a **discovery-UX assist only**. The DMP168's factory-default mDNS hostname is the constant `DMP168.local` (user-renameable via the web GUI, never MAC-derived), and TXT records carry no identity, so zeroconf cannot supply a stable identifier. Two out-of-the-box units on one LAN collide on `dmp168.local` until renamed — and a renamed unit stops matching the `name: dmp168*` matcher — so mDNS is a find-the-IP assist, not identity. A zeroconf hit routes the user into the manual setup step, where the manual or entry-id path takes over.

## Consequences

- No automatic identity upgrades: once an entry's `unique_id` is set, it is rewritten only by explicit user action through the reconfiguration flow — never by the coordinator, never silently by a later DHCP discovery firing for the same host. HA's canonical stance is that manual identity outranks discovered identity, and silent rewrites hide configuration errors.
- A MAC mismatch on a previously-stable entry raises a fixable repair issue rather than auto-rewriting.
- Migration from entry-id to MAC-based identity is reconfigure-flow or delete-and-re-add; both preserve no entity history across the transition, which is honest given the integration cannot prove the post-migration device is the same physical unit.

## Considered Options

- `getmac` / ARP-cache resolution — explicitly disallowed by HA (PR #97837).
- Web-GUI HTML scraping for the MAC — a code-review smell in HA core and brittle to firmware UI changes.
- IP-as-unique-id — CI-blocked by a pylint plugin (PR #168822).
- A Blustream firmware feature request for a `NET MAC?` getter remains worth filing independently — if granted, that path becomes the canonical identity source (HA's preferred "MAC from device API") and supersedes the discovered/manual fallback chain; record that decision in a new ADR and mark this one `status: superseded by ADR-NNNN`.
