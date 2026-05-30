# Blustream Home Assistant integration

The Blustream integration adds the [Blustream DMP168](https://www.blustream.co.uk/) digital
audio matrix processor as a device in Home Assistant. The v0.1 release ships a single
`SensorDeviceClass.UPTIME` entity that reports when the device last booted, rendered
by HA as relative time ("3 days ago"). It depends on the
[`blustream`](https://pypi.org/project/blustream/) PyPI library for the wire protocol
(ADR 0011 — the library owns the protocol boundary).

The integration targets HA's [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
**Gold** tier from v0.1 (ADR 0009). Surfaces are built to that standard from the start so
that later slices — discovery, reconfigure, repair, diagnostics, more entities — are
purely additive.

## Installation (HACS)

1. In Home Assistant, open **HACS → Integrations**.
2. Click the kebab menu → **Custom repositories**, add
   `https://github.com/caidurbin/blustream` with category **Integration**.
3. Install **Blustream Audio Matrix** from the HACS integrations list.
4. Restart Home Assistant.

## Configuration

1. Open **Settings → Devices & Services → Add Integration** and choose **Blustream Audio
   Matrix**.
2. Enter the device's **Host** (IP address or hostname) and **Port** (defaults to `23`,
   the DMP168's telnet port).
3. Optionally enter a **Name** to override the entry title.
4. Optionally enter the device's **MAC address** (visible on the DMP168 web GUI's
   *Information* page). Supplying a MAC gives the device a stable identity that survives
   IP changes; without it the integration falls back to the config entry's internal id
   (ADR 0010).

The integration verifies connectivity before creating the entry. If it can't reach the
device you'll see a `cannot_connect` error; an ill-formed MAC reports `invalid_mac`.

## Entities

| Entity   | Class                       | Description                              |
| -------- | --------------------------- | ---------------------------------------- |
| Uptime   | `SensorDeviceClass.UPTIME`  | Boot time of the DMP168 (relative time). |

The sensor reports **Unavailable** when the device is unreachable and recovers within
one polling cycle (~30 s) once the device returns. HA logs "device unavailable" /
"device recovered" once per transition.

## Networking caveats

Discovery via DHCP and zeroconf lands in later slices. Until then, manual setup is the
only entry point. In Docker Desktop on macOS or Windows neither discovery path is
reliable anyway — HA in those environments lives behind a NAT'd Linux VM that doesn't
see DHCP broadcast traffic or have automatic Bonjour passthrough. Manual setup works
everywhere.

## Removing the integration

**Settings → Devices & Services → Blustream Audio Matrix → kebab menu → Delete**.
Removing the integration cleans up the device-registry and entity-registry entries.
The integration is intentionally 1:1 (one config entry per physical device), so HA's
device-level **Delete Device** button is hidden — there is nothing to delete short of
removing the integration itself (ADR 0012).

## Status

| Surface              | v0.1                            | Later                           |
| -------------------- | ------------------------------- | ------------------------------- |
| Manual setup         | ✅                              | —                               |
| Uptime sensor        | ✅                              | —                               |
| DHCP discovery       | Manifest only (matcher unused)  | Discovery slice                 |
| Zeroconf discovery   | Manifest only (matcher unused)  | Discovery slice                 |
| Reconfigure flow     | —                               | Reconfigure slice               |
| MAC-mismatch repair  | —                               | Reconfigure slice               |
| Diagnostics          | —                               | Diagnostics slice               |
| Volume / mute / routing entities | —                   | v0.2+                           |

## Context

- Parent PRD: [issue #28](https://github.com/caidurbin/blustream/issues/28).
- Skeleton slice: [issue #31](https://github.com/caidurbin/blustream/issues/31).
- ADRs: [0009](../../docs/adr/0009-ha-integration-gold-tier-from-v0.1.md),
  [0010](../../docs/adr/0010-ha-integration-device-identity.md),
  [0011](../../docs/adr/0011-ha-integration-library-is-protocol-boundary.md),
  [0012](../../docs/adr/0012-ha-integration-gold-tier-operationalization.md).
