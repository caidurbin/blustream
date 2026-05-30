"""Pure-function parser for the DMP168 uptime *duration* string.

Converts the raw ``DDDD:HH:MM:SS`` uptime-duration string — as returned by the
``UPTIME`` command and embedded in the system header of ``STATUS`` — into a
:class:`datetime.timedelta`.

This is a sibling of :mod:`blustream.devices.dmp168.status_parser`: a
module-level pure function, deliberately **not** part of the legacy
class-based :class:`blustream.devices.dmp168.parser.DMP168Parser`. Keeping the
parse boundary as a free function mirrors the Lua driver's parser shape and
keeps the cross-language contract narrow (ADR 0011 — the library owns the
protocol boundary). See CONTEXT.md "Uptime" for the duration-vs-boot-time
vocabulary the Home Assistant integration depends on.
"""

from __future__ import annotations

import re
from datetime import timedelta

from blustream.base.exceptions import ParseError

# DDDD:HH:MM:SS — four colon-separated, non-negative ASCII-integer fields.
# ``re.ASCII`` constrains ``\d`` to 0-9: the device never emits non-ASCII
# digits, so Unicode digits are corrupt input and must be rejected rather than
# silently coerced by ``int``. Field widths are not pinned and the H/M/S
# components are not range-checked (this is a *duration*, not a wall-clock
# time); values that overflow ``timedelta`` or exceed CPython's int-from-string
# limit are caught in ``parse`` and re-raised as ParseError, so the
# ParseError-only contract holds for every input.
_UPTIME_RE = re.compile(r"^(\d+):(\d+):(\d+):(\d+)\Z", re.ASCII)


def parse(raw: str) -> timedelta:
    """Parse a raw ``DDDD:HH:MM:SS`` uptime-duration string into a timedelta.

    Args:
        raw: The uptime-duration string, e.g. ``"0000:08:57:01"``.

    Returns:
        The uptime as a :class:`datetime.timedelta`.

    Raises:
        ParseError: If ``raw`` is empty, an ``[ERROR]…`` device reply, not four
            colon-separated ASCII-integer fields (missing colons, non-numeric,
            Unicode digits, or a partial value), or a value too large to
            represent as a :class:`datetime.timedelta`.
    """
    text = raw.strip()
    if not text:
        raise ParseError("uptime string is empty")
    if text.upper().startswith("[ERROR]"):
        raise ParseError(f"device returned an error instead of uptime: {raw!r}")

    match = _UPTIME_RE.match(text)
    if match is None:
        raise ParseError(f"malformed uptime string {raw!r}; expected DDDD:HH:MM:SS")

    try:
        days, hours, minutes, seconds = (int(group) for group in match.groups())
        return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    except (ValueError, OverflowError) as exc:
        raise ParseError(f"uptime {raw!r} is out of representable range") from exc
