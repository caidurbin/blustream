# Secret-scanning allowlist

Repository values that look like secrets or device identifiers to an automated
scanner but are **intentionally public**. This is the human-readable companion to
[`.gitleaks.toml`](../.gitleaks.toml) — the shared source of truth consumed by the
local pre-commit scanner (betterleaks + custom device-identifier rules) and by
GitHub-native secret scanning. Everything listed here is a known non-secret; the
allowlists in `.gitleaks.toml` encode exactly these patterns.

## Policy: example identifiers use documentation ranges

Every **example** IP or MAC committed to this repo must use an IETF
documentation range, so the scanner can allowlist *only* those ranges and still
block a real device identifier planted anywhere:

- IPv4 → **RFC 5737**: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`
- IPv6 → **RFC 3849**: `2001:db8::/32`
- MAC  → **RFC 7042**: `00:00:5E:00:53:00`–`FF`

The one unavoidable exception is the Blustream OUI: a MAC's first 24 bits are
manufacturer-assigned and **required** to be public (the HA manifest declares
`dhcp: 34D0B82*` so discovery works). Synthetic test MACs therefore keep the real
`34:D0:B8` prefix and fabricate only the host octets.

When a scan flags a value, the fix is almost always to move it into a
documentation range — **not** to widen the allowlist. Extend the table below only
for a genuinely-new public value (e.g. another vendor-published identifier).

| Value / pattern | What it is | Why it is safe to publish |
|---|---|---|
| `34:D0:B8`, `34:D0:B8:2*` | Blustream's IEEE OUI / 28-bit MA-M block | Manufacturer-assigned and **required** to be public — declared in the HA manifest (`dhcp: 34D0B82*`) so discovery works (see `docs/adr/0010-ha-integration-device-identity.md`) |
| `34:D0:B8:21:22:33`, `…:AA:BB:CC` | Synthetic example MACs (real OUI, fabricated host octets) | Invented host portions used in the component tests and the `status` fixture |
| `34:D0:B8:27:2D:96` | MAC printed in Blustream's published User Manual (p. 24) | Published by the vendor; a documentation example, not a private device |
| `34:D0:B8:2A:BB:CC` | Dev-unit MAC quoted in the identity-spike ADR | Author's own bench unit, within the public OUI; kept as an empirical example |
| `00:00:5E:00:53:00`–`FF` | RFC 7042 documentation MAC range | Reserved by RFC for documentation examples |
| `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24` | RFC 5737 documentation IPv4 ranges | Reserved by RFC for documentation; never routable. Includes the zero-padded form the device prints in its status table (e.g. `192.000.002.176`) |
| `2001:db8::/32` | RFC 3849 documentation IPv6 range | Reserved by RFC for documentation |
| `255.255.255.x` | Subnet mask / broadcast address | Network parameter, not a host identifier |
| `0000::57:01` | A `DDDD:HH:MM:SS` uptime duration that happens to parse as a compressed IPv6 literal | Time value in `tests/test_uptime_parser.py`, not an address |
| `dmp168.local`, `DMP168` | Vendor default mDNS hostname | Fixed default for every unit; not user-specific |
| `name@example.com` | Placeholder author/contact email | Used in doc author lines; not a real address |
