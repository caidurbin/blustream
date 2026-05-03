"""Result formatters for DMP168 commands."""

import json
from typing import Any

from bluestream.base.commands import RenderContext

OUTPUT_MIX_MODE_NAMES = [
    "None",
    "Swap",
    "Mono L+R",
    "Mono All L",
    "Mono All R",
    "Mono L-R",
    "Mono R-L",
]


def format_status(result: Any, ctx: RenderContext) -> str:
    if ctx.json:
        return json.dumps(
            {
                "power": result.power,
                "baud": result.baud,
                "level_unit": result.level_unit,
                "auto_standby_time": result.auto_standby_time,
                "dsp_usage": result.dsp_usage,
                "fade": result.fade,
                "temperature": result.temperature,
                "uptime": result.uptime,
                "firmware_version": result.firmware_version,
                "inputs": [
                    {
                        "port": inp.port,
                        "lock": inp.lock,
                        "gain_l": inp.gain_l,
                        "gain_r": inp.gain_r,
                        "mute_l": inp.mute_l,
                        "mute_r": inp.mute_r,
                    }
                    for inp in result.inputs
                ],
                "routing": [
                    {
                        "output": r.output,
                        "channel": r.channel,
                        "from_input": r.from_input,
                    }
                    for r in result.routing
                ],
            },
            indent=2,
        )

    lines = [
        f"Power: {result.power}",
        f"Baud: {result.baud}",
        f"Level Unit: {result.level_unit}",
        f"Auto Standby: {result.auto_standby_time} mins",
        f"DSP Usage: {result.dsp_usage}%",
        f"Fade: {'On' if result.fade else 'Off'}",
        f"Temperature: {result.temperature}°C",
        f"Uptime: {result.uptime}",
        f"Firmware: {result.firmware_version}",
        "",
        "Input Settings:",
    ]
    for inp in result.inputs:
        lines.append(
            f"  In{inp.port}: Gain L={inp.gain_l} R={inp.gain_r}, "
            f"Mute L={'On' if inp.mute_l else 'Off'} R={'On' if inp.mute_r else 'Off'}, "
            f"Lock={'On' if inp.lock else 'Off'}"
        )
    lines.append("")
    lines.append("Output Routing:")
    for r in result.routing:
        if r.from_input:
            lines.append(f"  Out{r.output} {r.channel}: From In{r.from_input}")
        else:
            lines.append(f"  Out{r.output} {r.channel}: Not routed")
    return "\n".join(lines)


def format_preset_status(result: Any, ctx: RenderContext) -> str:
    if ctx.json:
        return json.dumps(
            {
                "preset_number": result.preset_number,
                "exists": result.exists,
                "description": result.description,
            },
            indent=2,
        )

    lines = [f"Preset {result.preset_number}: {'Exists' if result.exists else 'Not found'}"]
    if result.description:
        lines.append(f"Description: {result.description}")
    return "\n".join(lines)
