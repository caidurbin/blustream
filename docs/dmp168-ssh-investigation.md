# DMP168 undocumented SSH service: investigation

Follow-up to the identity spike ([draft-dmp168-identity-spike.md](adr/draft-dmp168-identity-spike.md)). Investigates the `_ssh._tcp` advertisement on port 22 noticed during mDNS enumeration. Target: firmware **MCU 1.5.0 / Web 1.4.0 / DSP 1.5.9** at `192.168.1.176`, 2026-05-27.

## Summary

The DMP168 advertises and answers SSH on TCP/22, running **`Dropbear sshd 2022.83`** on a Linux kernel. The service is **not mentioned anywhere** in `references/DMP168 API.txt`, `references/REVA1_DMP168_User_Manual.pdf`, or `references/DMP168_Datasheet_REVA1.pdf`. The web GUI's network-settings page exposes toggles for Telnet, TCP, and mDNS only — there is **no documented way to disable SSH**. The documented admin password and the obvious embedded-Linux defaults were all rejected, so SSH does not currently grant unauthenticated or known-credential shell access. The integration's identity strategy is unaffected: DHCP discovery remains correct.

## Task 1 — Confirm the service

```
$ nmap -p 22 -sV --version-intensity 5 192.168.1.176
PORT   STATE SERVICE VERSION
22/tcp open  ssh     Dropbear sshd 2022.83 (protocol 2.0)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

Banner: **`Dropbear sshd 2022.83`**, protocol 2.0. nmap's CPE inference identifies the OS as Linux (consistent with Dropbear's typical deployment in embedded Linux firmware). Independent confirmation in [dmp168-known-issues.md](dmp168-known-issues.md) — the SSH daemon stays responsive even when the rest of the control surface wedges, suggesting it lives in a separate process from the failing serial-bridge daemon.

## Task 2 — Auth probe

Single attempt per credential, password auth only (`PreferredAuthentications=password`, `PubkeyAuthentication=no`), one prompt (`NumberOfPasswordPrompts=1`), 8 s connect timeout. Probe script: `/tmp/dmp168_ssh_auth.exp`.

| Username | Password | Result |
|---|---|---|
| `blustream` | documented admin from user manual | denied |
| `root` | *(empty)* | denied |
| `root` | `root` | denied |
| `root` | `admin` | denied |
| `root` | `dropbear` | denied |
| `admin` | `admin` | denied |
| `admin` | *(empty)* | denied |
| `admin` | `blustream` | denied |
| `blustream` | `blustream` | denied |
| `blustream` | `admin` | denied |

Every attempt returned `Permission denied (publickey,password)` from Dropbear. The server advertises both `publickey` and `password` auth; we exercised the password path. **Default credentials do not grant shell access.**

Worth noting: Dropbear answers password prompts at the same speed regardless of whether the *user* exists or not (no observable timing oracle), and it does not silently throttle the connector across this many attempts. The probe is non-destructive; no account-lockout signal was observed.

## Task 3 — Shell inventory

**Not performed.** Auth never succeeded, so no inventory was possible. Items that were on the plan but remain unverified:

- `uname -a` / `/etc/os-release` — OS identified as Linux from `nmap`'s CPE only; kernel version and distribution remain unknown.
- `/sys/class/net/*/address` MAC reading — unverified. (The MAC is already obtainable via ARP / DHCP per the identity spike, so this gap does not block the HA integration.)
- Running processes / `/tmp/web2ser` daemon state — unverified. (Relevant to the *problem*-state investigation in [dmp168-known-issues.md](dmp168-known-issues.md); shell access would let us inspect the failing daemon, which the vendor inquiry already lists as a request.)
- Config-file shape — unverified.

## Task 4 — Security assessment

**Is SSH enabled by default?** Apparently yes. The device under test was never configured to enable SSH — it has been controlled exclusively via the web GUI, raw TCP/8000, and Telnet/23. The web GUI exposes no SSH-related setting (see below), so the user has had no opportunity to enable it. The simplest explanation is that the firmware ships with Dropbear running.

**Do default credentials grant shell?** **No** (Task 2). This downgrades the severity of the finding significantly — the SSH service is undocumented attack surface, but it is not an *open* door. Either Dropbear is running with a randomized password, a vendor-internal password, key-only auth (despite the `password` method being advertised), or no accounts that match the obvious names.

**Can SSH be disabled via the documented surfaces?** **No.**

- The user manual's Network Settings page (`Web-GUI - Settings`, p. 21) lists IP Mode, IP Address/Subnet/Gateway, **TCP Port** (enable/disable), **Telnet Port** (enable/disable), and **Domain name (mDNS)** — no SSH toggle.
- The TCP control-protocol reference (`references/DMP168 API.txt`) documents `NET TCPPORT ON/OFF` and `NET TN ON/OFF` for the two known control channels. No `NET SSH …` command appears anywhere in the published reference, and the identity spike confirmed the device's `HELP` output matches the document byte-for-byte. There is therefore no documented `NET SSH` setter to probe; the spike also showed that probing speculative `NET <foo>?` commands can have destructive side effects (`NET DNS?` overwrote the DNS field with the literal string `?`), so blind probing for an SSH toggle is contraindicated.
- Disabling mDNS would only hide the *advertisement* — port 22 would still answer to anyone scanning the LAN.

**Net assessment.** Undocumented, always-on, non-disable-able SSH on an embedded Linux box on a LAN with no public-credential exposure. Medium-severity finding: not an immediate exploit, but a coordinated-disclosure-worthy gap in vendor transparency.

## Task 5 — Implications for the HA integration

**No change to identity strategy.** The recommended path remains DHCP discovery + zeroconf, per the identity spike. SSH is a poor Tier-2 alternative for identity because:

- It requires credentials at config time. The user manual provides web-GUI credentials, but those don't work over SSH; we'd be asking the user for a credential they don't have.
- Even if a credential were available, every Tier-2 source ultimately resolves to "the MAC", which DHCP discovery delivers without device interaction — SSH would replace a free signal with a privileged one.
- Dropbear's default host key is unique-per-device (generated on first boot), but the SSH *user identity* is not a function of the device serial — there is no benefit to SSH as a fingerprint that ARP doesn't already provide.

**Setup-checklist recommendations for the HA integration documentation:**

1. State plainly that the device exposes SSH on port 22 with no documented disable path. Users running the DMP168 on a hostile or shared network segment should firewall TCP/22 to a trusted management subnet.
2. Do not attempt SSH from the integration. If the user reports `problem`-state symptoms (see [dmp168-known-issues.md](dmp168-known-issues.md)), the diagnosis runbook may *separately* ask the user to coordinate with the vendor for SSH access — but the integration's runtime path must never touch port 22.

## Recommendation

**File a coordinated security disclosure with Blustream Pty Ltd** asking for:

1. Confirmation of whether `Dropbear sshd 2022.83` is enabled on all shipped DMP168 units, or whether the test device was provisioned differently at the factory.
2. Confirmation of whether the Dropbear host key is unique per unit or shared across the fleet (shared host keys would let an attacker MITM any DMP168 on a routable network).
3. A documented, supported mechanism to disable SSH — either a web-GUI toggle alongside the existing Telnet/TCP toggles, a `NET SSH ON/OFF` command, or written confirmation that the service is required for vendor support.
4. Either public documentation of the SSH service (purpose, accounts, intended use) or removal of the service from production firmware.

Attach this document and reference the firmware versions tested. **Do not publish externally** until Blustream has had a reasonable window to respond.

The default-credentials test came up empty, so this is **not** a publish-before-the-vendor-replies disclosure — there is no active exploit to warn users about. Disclosure is appropriate but not time-critical.

## Does this change the HA integration's identity strategy?

**No.** [draft-dmp168-identity-spike.md](adr/draft-dmp168-identity-spike.md) stands as written: Tier-2 DHCP + zeroconf discovery, with MAC from DHCP / ARP as the `unique_id`. SSH is filed as undocumented attack surface, not as an identity surface. The HA integration's responsibility is to surface a *user-facing setup warning* about SSH (see Task 5 recommendations) and otherwise stay out of port 22.

## Artefacts

- nmap output (above)
- Auth probe script: `/tmp/dmp168_ssh_auth.exp`
- Auth probe logs: `/tmp/ssh_root_blank.log`, `/tmp/ssh_admin.log`, `/tmp/ssh_blustream.log`
