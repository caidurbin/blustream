"""Tests for spec/codegen — emitters, hashing, and the committed output gate.

Per ADR-0007, the committed `_generated.py` and `generated.lua` files MUST
match what running the emitters produces against the current spec. The two
"is fresh" tests below are the in-process equivalent of the CI
`git diff --exit-code` gate — they fail loudly if a developer edits the spec
without regenerating, or hand-edits a generated file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spec.codegen import emit_lua, emit_python
from spec.codegen.spec import REPO_ROOT, load_spec, spec_hash


def test_load_spec_round_trip():
    spec = load_spec()
    assert spec["device"]["name"] == "dmp168"
    assert spec["device"]["firmware_baseline"] == "1.5.0"
    assert spec["transport"]["default_port"] == 8000
    assert spec["transport"]["alternative_port"] == 23
    assert spec["transport"]["terminator"] == "\r\n"
    assert "power_on" in spec["commands"]
    assert spec["commands"]["power_on"]["wire"] == "PON"


def test_spec_hash_is_stable_and_short():
    h1 = spec_hash()
    h2 = spec_hash()
    assert h1 == h2
    assert len(h1) == 16
    int(h1, 16)  # hex-decodable


def test_spec_hash_changes_when_content_changes(tmp_path: Path):
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text("device: {name: x}\n")
    b.write_text("device: {name: y}\n")
    assert spec_hash(a) != spec_hash(b)


def test_emit_python_includes_hash_header_and_formatter():
    src = emit_python.render()
    assert f"Spec hash: {spec_hash()}" in src
    assert "def format_power_on() -> str:" in src
    assert "return 'PON'" in src
    assert "DEFAULT_PORT = 8000" in src
    assert "ALTERNATIVE_PORT = 23" in src
    assert "TERMINATOR = '\\r\\n'" in src


def test_emit_lua_includes_hash_header_and_formatter():
    src = emit_lua.render()
    assert f"Spec hash: {spec_hash()}" in src
    # Zero-arg commands use ``_`` as the unused parameter name so luacheck
    # doesn't flag a discarded ``args`` assignment. Parameterised commands
    # use ``args`` and read keyword fields off it (see format_standby etc).
    assert "function M.format_power_on(_)" in src
    assert "function M.format_standby(args)" in src
    assert 'return "PON"' in src
    assert "M.DEFAULT_PORT = 8000" in src
    assert "M.ALTERNATIVE_PORT = 23" in src
    assert 'M.TERMINATOR = "\\r\\n"' in src


def _stale_msg(rel_path: str, command: str) -> str:
    return (
        f"{rel_path} is stale relative to spec/protocol.yaml. "
        f"Regenerate with: {command}"
    )


def test_committed_python_generated_is_fresh():
    on_disk = (REPO_ROOT / "blustream" / "devices" / "dmp168" / "_generated.py").read_text(
        encoding="utf-8"
    )
    assert on_disk == emit_python.render(), _stale_msg(
        "blustream/devices/dmp168/_generated.py",
        "python -m spec.codegen.emit_python",
    )


def test_committed_lua_generated_is_fresh():
    on_disk = (REPO_ROOT / "control4" / "dmp168" / "src" / "generated.lua").read_text(
        encoding="utf-8"
    )
    assert on_disk == emit_lua.render(), _stale_msg(
        "control4/dmp168/src/generated.lua",
        "python -m spec.codegen.emit_lua",
    )


def test_python_and_lua_share_one_spec_hash():
    py = emit_python.render()
    lua = emit_lua.render()
    h = spec_hash()
    py_line = next(line for line in py.splitlines() if "Spec hash:" in line)
    lua_line = next(line for line in lua.splitlines() if "Spec hash:" in line)
    assert h in py_line and h in lua_line


def test_lua_str_filter_escapes_quotes_and_backslashes():
    # The filter is the load-bearing piece for Lua wire-format correctness;
    # unescaped quotes or backslashes in a `wire:` value would emit broken
    # Lua source. Exercise it directly so a regression here gets a clear
    # signal independent of the spec content.
    f = emit_lua._lua_str
    assert f("PON") == '"PON"'
    assert f('hi"there') == '"hi\\"there"'
    assert f("a\\b") == '"a\\\\b"'
    assert f("\r\n\t") == '"\\r\\n\\t"'


def test_python_str_filter_round_trips_through_eval():
    f = emit_python._py_str
    for value in ["PON", "hi'there", 'hi"there', "a\\b", "\r\n\t"]:
        assert eval(f(value)) == value  # noqa: S307 - test-only


def test_emit_main_writes_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    out_py = tmp_path / "py" / "_generated.py"
    out_lua = tmp_path / "lua" / "generated.lua"
    monkeypatch.setattr(emit_python, "OUTPUT_PATH", out_py)
    monkeypatch.setattr(emit_lua, "OUTPUT_PATH", out_lua)
    emit_python.main()
    emit_lua.main()
    assert out_py.read_text(encoding="utf-8") == emit_python.render()
    assert out_lua.read_text(encoding="utf-8") == emit_lua.render()
