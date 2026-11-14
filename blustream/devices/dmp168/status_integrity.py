"""Integrity check for a DMP168 ``STATUS`` dump.

A broadcast ``STATUS`` dump can arrive corrupted: the device interleaves binary
frames (``AA 54 <len:u16 BE> 07 <payload> A5``) into the text and drops bytes
near them (``tests/fixtures/live/2026-10-29/FINDINGS.md``). Both STATUS parsers
call :func:`check` before they read any value, so a corrupted dump raises
:class:`ParseError` and a poll can retry instead of publishing bad state.
"""

from __future__ import annotations

import re

from blustream.base.exceptions import ParseError

# Anything outside printable ASCII, tab, CR and LF. A binary frame decodes to
# NUL, other control bytes or U+FFFD, so it always contains one of these.
_NON_TEXT_RE = re.compile(r"[^\t\r\n\x20-\x7e]")

# A row that belongs to one input or output port.
_PORT_ROW_RE = re.compile(r"(?:In|Out)\d+")

_NUMBER = r"-?\d+(?:\.\d+)?"
# A level column. With the level unit set to dB the device may print a signed
# decimal with a unit; no dump in that mode has been captured. The check lets
# such levels through so a dB-mode unit polls as it does without the check;
# reading dB levels is the parsers' job.
_LEVEL = r"[-+]?\d+(?:\.\d+)?(?:dB)?"
_ON_OFF = r"(?:On|Off)"
# One comma-separated field inside an EQ band, padded with spaces.
_EQ_FIELD = r" *[^\s\[\],]+ *"
_EQ_BAND_2 = rf"\[{_EQ_FIELD},{_EQ_FIELD}\]"
_EQ_BAND_3 = rf"\[{_EQ_FIELD},{_EQ_FIELD},{_EQ_FIELD}\]"


# The shapes a port row takes in a clean dump. Each is matched against the
# whole row with trailing whitespace removed.
_PORT_ROW_SHAPES = (
    # Matrix Config: "Out1 L        In2 L", "Out1 R        Bus3 R",
    # "Out1 L        None". Source tokens match case-insensitively, as
    # DMP168Parser reads them, since the BUS sections print "BUS<n>".
    re.compile(r"Out\d+ +[LR] +(?:None|(?i:in|bus)\d+ +[LR])"),
    # Input Settings and Output Settings: port, lock, L/R level, L/R mute,
    # then the numeric columns (maximum, delay, mix, group).
    re.compile(
        rf"(?:In|Out)\d+ +{_ON_OFF} +{_LEVEL} +{_LEVEL} +{_ON_OFF} +{_ON_OFF}"
        rf"(?: +{_NUMBER})*"
    ),
    # Input EQ and Output EQ: L/R, then eight bands of
    # [freq, slope], [freq, gain], four of [freq, gain, Q], [freq, gain],
    # [freq, slope].
    re.compile(
        rf"(?:In|Out)\d+ +[LR](?:{_EQ_BAND_2}){{2}}(?:{_EQ_BAND_3}){{4}}"
        rf"(?:{_EQ_BAND_2}){{2}}"
    ),
)


def check(response_text: str) -> None:
    """Raise :class:`ParseError` if a ``STATUS`` dump is corrupted.

    A dump counts as malformed when either holds:

    * It contains a character outside printable ASCII, tab, CR and LF. This
      catches the interleaved binary frames, which carry NUL and other control
      bytes and decode to U+FFFD.
    * A row starting with ``In<n>`` or ``Out<n>`` does not match one of the
      port row shapes a clean dump uses: a Matrix Config row
      (``Out1 L  In2 L``, ``Bus<n>`` or ``None`` as the source), an Input or
      Output Settings row (lock, two levels, two mutes, then numbers only), or
      an Input or Output EQ row (exactly eight ``[...]`` bands with 2, 2, 3, 3,
      3, 3, 2 and 2 fields). This catches rows truncated or spliced by dropped
      bytes, such as an EQ band reading ``[4000 ,00,off ]``.

    Lines that are not port rows (titles, column headers, the system line,
    bus, group, preset, trigger and network rows) are checked for characters
    only.
    """
    bad_char = _NON_TEXT_RE.search(response_text)
    if bad_char is not None:
        raise ParseError(
            f"STATUS response is corrupted: non-text character "
            f"{bad_char.group()!r} at offset {bad_char.start()}"
        )
    for number, line in enumerate(response_text.splitlines(), start=1):
        row = line.rstrip()
        if not _PORT_ROW_RE.match(row):
            continue
        if not any(shape.fullmatch(row) for shape in _PORT_ROW_SHAPES):
            raise ParseError(
                f"STATUS response is corrupted: malformed row on line {number}: "
                f"{row[:80]!r}"
            )
