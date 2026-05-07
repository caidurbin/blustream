"""Emit Lua wire-protocol primitives from spec/protocol.yaml.

Run as a module to regenerate ``control4/dmp168/src/generated.lua``::

    python -m spec.codegen.emit_lua

Each generated function takes a single ``args`` table (Lua's idiomatic
keyword-args), reads named entries, applies defaults, runs validation, and
returns the wire payload string. Mirrors emit_python.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2

from spec.codegen.spec import REPO_ROOT, load_spec, spec_hash

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_NAME = "lua.lua.j2"
OUTPUT_PATH = REPO_ROOT / "control4" / "dmp168" / "src" / "generated.lua"

INDENT = "    "


_LUA_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


# ---------- Lua literal rendering ----------


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


def _lua_literal(value: Any) -> str:
    """Render ``value`` as a Lua literal expression."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return _lua_str(value)
    raise TypeError(f"unsupported lua literal type: {type(value).__name__}")


def _in_set_expr(var: str, values: list[Any]) -> str:
    """Build a Lua expression equivalent to ``var in values``."""
    parts = [f"{var} == {_lua_literal(v)}" for v in values]
    return "(" + " or ".join(parts) + ")"


# ---------- Validation rendering ----------


def _format_message_lua(message: str, var_name: str) -> str:
    """Translate a ``{value}`` placeholder into a Lua concat with tostring()."""
    if "{value}" not in message:
        return _lua_str(message)
    before, after = message.split("{value}", 1)
    parts: list[str] = []
    if before:
        parts.append(_lua_str(before))
    parts.append(f"tostring({var_name})")
    if after:
        parts.append(_lua_str(after))
    return " .. ".join(parts)


def _render_validation_lua(rule: dict) -> list[str]:
    name = rule["param"]
    message = _format_message_lua(rule["message"], name)
    lines: list[str] = []
    if "range" in rule:
        lo, hi = rule["range"]
        lines.append(f"{INDENT}if {name} < {lo} or {name} > {hi} then")
        lines.append(f"{INDENT}{INDENT}error({message})")
        lines.append(f"{INDENT}end")
    elif "choices" in rule:
        lines.append(
            f"{INDENT}if not {_in_set_expr(name, list(rule['choices']))} then"
        )
        lines.append(f"{INDENT}{INDENT}error({message})")
        lines.append(f"{INDENT}end")
    else:
        raise ValueError(f"unknown validation rule shape: {rule!r}")
    return lines


# ---------- Wire-step rendering ----------


def _render_wire_step_lua(step: dict) -> list[str]:
    if "lit" in step and "when_true" in step:
        return [
            f"{INDENT}if {step['when_true']} then",
            f"{INDENT}{INDENT}cmd = cmd .. {_lua_str(step['lit'])}",
            f"{INDENT}end",
        ]
    if "lit" in step and "when_false" in step:
        return [
            f"{INDENT}if not {step['when_false']} then",
            f"{INDENT}{INDENT}cmd = cmd .. {_lua_str(step['lit'])}",
            f"{INDENT}end",
        ]
    if "lit" in step and "when_eq" in step and "when_not_in" in step:
        eq_param, eq_value = next(iter(step["when_eq"].items()))
        ni_param, ni_values = next(iter(step["when_not_in"].items()))
        cond = (
            f"{eq_param} == {_lua_literal(eq_value)} "
            f"and not {_in_set_expr(ni_param, list(ni_values))}"
        )
        return [
            f"{INDENT}if {cond} then",
            f"{INDENT}{INDENT}cmd = cmd .. {_lua_str(step['lit'])}",
            f"{INDENT}end",
        ]
    if "lit" in step:
        return [f"{INDENT}cmd = cmd .. {_lua_str(step['lit'])}"]
    if "var" in step:
        var = step["var"]
        prefix = step.get("prefix", "")
        payload = (
            f"{_lua_str(prefix)} .. tostring({var})"
            if prefix
            else f"tostring({var})"
        )
        if "when_ne" in step:
            return [
                f"{INDENT}if {var} ~= {_lua_literal(step['when_ne'])} then",
                f"{INDENT}{INDENT}cmd = cmd .. {payload}",
                f"{INDENT}end",
            ]
        return [f"{INDENT}cmd = cmd .. {payload}"]
    raise ValueError(f"unknown wire step: {step!r}")


def _normalize_wire(wire: Any) -> list[dict]:
    if isinstance(wire, str):
        return [{"lit": wire}]
    return list(wire or [])


# ---------- Function rendering ----------


def _render_args_unpack(params: list[dict]) -> list[str]:
    """Read each parameter from ``args`` and apply defaults."""
    lines: list[str] = []
    for p in params:
        name = p["name"]
        lines.append(f"{INDENT}local {name} = args.{name}")
        if "default" in p:
            default = _lua_literal(p["default"])
            if default != "nil":
                lines.append(
                    f"{INDENT}if {name} == nil then {name} = {default} end"
                )
    return lines


def _render_function_lua(name: str, cmd: dict) -> str:
    params = cmd.get("params") or []
    body: list[str] = []
    body.append(f"{INDENT}-- {cmd['description']}")
    body.append(f"{INDENT}args = args or {{}}")
    body.extend(_render_args_unpack(params))

    for rule in cmd.get("validate") or []:
        body.extend(_render_validation_lua(rule))

    steps = _normalize_wire(cmd.get("wire"))
    only_literal_steps = all("lit" in s and len(s) == 1 for s in steps)
    if only_literal_steps:
        joined = "".join(s["lit"] for s in steps)
        body.append(f"{INDENT}return {_lua_str(joined)}")
    else:
        body.append(f'{INDENT}local cmd = ""')
        for step in steps:
            body.extend(_render_wire_step_lua(step))
        body.append(f"{INDENT}return cmd")

    header = f"function M.format_{name}(args)"
    return header + "\n" + "\n".join(body) + "\nend"


def _render_functions_lua(commands: dict) -> str:
    blocks = [_render_function_lua(name, cmd) for name, cmd in commands.items()]
    return "\n\n".join(blocks)


# ---------- Template orchestration ----------


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
    return template.render(
        spec_hash=spec_hash(),
        functions_code=_render_functions_lua(spec["commands"]),
        **spec,
    )


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
