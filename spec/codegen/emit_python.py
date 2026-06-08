"""Emit Python wire-protocol primitives from spec/protocol.yaml.

Run as a module to regenerate ``blustream/devices/dmp168/_generated.py``::

    python -m spec.codegen.emit_python

The function bodies are assembled by the helpers in this module rather than
inside the Jinja template; the template only owns the file-level structure
(header comment, imports, transport constants, joined function blocks).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2

from spec.codegen.spec import REPO_ROOT, load_spec, spec_hash

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_NAME = "python.py.j2"
OUTPUT_PATH = REPO_ROOT / "blustream" / "devices" / "dmp168" / "_generated.py"

INDENT = "    "


# ---------- Python literal rendering ----------


def _py_str(value: str) -> str:
    """Render ``value`` as a Python string literal preserving escapes."""
    # repr produces single-quoted strings which is fine for code generation
    # and survives \r\n / \t round-trips cleanly.
    return repr(value)


def _py_literal(value: Any) -> str:
    """Render ``value`` as a Python literal expression."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return _py_str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_py_literal(v) for v in value) + "]"
    raise TypeError(f"unsupported literal type: {type(value).__name__}")


def _py_type(spec_type: str) -> str:
    """Map a spec type tag to a Python type annotation string.

    'any' (or any unknown tag) renders without an annotation.
    """
    mapping = {
        "int": "int",
        "bool": "bool",
        "str": "str",
    }
    return mapping.get(spec_type, "")


# ---------- Function-shape helpers ----------


def _signature(params: list[dict]) -> str:
    """Build the Python function signature for a parameter list."""
    pieces: list[str] = []
    for p in params:
        ann = _py_type(p["type"])
        annotated = f"{p['name']}: {ann}" if ann else p["name"]
        if "default" in p:
            pieces.append(f"{annotated} = {_py_literal(p['default'])}")
        else:
            pieces.append(annotated)
    return ", ".join(pieces)


def _format_message(message: str, var_name: str) -> str:
    """Translate a ``{value}`` placeholder into an f-string ``{var_name}``."""
    safe = message.replace("{", "{{").replace("}", "}}")
    safe = safe.replace("{{value}}", "{" + var_name + "}")
    return f'f"{safe}"'


def _render_validation(rule: dict) -> list[str]:
    """Render one validation rule as Python source lines (indented body)."""
    name = rule["param"]
    message = _format_message(rule["message"], name)
    lines: list[str] = []
    if "range" in rule:
        lo, hi = rule["range"]
        lines.append(f"{INDENT}if {name} < {lo} or {name} > {hi}:")
        lines.append(f"{INDENT}{INDENT}raise ValidationError({message})")
    elif "choices" in rule:
        choices = _py_literal(list(rule["choices"]))
        lines.append(f"{INDENT}if {name} not in {choices}:")
        lines.append(f"{INDENT}{INDENT}raise ValidationError({message})")
    else:
        raise ValueError(f"unknown validation rule shape: {rule!r}")
    return lines


def _render_wire_step(step: dict) -> list[str]:
    """Render one wire step as Python source lines (indented body)."""
    if "lit" in step and "when_true" in step:
        return [
            f"{INDENT}if {step['when_true']}:",
            f"{INDENT}{INDENT}cmd += {_py_str(step['lit'])}",
        ]
    if "lit" in step and "when_false" in step:
        return [
            f"{INDENT}if not {step['when_false']}:",
            f"{INDENT}{INDENT}cmd += {_py_str(step['lit'])}",
        ]
    if "lit" in step and "when_eq" in step and "when_not_in" in step:
        eq_param, eq_value = next(iter(step["when_eq"].items()))
        ni_param, ni_values = next(iter(step["when_not_in"].items()))
        cond = (
            f"{eq_param} == {_py_literal(eq_value)} "
            f"and {ni_param} not in {_py_literal(list(ni_values))}"
        )
        return [
            f"{INDENT}if {cond}:",
            f"{INDENT}{INDENT}cmd += {_py_str(step['lit'])}",
        ]
    if "lit" in step:
        return [f"{INDENT}cmd += {_py_str(step['lit'])}"]
    if "var" in step:
        var = step["var"]
        prefix = step.get("prefix", "")
        payload = f"{_py_str(prefix)} + str({var})" if prefix else f"str({var})"
        if "when_ne" in step:
            cond_value = _py_literal(step["when_ne"])
            return [
                f"{INDENT}if {var} != {cond_value}:",
                f"{INDENT}{INDENT}cmd += {payload}",
            ]
        return [f"{INDENT}cmd += {payload}"]
    raise ValueError(f"unknown wire step: {step!r}")


def _normalize_wire(wire: Any) -> list[dict]:
    """Accept either a raw string shorthand or a list of step dicts."""
    if isinstance(wire, str):
        return [{"lit": wire}]
    return list(wire or [])


def _render_function(name: str, cmd: dict) -> str:
    """Render one ``format_<name>`` function as a Python source block."""
    params = cmd.get("params") or []
    sig = _signature(params)
    body: list[str] = []
    body.append(f'{INDENT}"""{cmd["description"]}"""')

    for rule in cmd.get("validate") or []:
        body.extend(_render_validation(rule))

    steps = _normalize_wire(cmd.get("wire"))
    only_literal_steps = all("lit" in s and len(s) == 1 for s in steps)
    if only_literal_steps:
        joined = "".join(s["lit"] for s in steps)
        body.append(f"{INDENT}return {_py_str(joined)}")
    else:
        body.append(f'{INDENT}cmd = ""')
        for step in steps:
            body.extend(_render_wire_step(step))
        body.append(f"{INDENT}return cmd")

    header = f"def format_{name}({sig}) -> str:"
    return header + "\n" + "\n".join(body)


def _render_functions(commands: dict) -> str:
    blocks = [_render_function(name, cmd) for name, cmd in commands.items()]
    return "\n\n\n".join(blocks)


# ---------- Template orchestration ----------


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
    return template.render(
        spec_hash=spec_hash(),
        functions_code=_render_functions(spec["commands"]),
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
