"""Tests for the identity resolver."""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from custom_components.blustream.identity import resolve_identity  # noqa: E402


def test_resolve_identity_with_mac_normalizes_to_colon_lowercase() -> None:
    assert resolve_identity("34-D0-B8-21-22-33", "entry-xyz") == "34:d0:b8:21:22:33"


def test_resolve_identity_with_no_separator_mac_normalizes() -> None:
    assert resolve_identity("34D0B8212233", "entry-xyz") == "34:d0:b8:21:22:33"


def test_resolve_identity_with_mixed_case_mac_normalizes() -> None:
    assert resolve_identity("34:d0:B8:21:22:33", "entry-xyz") == "34:d0:b8:21:22:33"


def test_resolve_identity_with_none_mac_falls_back_to_entry_id() -> None:
    assert resolve_identity(None, "entry-xyz") == "entry-xyz"


def test_resolve_identity_with_empty_mac_falls_back_to_entry_id() -> None:
    assert resolve_identity("", "entry-xyz") == "entry-xyz"
