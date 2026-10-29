# Live read-only capture: DMP168, 29 Oct 2026

Read-only capture from the real matrix. These are raw captures from the real matrix, to be used as ground truth for a simulator.

- **Firmware:** MCU_Main V1.5.0 / Web_GUI V1.4.0a / DSP V1.5.9.
- **Uptime at capture:** 149 days, 4 hours.
- **Client:** a passive raw socket that never answers telnet IAC, connecting to ports 23 and 8000.

## What was sent

Only these commands were sent. Each is a query according to `spec/protocol.yaml` and the device's own `HELP` listing.

| Command | Why it's safe |
|---|---|
| `STATUS`, `UPTIME`, `TEMP`, `HELP` | Spec "Status / introspection" section |
| `PRESET 1 STATUS` | Spec `preset_status`, "Get preset configuration status"; HELP says "Print Preset xx Config Status" |
| `PRESET 9 STATUS` | Out-of-range read, used to record the `[ERROR]` reply |
| `FOO` | Unknown command, used to record the `[ERROR]` reply |

Every command was terminated with `\r\n`.

**Skipped:**
- `OUT 9 FR 1`. It is a routing write, so a firmware that misparsed it could change a route. `PRESET 9 STATUS` covers the out-of-range `[ERROR]` case instead.
- `PRESET STATUS 1` (that word order). It isn't in the spec or in HELP.
- `DSP STATUS` and `EQ PRESET xx STATUS`. Both look read-only in HELP, but neither is in the spec, so they were not sent.

**Machine state before and after:**
- The first and last `STATUS` on each port are byte-identical apart from the system line, which holds temperature, uptime and DSP%. That covers routing, volumes, mutes, EQ, presets and network.
- Power was On, routing was Out2–5 ← In2 L/R with all other outputs None, and all presets were empty.

## Files

- `p<port>_<client>_<step>.bin` holds the exact bytes received for one step. Client A is the main connection and B is the second one.
  - `*_connect.bin` is what arrived in the first 3 s after connecting, i.e. the banner.
  - `p23_A_after-B-connect.bin` is what A received when B connected.
- `timing.json` gives, for every chunk, `[offset, length, seconds since send/connect]`.
- `passive_p{23,8000}_180s.bin` (plus `.timing.json`) are 180 s with both ports open and nothing sent.
- `scripts/` holds the capture scripts (`capture.py`, `listen_save.py`, `probe.py`).

**Sanitised:** the MAC was replaced with `34:D0:B8:21:22:33` and the LAN IPs with `192.000.002.x`, matching `tests/fixtures/status_live_full.txt`. Both substitutions keep the byte length. A truncated copy of the real MAC inside one corrupted broadcast STATUS in each `passive_*.bin` was overwritten the same way (`34:D0:B8:21:2`, same length). Nothing else was changed.

## Reply shapes

| Command | Port 8000 (exact bytes) | Port 23 |
|---|---|---|
| `UPTIME` | `[SUCCESS]The uptime of the system is 0149:04:17:56\r\n` | `UPTIME\r\n` + same + `\r\nDMP168> ` |
| `TEMP` | `[SUCCESS]The temperature of the system is 38.1C\r\n` | echo + same + prompt |
| `PRESET 1 STATUS` (empty preset) | `[ERROR]Preset 1 config status null.\r\n` | echo + same + prompt |
| `PRESET 9 STATUS` | `[ERROR]PRESET param out of range. Type "HELP" for more reference.\r\n` | echo + same + prompt |
| `FOO` | `[ERROR]Command not found.\r\n` | echo + same + prompt |
| `STATUS` | `\r\n` + 64×`=` … 64×`=` + `\r\n` (11,694 B). No `[SUCCESS]` | echo + same + `\r\nDMP168> ` (11,712 B) |
| `HELP` | `\r\n` + 64×`=` … listing … 64×`=` + `\r\n` + 15 lines of DSP prose (21,297 B) | echo + same + prompt |

**Timing:**
- The first byte arrives about 0.10–0.25 s after the send.
- Simple replies arrive in one chunk on port 8000, but in 7–19 small chunks on port 23.
- `STATUS` streams in about 600 chunks over about 1.4–1.5 s.
- `HELP` streams in about 360 chunks over about 2.1 s.

