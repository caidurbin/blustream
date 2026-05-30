# DMP168 known issues

## "Problem" state

The DMP168 has three operator-visible states: **off**, **on**, and **problem**. In the *problem* state the device appears unresponsive — control commands silently fail and the web console rejects valid logins — even though the device is still powered and answering on the network.

The device enters this state spontaneously after running normally for some period. No API or UI action recovers it; only a power-cycle restores normal operation. The device returns to the *problem* state again after another indeterminate interval.

**Versions observed:** the bug has been reproduced on MCU V1.5.0, Web V1.4.0, DSP V1.5.9.

**Configuration observed.** Settings on the device when the bug recurs:

- Standby Mode = Sleep (the mode the manual describes as *"the unit will power off but the API and web-GUI remain active"*)
- Auto Standby Time = **0 minutes (disabled)** — the device is not entering Sleep automatically
- Telnet (port 23) and raw TCP (port 8000) control are **both enabled** in the network config
- All hardware triggers (rear-panel SW1, SW2, VI1, VI2) are disabled

In particular, Auto Standby is off: the device enters the *problem* state without any auto-standby trigger, so the bug is **not** caused by a Sleep-mode transition.

**Workload observed:** no audio has been routed or played through the device during the reproduction periods. The failure occurs at idle, so it is not workload-induced (DSP load, routing activity, or output traffic).

## Detection

The cheapest unambiguous probe is a TCP connect on port 23:

- *On* → connect succeeds (followed by telnet IAC negotiation bytes).
- *Problem* → SYN times out (not RST / "connection refused" — that would distinguish a configuration-disabled service from this stuck state).

ICMP reachability is **not** a reliable signal: the device responds to ping in both the *on* and *problem* states.

### Other symptoms

Beyond the Telnet probe above, the web UI surfaces these secondary signs in the *problem* state — useful when diagnosing from a browser:

- **Login is rejected with "Wrong password" for known-good credentials.** The toast persists across attempts and gives no hint that the failure is server-side rather than a credential mistake.
- **`POST /cgi-bin/instr` either returns HTTP `200 OK` with a `text/plain` error-shaped body, or hangs the connection indefinitely with zero bytes returned.** Observed quick-response sentinels include `[err]Fail to open fifo: /tmp/web2ser.` and `not wait comhead [<command>]`. The CGI layer never returns a non-200 status; the web UI does not string-parse the body, so failures are silent on screen.
- **The SPA polls `/cgi-bin/instr` continuously, including from the pre-authentication login screen.** Each polling cycle aborts the previous in-flight request (`net::ERR_ABORTED`), producing dozens of failed requests per minute with no user-visible signal. This noise can also cancel an in-flight login submission before the server replies.
- **The alternate raw-TCP control port (8000) is also impaired.** An initial TCP `connect` may succeed, but the server closes the connection without responding to any command (0 bytes returned). After such an exchange, subsequent connects fail at the TCP layer with the same timeout signature as port 23. Port 8000 is **not** a viable software-reboot channel in this state.

## Overnight monitor run (2026-05-25 → 2026-05-26)

A monitoring script captured one full `on → problem` transition during an overnight idle run. `tools/dmp168_state.py` ran every 30 seconds and appended each result to `dmp168_monitor.log`. The device was power-cycled just before the run; the web UI was used briefly to verify it, then the operator stepped away. The `NOTE` marker in the table marks the end of that manual session.

Each snapshot runs three probes (no browser, no auth) and classifies the result:

1. **ICMP ping** — single packet, 2 s timeout. No reply → state `off`.
2. **TCP connect on port 23** — 3 s timeout. `open` → `on`; `timeout` (with ping replying) → `problem`. The canonical detection probe.
3. **HTTP `POST /cgi-bin/instr`** with body `{"comhead":"get status"}`, 3 s timeout. Not used for classification, but when it returns 200 + JSON the script extracts the device's reported `uptime` and `temp` (source of the uptime column below).

