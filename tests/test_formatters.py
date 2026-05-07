"""Tests for DMP168 formatters and Command.format_result integration."""

import json

import pytest

from blustream.base.commands import Command, RenderContext
from blustream.devices.dmp168.formatters import (
    OUTPUT_MIX_MODE_NAMES,
    format_preset_status,
    format_status,
)
from blustream.devices.dmp168.models import (
    InputSettings,
    OutputRouting,
    PresetStatus,
    SystemStatus,
)


@pytest.fixture
def sample_status():
    return SystemStatus(
        power="On",
        baud=115200,
        level_unit="%",
        auto_standby_time=30,
        dsp_usage=45.2,
        fade=True,
        temperature=47.4,
        uptime="0000:08:57:01",
        firmware_version="1.2.3",
        inputs=[
            InputSettings(port=1, lock=False, gain_l=80, gain_r=80, mute_l=False, mute_r=False),
            InputSettings(port=2, lock=True, gain_l=50, gain_r=60, mute_l=True, mute_r=False),
        ],
        routing=[
            OutputRouting(output=1, channel="L", from_input=1),
            OutputRouting(output=1, channel="R", from_input=2),
            OutputRouting(output=2, channel="L", from_input=None),
        ],
    )


@pytest.fixture
def preset_exists():
    return PresetStatus(preset_number=3, exists=True, description="My Config")


@pytest.fixture
def preset_not_found():
    return PresetStatus(preset_number=5, exists=False)


class TestRenderContext:
    def test_default_json_false(self):
        ctx = RenderContext()
        assert ctx.json is False

    def test_json_true(self):
        ctx = RenderContext(json=True)
        assert ctx.json is True


class TestCommandFormatResult:
    def test_format_result_default_none(self):
        cmd = Command(
            name="test",
            description="test",
            parameters=[],
            handler=lambda **kw: "TEST",
        )
        assert cmd.format_result is None

    def test_format_result_accepts_callable(self):
        def my_formatter(result, ctx):
            return str(result)

        cmd = Command(
            name="test",
            description="test",
            parameters=[],
            handler=lambda **kw: "TEST",
            format_result=my_formatter,
        )
        assert cmd.format_result is my_formatter
        assert cmd.format_result("hello", RenderContext()) == "hello"


class TestFormatStatus:
    def test_human_mode(self, sample_status):
        ctx = RenderContext(json=False)
        result = format_status(sample_status, ctx)

        assert "Power: On" in result
        assert "Baud: 115200" in result
        assert "Level Unit: %" in result
        assert "Auto Standby: 30 mins" in result
        assert "DSP Usage: 45.2%" in result
        assert "Fade: On" in result
        assert "Temperature: 47.4°C" in result
        assert "Uptime: 0000:08:57:01" in result
        assert "Firmware: 1.2.3" in result
        assert "Input Settings:" in result
        assert "In1: Gain L=80 R=80, Mute L=Off R=Off, Lock=Off" in result
        assert "In2: Gain L=50 R=60, Mute L=On R=Off, Lock=On" in result
        assert "Output Routing:" in result
        assert "Out1 L: From In1" in result
        assert "Out1 R: From In2" in result
        assert "Out2 L: Not routed" in result

    def test_json_mode(self, sample_status):
        ctx = RenderContext(json=True)
        result = format_status(sample_status, ctx)
        data = json.loads(result)

        assert data["power"] == "On"
        assert data["baud"] == 115200
        assert data["level_unit"] == "%"
        assert data["auto_standby_time"] == 30
        assert data["dsp_usage"] == 45.2
        assert data["fade"] is True
        assert data["temperature"] == 47.4
        assert data["uptime"] == "0000:08:57:01"
        assert data["firmware_version"] == "1.2.3"
        assert len(data["inputs"]) == 2
        assert data["inputs"][0]["port"] == 1
        assert data["inputs"][0]["lock"] is False
        assert data["inputs"][1]["mute_l"] is True
        assert len(data["routing"]) == 3
        assert data["routing"][0]["from_input"] == 1
        assert data["routing"][2]["from_input"] is None

    def test_human_mode_fade_off(self):
        status = SystemStatus(
            power="Off(Standby)",
            baud=9600,
            level_unit="dB",
            auto_standby_time=0,
            dsp_usage=0.0,
            fade=False,
            temperature=30.0,
            uptime="0000:00:00:00",
            firmware_version="0.0.1",
            inputs=[],
            routing=[],
        )
        ctx = RenderContext(json=False)
        result = format_status(status, ctx)
        assert "Fade: Off" in result
        assert "Power: Off(Standby)" in result

    def test_byte_identical_to_legacy_human(self, sample_status):
        """Regression: formatter output must match legacy CLI format_status."""
        ctx = RenderContext(json=False)
        result = format_status(sample_status, ctx)

        lines = [
            "Power: On",
            "Baud: 115200",
            "Level Unit: %",
            "Auto Standby: 30 mins",
            "DSP Usage: 45.2%",
            "Fade: On",
            "Temperature: 47.4°C",
            "Uptime: 0000:08:57:01",
            "Firmware: 1.2.3",
            "",
            "Input Settings:",
            "  In1: Gain L=80 R=80, Mute L=Off R=Off, Lock=Off",
            "  In2: Gain L=50 R=60, Mute L=On R=Off, Lock=On",
            "",
            "Output Routing:",
            "  Out1 L: From In1",
            "  Out1 R: From In2",
            "  Out2 L: Not routed",
        ]
        expected = "\n".join(lines)
        assert result == expected

    def test_byte_identical_to_legacy_json(self, sample_status):
        """Regression: formatter JSON output must match legacy CLI json.dumps."""
        ctx = RenderContext(json=True)
        result = format_status(sample_status, ctx)

        expected = json.dumps(
            {
                "power": "On",
                "baud": 115200,
                "level_unit": "%",
                "auto_standby_time": 30,
                "dsp_usage": 45.2,
                "fade": True,
                "temperature": 47.4,
                "uptime": "0000:08:57:01",
                "firmware_version": "1.2.3",
                "inputs": [
                    {"port": 1, "lock": False, "gain_l": 80, "gain_r": 80, "mute_l": False, "mute_r": False},
                    {"port": 2, "lock": True, "gain_l": 50, "gain_r": 60, "mute_l": True, "mute_r": False},
                ],
                "routing": [
                    {"output": 1, "channel": "L", "from_input": 1},
                    {"output": 1, "channel": "R", "from_input": 2},
                    {"output": 2, "channel": "L", "from_input": None},
                ],
            },
            indent=2,
        )
        assert result == expected


