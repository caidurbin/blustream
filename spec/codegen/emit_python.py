"""Emit Python wire-protocol primitives from spec/protocol.yaml.

Run as a module to regenerate ``blustream/devices/dmp168/_generated.py``::

    python -m spec.codegen.emit_python
"""

from __future__ import annotations

from pathlib import Path

import jinja2

from spec.codegen.spec import REPO_ROOT, load_spec, spec_hash

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_NAME = "python.py.j2"
OUTPUT_PATH = REPO_ROOT / "blustream" / "devices" / "dmp168" / "_generated.py"


def _py_str(value: str) -> str:
    """Render ``value`` as a Python string literal preserving escapes."""
    # repr produces single-quoted strings which is fine for code generation
    # and survives \r\n / \t round-trips cleanly.
    return repr(value)


def _build_env() -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
        autoescape=False,
    )
    env.filters["py_str"] = _py_str
    return env


def render() -> str:
    """Render the Python source as a string."""
    spec = load_spec()
    env = _build_env()
    template = env.get_template(TEMPLATE_NAME)
    return template.render(spec_hash=spec_hash(), **spec)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render(), encoding="utf-8")
    try:
        display = OUTPUT_PATH.relative_to(REPO_ROOT)
    except ValueError:
        display = OUTPUT_PATH
    print(f"Wrote {display}")


if __name__ == "__main__":
    main()