| # | Time (UTC*) | Time (EDT†) | Uptime‡ | Time since last web UI session | Event |
|---|---|---|---|---|---|
| 1 | 03:22:34Z | May 25, 23:22:34 | 0:07:29 | — | Monitor starts. State `on`, device freshly power-cycled. Manual UI session still active. |
| 2 | 03:25:07Z | May 25, 23:25:07 | 0:10:02 | — | Brief CGI `unreachable` (one sample, recovers). Plausibly SPA-vs-monitor contention while the UI was still open. |
| **3** | **03:36:08Z** | **May 25, 23:36:08** | **~0:21:03** | **0s** | **← Manual web UI session ended** (NOTE marker in log). Only monitor-script traffic from here on. |
| 4 | 06:13:58Z | May 26, 02:13:58 | 2:58:53 | 2h 37m 50s | Last successful CGI poll. |
| 5 | 06:14:29Z | May 26, 02:14:29 | ~2:59:24 | 2h 38m 21s | CGI starts returning `unreachable` and never recovers. Telnet/23 still open, state still `on`. |
| 6 | 06:16:41Z | May 26, 02:16:41 | ~3:01:36 | 2h 40m 33s | State flips `on` → `problem` — telnet/23 now times out. |
| 7 | 10:01:37Z | May 26, 06:01:37 | ~6:46:32 | 6h 25m 29s | Single missed ping (`off` for one sample), back to `problem` 30s later. |
| 8 | 23:24:08Z | May 26, 19:24:08 | ~20:09:03 | 19h 48m 0s | Same — one missed ping, back to `problem`. |
| 9 | 23:57:51Z | May 26, 19:57:51 | ~20:42:46 | 20h 21m 43s | Last snapshot in log; still `problem`. |

\* All rows are 2026-05-26 UTC. † UTC−4 (EDT). ‡ Extrapolated after row 4; the device hasn't rebooted (ping continues) but its own uptime counter is unreadable once CGI stops responding.

Notes:

- The transition happened after ~2h 38m of idle time with only the script's 30-second polling as load. The daemon was steady up to the moment it failed — no progressive degradation observable in this trace.
- HTTP/80 CGI started failing ~2 minutes before TCP/23 timed out, suggesting the web CGI is a slightly earlier indicator than the canonical telnet probe.
- The two `off` samples (rows 7 and 8) are single missed pings surrounded by `problem` on either side — almost certainly transient network blips, not real device-off events.
- Normal operation resumed immediately after a restart.

## Mitigation

Two hardware recovery paths:

- **Power-cycle.** Fast, preserves configuration.
- **Hold the rear-panel `RESET` button for ≥10 s** (recovery ~30 s, per the Blustream DMP168 user manual, p.4). Also recovers the daemon but **factory-resets configuration** — export the config first via System → Import/Export while the device is healthy so it can be restored afterwards.

There is no known software recovery path; every documented control surface is fronted by the same failing daemon.

## Open questions

- **Root cause is unverified.** Every command surface (Telnet 23, raw 8000, web CGI) fails together while the static HTTP layer (port 80) continues to serve normally — strong evidence that a single shared on-device component is the failing element, likely the serial-bridge daemon behind the `/tmp/web2ser` fifo.
- **Time-to-failure is uncharacterized.** The recorded run failed ~3h after cold boot (~2h 38m after the last UI activity). n=1; the doc previously said only "indeterminate interval".
- **The failure is staged, not instantaneous.** HTTP/80 `/cgi-bin/instr` went `unreachable` ~2 minutes before TCP/23 timed out. If both surfaces share one daemon, that daemon must die in stages rather than at a single instant.

## Suggested next steps

1. **Back up the configuration** via System → Import/Export while the device is healthy, so the rear `RESET` button becomes a usable alternative to power-cycling. Note that the exported file covers audio configuration (routing, levels, presets, triggers) but **not** network or system-audio settings (Telnet/TCP enables, IP mode, baud rate), so those will need to be reapplied manually after a factory reset.
2. **Ask the vendor** for a firmware fix or workaround for the daemon-stability issue — the public documentation includes no errata, troubleshooting, watchdog, or daemon architecture notes. Attach `dmp168_monitor.log` to the inquiry — it records one full transition at 30-second resolution.
3. **Switch monitors to HTTP/80 `/cgi-bin/instr` as the leading-edge probe.** It fails ~2 minutes before the canonical TCP/23 probe, giving earlier warning of an impending wedge.
4. **Repeat the overnight monitor run** to characterize the time-to-failure beyond n=1.
