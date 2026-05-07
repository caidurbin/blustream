"""Emit Lua wire-protocol primitives from spec/protocol.yaml.

Run as a module to regenerate ``control4/dmp168/src/generated.lua``::

    python -m spec.codegen.emit_lua
"""

from __future__ import annotations

from pathlib import Path

import jinja2

from spec.codegen.spec import REPO_ROOT, load_spec, spec_hash

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_NAME = "lua.lua.j2"
OUTPUT_PATH = REPO_ROOT / "control4" / "dmp168" / "src" / "generated.lua"

_LUA_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _lua_str(value: str) -> str:
    """Render ``value`` as a Lua double-quoted string literal."""
    out = []
    for ch in value:
        if ch in _LUA_ESCAPES:
            out.append(_LUA_ESCAPES[ch])
        elif ord(ch) < 32:
            out.append(f"\\{ord(ch)}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _build_env() -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
        autoescape=False,
    )
    env.filters["lua_str"] = _lua_str
    return env


def render() -> str:
    """Render the Lua source as a string."""
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