class TestFormatPresetStatus:
    def test_human_mode_exists(self, preset_exists):
        ctx = RenderContext(json=False)
        result = format_preset_status(preset_exists, ctx)
        assert "Preset 3: Exists" in result
        assert "Description: My Config" in result

    def test_human_mode_not_found(self, preset_not_found):
        ctx = RenderContext(json=False)
        result = format_preset_status(preset_not_found, ctx)
        assert "Preset 5: Not found" in result
        assert "Description" not in result

    def test_json_mode_exists(self, preset_exists):
        ctx = RenderContext(json=True)
        result = format_preset_status(preset_exists, ctx)
        data = json.loads(result)
        assert data["preset_number"] == 3
        assert data["exists"] is True
        assert data["description"] == "My Config"

    def test_json_mode_not_found(self, preset_not_found):
        ctx = RenderContext(json=True)
        result = format_preset_status(preset_not_found, ctx)
        data = json.loads(result)
        assert data["preset_number"] == 5
        assert data["exists"] is False
        assert data["description"] is None

    def test_human_mode_exists_no_description(self):
        preset = PresetStatus(preset_number=1, exists=True)
        ctx = RenderContext(json=False)
        result = format_preset_status(preset, ctx)
        assert "Preset 1: Exists" in result
        assert "Description" not in result

    def test_byte_identical_to_legacy_human_exists(self, preset_exists):
        """Regression: must match legacy CLI preset status output."""
        ctx = RenderContext(json=False)
        result = format_preset_status(preset_exists, ctx)
        expected = "Preset 3: Exists\nDescription: My Config"
        assert result == expected

    def test_byte_identical_to_legacy_human_not_found(self, preset_not_found):
        """Regression: must match legacy CLI preset status output."""
        ctx = RenderContext(json=False)
        result = format_preset_status(preset_not_found, ctx)
        expected = "Preset 5: Not found"
        assert result == expected

    def test_byte_identical_to_legacy_json(self, preset_exists):
        """Regression: must match legacy CLI json output."""
        ctx = RenderContext(json=True)
        result = format_preset_status(preset_exists, ctx)
        expected = json.dumps(
            {
                "preset_number": 3,
                "exists": True,
                "description": "My Config",
            },
            indent=2,
        )
        assert result == expected


class TestOutputMixModeNames:
    def test_mode_names_count(self):
        assert len(OUTPUT_MIX_MODE_NAMES) == 7

    def test_mode_names_values(self):
        assert OUTPUT_MIX_MODE_NAMES[0] == "None"
        assert OUTPUT_MIX_MODE_NAMES[1] == "Swap"
        assert OUTPUT_MIX_MODE_NAMES[2] == "Mono L+R"
        assert OUTPUT_MIX_MODE_NAMES[3] == "Mono All L"
        assert OUTPUT_MIX_MODE_NAMES[4] == "Mono All R"
        assert OUTPUT_MIX_MODE_NAMES[5] == "Mono L-R"
        assert OUTPUT_MIX_MODE_NAMES[6] == "Mono R-L"


class TestCommandRegistrationWiring:
    """Verify DMP168 command registrations have format_result wired up."""

    def test_status_has_format_result(self):
        from blustream.base.commands import CommandRegistry
        from blustream.devices.dmp168.commands import _register_commands

        registry = CommandRegistry()
        _register_commands(registry)
        cmd = registry.get("status")
        assert cmd is not None
        assert cmd.format_result is not None

    def test_preset_status_has_format_result(self):
        from blustream.base.commands import CommandRegistry
        from blustream.devices.dmp168.commands import _register_commands

        registry = CommandRegistry()
        _register_commands(registry)
        cmd = registry.get("preset_status")
        assert cmd is not None
        assert cmd.format_result is not None

    def test_status_format_result_produces_correct_output(self, sample_status):
        from blustream.base.commands import CommandRegistry
        from blustream.devices.dmp168.commands import _register_commands

        registry = CommandRegistry()
        _register_commands(registry)
        cmd = registry.get("status")
        ctx = RenderContext(json=False)
        result = cmd.format_result(sample_status, ctx)
        assert "Power: On" in result
        assert "Input Settings:" in result

    def test_preset_status_format_result_produces_correct_output(self, preset_exists):
        from blustream.base.commands import CommandRegistry
        from blustream.devices.dmp168.commands import _register_commands

        registry = CommandRegistry()
        _register_commands(registry)
        cmd = registry.get("preset_status")
        ctx = RenderContext(json=False)
        result = cmd.format_result(preset_exists, ctx)
        assert "Preset 3: Exists" in result
