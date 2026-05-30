"""Table tests for the pure-function uptime-duration parser (issue #29).

Mirrors the module shape of :mod:`blustream.devices.dmp168.status_parser`: a
free function mapping the device's raw ``DDDD:HH:MM:SS`` uptime-duration string
onto a :class:`datetime.timedelta`, raising the library's :class:`ParseError`
on any non-conforming input.
"""

from datetime import timedelta

import pytest

from blustream.base.exceptions import BlustreamError, ParseError
from blustream.devices.dmp168.uptime_parser import parse


class TestParseValid:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("0000:00:00:00", timedelta(0)),
            ("0000:00:00:01", timedelta(seconds=1)),
            ("0000:00:01:00", timedelta(minutes=1)),
            ("0000:01:00:00", timedelta(hours=1)),
            ("0001:00:00:00", timedelta(days=1)),
            ("0000:08:57:01", timedelta(hours=8, minutes=57, seconds=1)),
            ("0042:12:30:45", timedelta(days=42, hours=12, minutes=30, seconds=45)),
            ("9999:23:59:59", timedelta(days=9999, hours=23, minutes=59, seconds=59)),
        ],
    )
    def test_valid_magnitudes(self, raw, expected):
        assert parse(raw) == expected

    def test_surrounding_whitespace_tolerated(self):
        # The device value arrives pre-stripped, but the pure function is
        # tolerant of incidental whitespace so callers needn't pre-clean.
        assert parse("  0000:08:57:01\r\n") == timedelta(hours=8, minutes=57, seconds=1)


class TestParseBoundaries:
    def test_min_boundary_is_zero_duration(self):
        assert parse("0000:00:00:00") == timedelta(0)
        assert parse("0000:00:00:00").total_seconds() == 0

    def test_max_boundary_total_seconds(self):
        # 9999d 23h 59m 59s — the widest the DDDD:HH:MM:SS field can express.
        expected = timedelta(days=9999, hours=23, minutes=59, seconds=59)
        assert parse("9999:23:59:59") == expected
        assert parse("9999:23:59:59").total_seconds() == 9999 * 86400 + 23 * 3600 + 59 * 60 + 59


class TestParseFailures:
    @pytest.mark.parametrize(
        "raw",
        [
            "",  # empty
            "   ",  # whitespace only -> empty after strip
            "\r\n",  # bare line terminators
            "[ERROR]Invalid Command",  # device error reply
            "[ERROR]",  # bare error marker
            "0000:08:57",  # partial: 3 fields
            "08:57:01",  # partial: 3 fields, no days
            "0000:08:57:01:99",  # too many fields
            "0000:08:57:0a",  # non-numeric field
            "abcd:ef:gh:ij",  # all non-numeric
            "00000805701",  # missing colons
            "0000-08-57-01",  # wrong separators
            "0000:08:57:",  # trailing empty field
            ":08:57:01",  # leading empty field
            "0000::57:01",  # empty middle field
            "0000:08:57:01extra",  # trailing junk
            "-1:00:00:00",  # negative field (\d+ rejects sign)
            "0000:08:57:01\nIn1 On 50 50",  # multi-line junk
            "٠١٢٣:٠٠:٠٠:٠٠",  # Arabic-Indic digits (U+0660-0663) — re.ASCII rejects
            "００００:０８:５７:０１",  # full-width digits (U+FF10-FF19) — re.ASCII rejects
        ],
    )
    def test_malformed_raises_parse_error(self, raw):
        with pytest.raises(ParseError):
            parse(raw)

    @pytest.mark.parametrize(
        "raw",
        [
            "1000000000:00:00:00",  # days exceed timedelta.max (999,999,999)
            "0000:99999999999:00:00",  # hours overflow C long in timedelta
            "9" * 4301 + ":00:00:00",  # exceeds CPython int-from-string limit
        ],
    )
    def test_out_of_range_raises_parse_error(self, raw):
        # Structurally valid (regex matches) but too large to build a timedelta;
        # must surface as ParseError, not a raw ValueError / OverflowError.
        with pytest.raises(ParseError):
            parse(raw)

    def test_parse_error_is_library_exception(self):
        # The contract is a *library-defined* exception, not a bare ValueError.
        assert issubclass(ParseError, BlustreamError)
        with pytest.raises(BlustreamError):
            parse("not-an-uptime")

    def test_empty_message_mentions_empty(self):
        with pytest.raises(ParseError, match="empty"):
            parse("")

    def test_error_prefix_message_distinguished_from_malformed(self):
        with pytest.raises(ParseError, match="error"):
            parse("[ERROR]Invalid Command")

    def test_lowercase_error_prefix_detected(self):
        # execute_command matches [ERROR] case-insensitively; the parser should
        # too, so a lowercase device error gets the device-error message.
        with pytest.raises(ParseError, match="error"):
            parse("[error]Invalid Command")
