# Blustream — domain glossary

Canonical vocabulary for the Blustream project. Update inline as new terms
are resolved during design or grilling sessions. Implementation details
belong in ADRs, not here.

## HA integration POC

The first published version of the Home Assistant integration is a
**"gold-tier POC"**: it exposes a single entity (the uptime sensor)
but every other surface — config flow, discovery, reconfiguration,
diagnostics, repair issues, translations, device registry — is built
to the HA Integration Quality Scale Gold standard from day one. The
narrowness is in entity *count*, not in production-quality
scaffolding. Adding further entities (volume, mute, routing, presets)
in later versions is purely additive — no scaffolding catch-up
required.

## Uptime

The elapsed duration since the device last booted.

The DMP168 protocol reports uptime as a `DDDD:HH:MM:SS` string from the
`UPTIME` command (also embedded in `STATUS`). The Python library exposes it
both unmodified — as a string via `get_uptime_raw()` (the *uptime duration*) —
and parsed into a `timedelta` via `get_uptime()`.

The Home Assistant integration derives a **boot time** from uptime
(`now - parsed_uptime`) and surfaces *that* as the entity value, using
`SensorDeviceClass.UPTIME`. So in the HA surface, "the uptime sensor" reports
*when the device last booted*, not how long it has been up — even though the
sensor is conventionally named "uptime" both in HA's vocabulary and ours.

When discussing this in code or design: prefer "boot time" for the derived
datetime, "uptime duration" for the raw `DDDD:HH:MM:SS` string. Reserve
"uptime" alone for the user-facing concept (which collapses both).

## Device identity

The DMP168 has a MAC address (shown on the web GUI's Information page as
e.g. `34:D0:B8:27:2D:96`) and a user-configurable mDNS domain name
(default: `dmp168.local`). **Neither is reachable through the device's
TCP command protocol** — the `NET …` commands are setters only, `STATUS`
emits no identity fields beyond model and firmware, and a live-hardware
probe of 52 undocumented-command candidates (firmware MCU 1.5.0 / Web
1.4.0 / DSP 1.5.9) confirmed the device has no hidden identity getter.
The device's `HELP` output matches the published API doc verbatim.

The MAC is reachable through two non-protocol channels:

1. **DHCP discovery** — the device requests DHCP leases with its
   real MAC. HA's `dhcp` discovery surface delivers `DhcpServiceInfo`
   with `macaddress`, hostname, and IP. This is the canonical
   programmatic identity path. The Blustream MAC prefix is the 28-bit
   IEEE MA-M block `34:D0:B8:2*` (NOT the full 24-bit OUI `34:D0:B8`,
   which is the parent IEEE MA-M block shared with other vendors).
2. **HTTP scrape of the web GUI Information page** — works but
   requires admin auth, is brittle to firmware UI changes, and is
   considered a code-review smell in HA core.

The default mDNS Domain Name is `DMP168` (fixed `dmp168.local`, not
MAC-derived), so two out-of-the-box units on one LAN collide on mDNS
until renamed. mDNS therefore serves as a discovery UX assist (find
the IP automatically) but **cannot** carry stable per-device identity.