**Port 23 connect:**
1. IAC `FF FB 03 FF FC 01 FF FE 01 FF FE 00` (WILL SGA, WONT ECHO, DONT ECHO, DONT BINARY).
2. The 232-byte banner: `\r\n` + 64×`=` + `\r\nWelcome to DMP168 Terminal Control System\r\nFW Version: 1.5.0\r\n\r\nType "HELP" For More Information\r\n` + 64×`=` + `\r\n`.
3. There is no `DMP168> ` prompt until after the first command.

**Port 8000 connect:** sends nothing.

## Differences from the spec and code

1. **Every client on both ports receives all command output.**
   - With nothing sent, both passive sockets received every `STATUS` that another LAN client issued, about every 32–35 s. This is probably a Home Assistant integration's 30 s poll, but that is unconfirmed.
   - On port 23 the broadcast includes that client's command echo. On port 8000 it doesn't.
   - As a result, the first commanded `STATUS` on each port came back with two full dumps (`p*_A_STATUS_1.bin`).
   - A `probe.py` rerun showed this is timing, not "first command after connect". One of those runs got a stray `STATUS` dump in reply to `UPTIME`.
   - Impact:
     - Any reader can pick up another client's `[SUCCESS]`/`[ERROR]`/`STATUS` as its own reply. This matters for framing in `tcp.py`/`device.py` and in `connection.lua`, and for the Control4 command queue.
     - The simulator must broadcast.
2. **The port-23 banner also reaches port-8000 clients.**
   - When a port-23 client connects, every open client on both ports gets the banner (`passive_p8000_180s.bin` starts with it).
   - `tcp.py:135-137` and ADR 0005 assume port 8000 never sees a banner. That is true only for 8000's own connect.
   - Port 23's own A connection also received the banner twice at connect, once before the IAC block. This is unexplained, and probably another client connecting at the same moment.
3. **`STATUS` can arrive corrupted.**
   - In the passive capture, 6 binary frames `AA 54 <len:u16 BE> 07 <payload> A5` were interleaved in `STATUS` text, identically on both ports. Their payloads were EQ fields and the `Telnet TCP/IP Mac` line.
   - Bytes were also dropped nearby, e.g. `[4000 ,00,off ]`.
   - None of the commanded dumps were corrupted.
   - Both `status_parser.parse` and `DMP168Parser.parse_status` accept the corrupted stream without raising, so bad data would pass silently.
   - This is a good fault-injection case for the simulator.
4. **Port 23 adds an echo and a prompt.**
   - It echoes the command line (`<cmd>\r\n`) and ends every reply with `\r\nDMP168> ` (no newline). Port 8000 has neither.
   - The code comments describe `[SUCCESS]`/`[ERROR]` framing but not the echo or the prompt.
5. **An empty preset returns `[ERROR]`.**
   - `PRESET 1 STATUS` on an empty preset gives `[ERROR]Preset 1 config status null.` and not a status body.
   - `parse_preset_status` / `send_command` will see that as an error for any unsaved preset.
6. **`HELP` has prose after its footer.** The trailing DSP prose comes after the `=`-only footer that `_help_terminator` stops on, so roughly 900 bytes stay in the buffer ahead of the next reply. The effect is unverified.
7. **`HELP` doesn't match the spec in a few places.** These are untested, since they are writes.
   - **No `OUT MASTER`:** there is no `OUT MASTER VOL` or `OUT MASTER MUTE`, only `GROUP MASTER …` and `BUS MASTER …`. The spec's `output_master_volume` and `output_master_mute` may be rejected.
   - **Channel token placement:**
     - HELP: `OUT xx VOL vv yy zz`, `OUT xx MUTE vv ON/OFF`, `OUT xx DELAY vv yy`.
     - Spec: emits the channel both before and after `VOL`/`MUTE`, and before `DELAY`.
   - **Input range:** `OUT xx vv FR yy` allows inputs 1–24, the same as the spec. A route to input 20 may therefore be accepted rather than rejected, so it is not a reliable way to provoke an `[ERROR]`.
8. **Fixture drift:**
   - `tests/fixtures/status_live_full.txt` has Web_GUI `V1.4.0`, baud 9600, output delay `0 0` and Local `DMP168`.
   - Live has `V1.4.0a`, 57600, `110 110` and `?`.
9. **Parsers accept the clean captures.** Both parsers accept the clean `p*_A_STATUS_2.bin` captures (power On, 16 route rows).
