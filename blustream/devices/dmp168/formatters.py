"""Result formatters for DMP168 commands."""

import json
from typing import Any

from blustream.base.commands import RenderContext
from blustream.devices.dmp168.models import SOURCE_BUS

OUTPUT_MIX_MODE_NAMES = (
    "None",
    "Swap",
    "Mono L+R",
    "Mono All L",
    "Mono All R",
    "Mono L-R",
    "Mono R-L",
)


def format_status(result: Any, ctx: RenderContext) -> str:
    if ctx.json:
        # SystemStatus.to_dict() is the single source of the --json shape;
        # delegate so the CLI surface can't drift from the library serializer.
        return json.dumps(result.to_dict(), indent=2)

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
        if r.source is None:
            lines.append(f"  Out{r.output} {r.channel}: Not routed")
        elif r.source.kind == SOURCE_BUS:
            lines.append(f"  Out{r.output} {r.channel}: From Bus{r.source.number}")
        else:
            lines.append(f"  Out{r.output} {r.channel}: From In{r.source.number}")
    if result.output_settings:
        lines.append("")
        lines.append("Output Settings:")
        for o in result.output_settings:
            lines.append(
                f"  Out{o.output}: Vol L={o.volume_pct_l} R={o.volume_pct_r}, "
                f"Mute L={'On' if o.mute_l else 'Off'} R={'On' if o.mute_r else 'Off'}, "
                f"Lock={'On' if o.lock else 'Off'}"
            )
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
