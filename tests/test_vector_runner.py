"""Tests for the Python ``VectorRunner`` (`spec.runner`).

The runner mirrors the Lua side; both consume `spec/vectors/formatters.yaml`.
A failure here flags drift between the spec, the generated Python primitives,
and the shared vector contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spec import runner
from spec.codegen.spec import REPO_ROOT


def test_committed_formatter_vectors_pass():
    path = REPO_ROOT / "spec" / "vectors" / "formatters.yaml"
    count = runner.run_vectors(path)
    assert count >= 1


def test_run_vectors_detects_mismatch(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "vectors:\n"
        "  - name: wrong expectation\n"
        "    op: power_on\n"
        "    args: {}\n"
        "    expected_wire: NOPE\n",
        encoding="utf-8",
    )
    with pytest.raises(runner.VectorMismatchError) as exc:
        runner.run_vectors(bad)
    msg = str(exc.value)
    assert "power_on" in msg
    assert "PON" in msg
    assert "NOPE" in msg


def test_run_vectors_unknown_op_raises(tmp_path: Path):
    bad = tmp_path / "unknown.yaml"
    bad.write_text(
        "vectors:\n"
        "  - name: missing op\n"
        "    op: not_a_real_op\n"
        "    args: {}\n"
        "    expected_wire: x\n",
        encoding="utf-8",
    )
    with pytest.raises(LookupError):
        runner.run_vectors(bad)


def test_run_vectors_empty_file_returns_zero(tmp_path: Path):
    empty = tmp_path / "empty.yaml"
    empty.write_text("vectors: []\n", encoding="utf-8")
    assert runner.run_vectors(empty) == 0
