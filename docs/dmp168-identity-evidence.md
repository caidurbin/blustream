---
applies_to: [ha-integration]
status: evidence record for ADR-0010
---

# DMP168 identity discovery: probe evidence

Empirical evidence base for [ADR 0010](adr/0010-ha-integration-device-identity.md), which rejects ARP lookup, adds an optional manual-MAC field, and drops the hostname dhcp matcher. Question answered: can a stable hardware identifier (MAC / serial / hostname) be read from a DMP168 over the network? Findings apply to firmware **MCU V1.5.0 / Web V1.4.0 / DSP V1.5.9**.

## Summary

**No undocumented in-band identity command exists.** Every plausible MAC / serial / hostname getter returned `[ERROR]Command not found.` or was greedy-parsed as a malformed write. Identity therefore has to arrive out-of-band: HA `dhcp` discovery keyed on the Blustream MA-M OUI prefix `34:D0:B8:2*`, plus `zeroconf` discovery on the fixed mDNS hostname `DMP168.local`. HA hands the MAC to the config flow at discovery time, so the integration never needs to query the device for identity.

## In-band command probe

Method: one fresh raw-TCP connection to port 8000 per command, send `<CMD>\r\n`, read up to ~1.2 s, classify by `[SUCCESS]` / `[ERROR]` markers.

### Banner / HELP capture

- **Port 23 (telnet) banner** is `Welcome to DMP168 Terminal Control System\r\nFW Version: 1.5.0` — no MAC, no serial, no per-unit identifier.
- **Port 8000 (raw TCP) banner** is empty (0 bytes) — confirms the existing `TCPConnection._discard_initial_data` behaviour.
- **`HELP`** output on port 8000 matches Blustream's published DMP168 API reference byte-for-byte aside from minor typo fixes ("Stanndby" → "Standby") and one new EQ command (`IN/OUT xx EQ vv PRESET yy`). **No identity-related command appears anywhere in HELP** that is missing from the vendor docs.

### Probe table

| Command | Verdict | Response |
|---|---|---|
| `NET MAC?` | ERROR | `[ERROR]NET MAC unknow param. Type "HELP" for more reference.` |
| `NET MAC` | ERROR | `[ERROR]NET MAC unknow param. ...` |
| `MAC?` / `MAC` | ERROR | `[ERROR]Command not found.` |
| `?MAC` | OTHER | full HELP banner (`?` is the documented help shortcut) |
| `INFO` / `INFO?` | ERROR | `[ERROR]IN unknow param.` (greedy-parsed as the `IN` input command) |
| `DEV INFO` / `DEVICE INFO` | ERROR | `[ERROR]Command not found.` |
| `SYS INFO` / `SYSINFO` | ERROR | `[ERROR]Command not found.` |
| `NET INFO` / `NET STATUS` / `NET ?` / `NET?` | ERROR | `[ERROR]NET unknow param.` |
| `IFCONFIG` / `IPCONFIG` | ERROR | `[ERROR]Command not found.` |
| `SERIAL` / `SERIAL?` / `SN` / `SN?` / `?SN` | ERROR / OTHER | `[ERROR]Command not found.` (`?SN` returned HELP banner) |
| `ID` / `ID?` / `?ID` | ERROR / OTHER | `[ERROR]Command not found.` (`?ID` returned HELP) |
| `HOSTNAME` / `HOSTNAME?` | ERROR | `[ERROR]Command not found.` |
| `HELP NET` / `HELP MAC` / `HELP INFO` / `HELP` | OTHER | full HELP banner (no per-subcommand help; trailing args ignored) |
| `LIST` / `VERSION` / `GETMAC` / `GETSERIAL` | ERROR | `[ERROR]Command not found.` |
| `MODEL` / `MODEL?` / `FW` / `FW?` / `FW VER` / `FIRMWARE` / `FIRMWARE?` | ERROR | `[ERROR]Command not found.` |
| `NET IP?` / `NET DHCP?` / `NET DHCP` / `NET GW?` / `NET SM?` / `NET TCPPORT?` / `NET TN?` | ERROR | `[ERROR]NET <subcmd> unknow param.` |
| `NET DNS?` | **SUCCESS (side effect)** | `[SUCCESS]Set DNS name to ?.` |

**Parser behaviour.** The CLI is greedy and left-to-right: `INFO` matches the `IN` command and `FO` becomes a bad parameter. `NET DNS?` is parsed as `NET DNS <arg=?>` (a write), not as a getter. There is no read-form syntax (`?` suffix is not a getter). No command echoed input; no hangs.

**Warning — `NET DNS?` is a destructive write.** It overwrites the DNS-name field with the literal string `?`. The device has no DNS getter, so an overwritten value cannot be recovered in-band; the field is unused by the control protocol — the device reaches the network by IP only. Reset with `NET DNS dmp168`.

**Verdict: no in-band identity command is reachable.**

## mDNS

Method: `dns-sd -G v4 dmp168.local`, `dns-sd -B _services._dns-sd._udp local`, plus a Python `zeroconf.ServiceBrowser` across ~25 candidate service types.

### Services advertised

| Type | Instance | Server | Port | TXT records |
|---|---|---|---|---|
| `_http._tcp.local.` | `DMP168._http._tcp.local.` | `DMP168.local.` | 80 | `path=/` |

### Hostname

- **Hostname is the fixed string `DMP168.local`** — not MAC-derived, not serial-derived. Two DMP168s on the same LAN will collide. (`_userspace.dmp168.local` collision behaviour not tested.)
- The A-record resolves cleanly to the device's IPv4 address.
- No custom `_blustream._tcp` / `_dmp168._tcp` service type. No TXT field carries MAC, serial, model, or firmware.

## DHCP

DHCP option payloads (options 12 / 60 / 61) were not captured; the MAC evidence below rests on the vendor-published example and OUI-registry analysis instead.

## OUI registry

The web-GUI screenshot on p. 24 of Blustream's published DMP168 user manual (REV A1) shows MAC `34:D0:B8:27:2D:96`. `api.maclookup.app/v2/macs/34D0B8272D96` returns:

```json
{
  "macPrefix": "34D0B82",
  "company": "Blustream Pty Ltd",
  "address": "24 Lionel Road, Mt. Waverley Victoria 3149, AU",
  "blockStart": "34D0B8200000",
  "blockEnd":   "34D0B82FFFFF",
  "blockType":  "MA-M"
}
```

- The 24-bit OUI `34:D0:B8` is an **IEEE MA-M block holder** (not Blustream directly).
- The **28-bit prefix `34:D0:B8:2`** is sub-allocated to **Blustream Pty Ltd** (AU). Range `34:D0:B8:20:00:00` – `34:D0:B8:2F:FF:FF`, ~1M MACs.
- HA's DHCP matcher must use **at least 7 hex digits** (`34D0B82*`) — matching only on the 24-bit OUI would also match every other tenant of the same MA-M block.
