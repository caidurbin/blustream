"""The STATUS integrity check: clean dumps pass, corrupted ones raise ParseError."""

from __future__ import annotations

from pathlib import Path

import pytest

from blustream.base.exceptions import ParseError
from blustream.devices.dmp168 import status_parser
from blustream.devices.dmp168.parser import DMP168Parser
from blustream.devices.dmp168.status_integrity import check
from tests.sim.matrix import RECORDINGS, has_binary_frame, recording, status_dumps

ROOT = Path(__file__).resolve().parents[1]

CLEAN_FIXTURES = sorted(
    [
        *(ROOT / "spec" / "vectors" / "fixtures").glob("*.txt"),
        *(ROOT / "tests" / "fixtures").glob("*.txt"),
        *RECORDINGS.glob("p*_A_STATUS_*.bin"),
    ]
)


def _passive_dumps(corrupted: bool) -> list:
    """Each broadcast STATUS dump in the passive captures, clean or corrupted."""
    return [
        pytest.param(dump, id=f"{capture}#{index}")
        for capture in ("passive_p8000_180s.bin", "passive_p23_180s.bin")
        for index, dump in enumerate(status_dumps(capture))
        if has_binary_frame(dump) == corrupted
    ]


CLEAN_PASSIVE = _passive_dumps(corrupted=False)
CORRUPTED_PASSIVE = _passive_dumps(corrupted=True)

LIVE_STATUS = recording("p8000_A_STATUS_2.bin").decode("utf-8")


def _both_parsers_reject(text: str) -> None:
    with pytest.raises(ParseError):
        DMP168Parser.parse_status(text)
    with pytest.raises(ParseError):
        status_parser.parse(text)


@pytest.mark.parametrize("path", CLEAN_FIXTURES, ids=lambda p: p.name)
def test_clean_fixture_passes(path):
    check(path.read_bytes().decode("utf-8"))


@pytest.mark.parametrize("dump", CLEAN_PASSIVE)
def test_clean_broadcast_dump_passes(dump):
    check(dump.decode("utf-8"))


def test_captures_hold_corrupted_dumps():
    assert len(CORRUPTED_PASSIVE) == 4


@pytest.mark.parametrize("dump", CORRUPTED_PASSIVE)
def test_corrupted_broadcast_dump_is_rejected(dump):
    _both_parsers_reject(dump.decode("utf-8", "replace"))


def test_binary_frame_is_rejected():
    frame = b"\xaaT\x00\x09\x07Out1 L\xa5".decode("utf-8", "replace")
    text = LIVE_STATUS.replace("Output EQ Status", frame + "Output EQ Status")
    with pytest.raises(ParseError, match="non-text character"):
        check(text)


def test_control_byte_is_rejected():
    text = LIVE_STATUS.replace("Matrix Config Status", "Matrix\x00 Config Status")
    with pytest.raises(ParseError, match="non-text character"):
        check(text)


@pytest.mark.parametrize(
    ("clean", "damaged"),
    [
        pytest.param(
            "[4000 ,0.0  ][20000,off ]\r\nOut2 L",
            "[4000 ,00,off ]\r\nOut2 L",
            id="eq-band-short",
        ),
        pytest.param("[20000,off ]\r\nOut4 R", "[20000,offOut4 R", id="eq-rows-joined"),
        pytest.param(
            "In3     On   100 100  Off Off  0   0",
            "In3     On   100",
            id="input-row-truncated",
        ),
        pytest.param("Out6 L        None", "Out6 L", id="routing-source-missing"),
        pytest.param(
            "Out2 R        In2 R", "Out2         In2 R", id="routing-channel-missing"
        ),
        pytest.param(
            "Out3    On   100 100  Off Off  110 110",
            "Out3    On   1 0 100  Off Off  110 110",
            id="output-level-split",
        ),
        pytest.param(
            "Out3 L[20   ,off ]", "Out30 [1000 ,0.0  ,3.00 ]", id="spliced-row"
        ),
    ],
)
def test_malformed_row_is_rejected(clean, damaged):
    assert clean in LIVE_STATUS
    text = LIVE_STATUS.replace(clean, damaged, 1)
    with pytest.raises(ParseError, match="malformed row"):
        check(text)
    _both_parsers_reject(text)


@pytest.mark.parametrize(
    "row",
    [
        pytest.param("Out1 L        Bus3 L", id="bus-source"),
        pytest.param("Out1 R        BUS7 R", id="bus-uppercase"),
        pytest.param("In1     Off  -20 -20  On  On   -6  -6", id="negative-levels"),
        pytest.param(
            "Out1    On   75 80  Off On   0   0    0     0     0   0",
            id="output-settings",
        ),
        pytest.param(
            "Out1 L[20   ,12dB][250  ,-3.5 ][500  ,1.0  ,0.70 ][1000 ,0.0  ,3.00 ]"
            "[2000 ,0.0  ,3.00 ][3000 ,0.0  ,3.00 ][4000 ,0.0  ][20000,24dB]",
            id="eq",
        ),
    ],
)
def test_other_valid_row_values_pass(row):
    check(f"{row}\r\n")
