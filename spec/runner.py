"""Python ``VectorRunner`` — execute shared formatter vectors against generated code.

Mirrors the Lua runner at ``control4/dmp168/src/vector_runner.lua``. Both
runners take the same shared vectors file (``spec/vectors/formatters.yaml``)
and assert byte-identical wire output. Drift between the two implementations
becomes a CI failure rather than a runtime surprise.

Vector shapes
-------------

Happy path (asserts wire output)::

    - name: power_on emits literal PON
      op: power_on
      args: {}
      expected_wire: "PON"

Range violation (asserts the formatter raises, optionally with a message
substring)::

    - name: output_volume rejects output=10
      op: output_volume
      args: {output: 10, level: 50}
      expected_error: true
      # optional: error_contains: "Output must be between 0-8"
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from blustream.devices.dmp168 import _generated as generated_dmp168


class VectorMismatchError(AssertionError):
    """A formatter vector produced unexpected wire output."""


def _formatter_for(op: str):
    name = f"format_{op}"
    fn = getattr(generated_dmp168, name, None)
    if fn is None:
        raise LookupError(f"Generated module has no formatter '{name}' for op '{op}'")
    return fn


def _run_one(vector: dict[str, Any]) -> None:
    op = vector["op"]
    args = vector.get("args") or {}
    fn = _formatter_for(op)

    if vector.get("expected_error"):
        try:
            actual = fn(**args)
        except Exception as exc:
            substring = vector.get("error_contains")
            if substring is not None and substring not in str(exc):
                raise VectorMismatchError(
                    f"vector {vector.get('name', op)!r}: "
                    f"format_{op}({args}) raised {exc!r}, "
                    f"expected message to contain {substring!r}"
                ) from exc
            return
        raise VectorMismatchError(
            f"vector {vector.get('name', op)!r}: "
            f"format_{op}({args}) -> {actual!r}, expected an error"
        )

    expected = vector["expected_wire"]
    actual = fn(**args)
    if actual != expected:
        raise VectorMismatchError(
            f"vector {vector.get('name', op)!r}: "
            f"format_{op}({args}) -> {actual!r}, expected {expected!r}"
        )


def run_vectors(yaml_path: str | Path) -> int:
    """Run every vector in ``yaml_path``. Returns the count run.

    Raises :class:`VectorMismatchError` on the first failure so CI fails loudly.
    """
    with open(yaml_path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    vectors = doc.get("vectors") or []
    for vector in vectors:
        _run_one(vector)
    return len(vectors)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    path = repo_root / "spec" / "vectors" / "formatters.yaml"
    count = run_vectors(path)
    print(f"OK: {count} vector(s) passed")


if __name__ == "__main__":
    main()
