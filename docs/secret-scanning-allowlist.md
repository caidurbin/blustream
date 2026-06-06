# Secret-scanning allowlist

Repository values that look like secrets or device identifiers to an automated
scanner but are **intentionally public**. This is the shared source of truth for
secret-scanning allow-rules: the local pre-commit scanner (betterleaks + custom
device-identifier rules) and GitHub-native secret scanning should both treat
everything listed here as a known non-secret.

When a scan flags one of these, it is a false positive. Extend this table when a
new genuinely-public value is introduced, rather than silencing scanners ad hoc.

| Value / pattern | What it is | Why it is safe to publish |
|---|---|---|
| `34:D0:B8`, `34:D0:B8:2*` | Blustream's IEEE OUI / 28-bit MA-M block | Manufacturer-assigned and **required** to be public — declared in the HA manifest (`dhcp: 34D0B82*`) so discovery works (see `docs/adr/0010-ha-integration-device-identity.md`) |
| `34:D0:B8:27:2D:96` | MAC printed in Blustream's published User Manual (p. 24) | Published by the vendor; a documentation example, not a private device |
| `34:D0:B8:2A:BB:CC`, `…:21:22:33`, `…:AA:BB:CC`, `…:20:00:00`, `…:2F:FF:FF` | Synthetic example MACs (real OUI, fabricated host octets) | Invented host portions used in tests and the `status` fixture |
| `dmp168.local`, `DMP168` | Vendor default mDNS hostname | Fixed default for every unit; not user-specific |
| `192.168.1.100` | Conventional example LAN IP | Placeholder in README / CLI docs; not a real host |
| `10.0.0.5`, `192.168.1.1`, `192.168.1.10`, `192.168.1.99` | Test-fixture IPs | Synthetic values in the Control4 Lua specs |
| `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24` | RFC 5737 documentation IP ranges | Reserved by RFC for documentation; never routable |
| `00:00:5E:00:53:00`–`FF` | RFC 7042 documentation MAC range | Reserved by RFC for documentation examples |
| `name@example.com` | Placeholder author/contact email | Used in doc author lines; not a real address |
