---
applies_to: [python-library]
date: 2026-11-14
---

# Reply attribution on a broadcast bus

**Constraint.** The DMP168 sends every command's output to every connected client,
on both port 23 and port 8000, and tags none of it: no sequence number, client tag
or command id appears in any capture. A reply to another client's command (a
*foreign reply*) can land just before ours, while we are idle, or part way through a
dump that stalled. A reader that takes the first line that looks like a reply can
return someone else's `TEMP` for our `UPTIME`, or someone else's `[ERROR]` for our
write.

What the wire does give us:

- Port 23 echoes each command, as sent and case included, ahead of its reply. After
  the first command the echo shares a line with the previous prompt
  (`DMP168> UPTIME`). A write block is the echo, the reply line
  (`[SUCCESS]Set output 8 L/R mute on.`), then the next prompt. Port 8000 has no
  echo and no prompt.
- The device queues commands and writes each command's output as one unbroken
  block. In live captures on 2026-11-14, two clients on one port sent `STATUS` and
  then `UPTIME` 0.2-1.0 s apart; in 32 of 32 trials, across both ports, the `UPTIME`
  echo and reply came only after the whole `STATUS` dump.
- Replies can stall. Write replies came up to 23.1 s after their echo, longer than
  the 5 s response timeout. One `STATUS` dump in 60 stalled for 33 s mid-dump and
  arrived short. A dump can also end torn mid-line, with no footer, and the next
  echo then arrives glued onto the torn line (`==========STATUS`).

**Decision: attributed framing.** `BlustreamDevice.send_command` finds our reply by
its start line and ends it at a terminator made fresh at each start line:

- On a link that echoes (`Connection.echoes_commands`), our reply starts at our own
  echo. The block is unbroken, so the lines after it are ours, and an `[ERROR]` line
  among them is our rejection. A reply that stalls past its timeout arrives before
  the next command's echo and is skipped.
- On both ports, `UPTIME`, `TEMP`, `STATUS` and `HELP` replies must fit their own
  shape: the reply text for `UPTIME` and `TEMP`, and the title line followed by a
  footer for `STATUS` and `HELP`. On port 8000 our reply starts at the first line
  that fits. On port 23 the reply starts at the echo, and the terminator is a second
  check after it: the reply text for `UPTIME` and `TEMP`, the header and footer for
  `STATUS` and `HELP`. Shapes are hand-written in the DMP168 device module
  (ADR 0007).
- Each start line restarts the frame with a fresh terminator, so a stateful
  terminator that a foreign dump armed starts over at ours.
- `TCPConnection` detects echo mode from the telnet negotiation (the device offers
  `WILL SGA` on port 23), read without waiting. When it has not been seen, port 23
  means echo. An explicit `echoes_commands` argument overrides both.
- The pre-send drain and the banner strip stay. The drain keeps stale output out of
  the read; the strip removes a peer's banner from inside our block.

**Known limits.** On port 8000 a write's `[SUCCESS]` or `[ERROR]` line has no shape
that names its command, so the first marker line ends the read, whoever it came
from. Such a write is best-effort; an `[ERROR]` read that way still raises
`CommandError`, and its message says that the reply may belong to another client.
The captured write replies restate the output and value, so port-8000 write shapes
are possible later. On port 8000, a torn foreign `STATUS` that ends with no footer
just ahead of ours is still returned in place of ours: our dump's top `=` rule ends
the read one line before our title can restart it (#119). A query reply that stalls
past its timeout fits its own shape, so on port 8000 it is taken as the reply to the
next query of the same command; `DMP168.reboot()` can then read an old uptime as a
restart (#119). On port 23 an echo glued onto a torn line that ends in a letter or
digit is not recognised, and the command times out. A foreign reply to the same
command text is accepted as ours; for queries it is equally fresh and for writes it
has the same effect. Port 23 is the recommended port when other clients share the
matrix. The Control4 driver, which uses port 8000 (ADR 0005), faces the same
broadcast; that is #117.

**Rejected alternatives.**

- *Shape checks alone, on both ports.* They attribute queries but not writes on
  either port, and port 23's echo attributes every command at no extra cost.
- *A longer listen-before-talk drain.* It adds up to 1.5 s per command while a dump
  streams and still loses to a foreign command sent just before ours. A 33 s
  mid-dump stall looks like silence, so the drain ends and the tail lands in our
  read anyway.
- *Echo anchoring on port 23 alone.* It leaves port 8000 queries and `STATUS`
  unattributed when shapes cover them.
- *Reading state back after each write.* A `STATUS` costs about 1.5 s and 11.7 KB,
  many writes (relative steps, presets, reboot) don't show in it, and the Home
  Assistant integration already refreshes after every write.
- *Documenting single-client use only.* The captures show a second client polling
  every 30 s on an ordinary installation, and wrong values reach callers.
- *A settle window after a port-8000 marker.* It rests on device timing, which the
  stalls show can't be relied on, and adds latency to every write.
