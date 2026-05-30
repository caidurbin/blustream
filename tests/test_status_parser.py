"""Shared-fixture parity tests for the pure-function STATUS parser.

Each YAML expected-state file under ``spec/vectors/fixtures/`` is consumed by
both this Python runner and the sibling Lua spec under
``control4/dmp168/spec/status_parser_spec.lua``. Both runners must agree on
every fixture; CI fails the build if either side diverges.
"""

from pathlib import Path

import pytest
import yaml

from blustream.devices.dmp168.status_parser import parse

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "spec" / "vectors" / "fixtures"


def _discover_fixtures():
    return sorted(p.stem for p in FIXTURES_DIR.glob("*.txt"))


@pytest.mark.parametrize("fixture", _discover_fixtures())
def test_status_parser_matches_expected(fixture):
    response = (FIXTURES_DIR / f"{fixture}.txt").read_text()
    expected = yaml.safe_load((FIXTURES_DIR / f"{fixture}.expected.yaml").read_text())

    actual = parse(response)

    assert actual == expected, (
        f"parser output for {fixture} does not match expected state"
    )


def test_all_required_fixtures_present():
    """Issue #16 acceptance: at minimum power_on, sleep, full_routing, partial."""
    fixtures = set(_discover_fixtures())
    required = {
        "status_power_on",
        "status_sleep",
        "status_full_routing",
        "status_partial",
    }
    missing = required - fixtures
    assert not missing, f"missing required fixtures: {sorted(missing)}"


def test_every_fixture_has_expected_yaml():
    for txt in FIXTURES_DIR.glob("*.txt"):
        expected = txt.with_suffix(".expected.yaml")
        assert expected.exists(), f"missing {expected.name} for {txt.name}"


def test_live_full_response_bounds_input_and_routing_sections():
    """Real captured response (172 lines) yields exactly 16 inputs / 16 routes.

    The full STATUS reply continues past the Input Settings table into
    Input EQ, Output Settings, and Output EQ sections — each of which
    has rows beginning with "In<n>" or "Out<n>". The section parsers
    must bound on row shape so EQ / Settings rows aren't misparsed as
    duplicates. Lives outside the parametrized shared-fixture set
    because no Lua sibling consumes it.
    """
    live_fixture = Path(__file__).resolve().parent / "fixtures" / "status_live_full.txt"
    # Bytes + decode preserves CRLF without translation and stays portable
    # to Python < 3.13 (read_text gained its newline kwarg in 3.13).
    response = live_fixture.read_bytes().decode("utf-8")

    actual = parse(response)

    assert len(actual["inputs"]) == 16, (
        f"expected 16 input rows, got {len(actual['inputs'])} — "
        "Input EQ rows likely leaked into the inputs list"
    )
    assert {row["port"] for row in actual["inputs"]} == set(range(1, 17))

    assert len(actual["routing"]) == 16, (
        f"expected 16 routing rows (8 outputs × L/R), got {len(actual['routing'])} — "
        "Output Settings or Output EQ rows likely leaked into the routing list"
    )
