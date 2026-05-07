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
