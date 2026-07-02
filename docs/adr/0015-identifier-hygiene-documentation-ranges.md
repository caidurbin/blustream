---
applies_to: [repo]
date: 2026-07-01
---

# Committed identifiers must use IETF documentation ranges

Every example IP or MAC committed to this repo must use an IETF documentation range
(RFC 5737 / RFC 3849 / RFC 7042), enforced by betterleaks — run as a pre-commit hook
and as a CI gate — with custom IPv4/IPv6/MAC rules in the shared `.gitleaks.toml`
that block any real device identifier. The one allowed real value is the Blustream
OUI prefix (`34:D0:B8`), which is manufacturer-assigned, required to be public for HA
discovery, and kept in synthetic test MACs whose host octets are fabricated. When a
scan flags a value, the fix is to move it into a documentation range — not to widen
the allowlist. Operational mechanics and the current allowlist live in
[`docs/secret-scanning-allowlist.md`](../secret-scanning-allowlist.md).
