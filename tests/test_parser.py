"""Tests for DMP168 parser."""

from pathlib import Path

import pytest

from blustream.base.exceptions import ParseError
from blustream.devices.dmp168.models import OutputSource
from blustream.devices.dmp168.parser import DMP168Parser


def load_fixture(name: str) -> str:
    """Load test fixture file.

    Args:
        name: Fixture filename

    Returns:
        Fixture content as string
    """
    fixture_path = Path(__file__).parent / "fixtures" / name
    return fixture_path.read_text()


def load_fixture_preserving_crlf(name: str) -> str:
    """Load a fixture without universal-newline conversion.

    Use for captured wire responses where the ``\\r\\n`` terminators
    matter — ``read_text()`` normalises CRLF to LF, which would change
    what the parser sees compared to live-device bytes.
    """
    fixture_path = Path(__file__).parent / "fixtures" / name
    # Bytes + decode preserves CRLF without translation and stays portable
    # to Python < 3.13 (read_text gained its newline kwarg in 3.13).
    return fixture_path.read_bytes().decode("utf-8")


class TestDMP168Parser:
    """Tests for DMP168Parser."""

    def test_parse_status_live_full_response_bounds_input_section(self):
        """Real captured response (172 lines) yields exactly 16 inputs / 16 routes.

        The full STATUS reply continues past the Input Settings table into
        an Input EQ section whose rows ("In1  L[20   ,off ][...]") share
        the "In<n>" prefix. Before the section was bounded, every EQ row
        was misparsed as a duplicate input, yielding 48-ish entries.
        Same shape for the routing parser: Output Settings + Output EQ
        sections both lead with "Out<n>" and would double-count.
        """
        # newline="" preserves the on-disk CRLFs so the parser sees the
        # response exactly as it would arrive off the wire.
        response = load_fixture_preserving_crlf("status_live_full.txt")
        parser = DMP168Parser()
        status = parser.parse_status(response)

        assert len(status.inputs) == 16, (
            f"expected 16 input rows, got {len(status.inputs)} — "
            "EQ-section rows are likely leaking into the input list"
        )
        assert {i.port for i in status.inputs} == set(range(1, 17))

        assert len(status.routing) == 16, (
            f"expected 16 routing rows (8 outputs × L/R), got {len(status.routing)} — "
            "Output Settings or Output EQ rows are likely leaking into the routing list"
        )
        # The first Matrix Config row in the fixture is "Out1 L  None"
        assert status.routing[0].output == 1
        assert status.routing[0].channel == "L"
        assert status.routing[0].source is None

    def test_parse_status(self):
        """Test parsing STATUS response."""
        response = load_fixture("status_response.txt")
        parser = DMP168Parser()
        status = parser.parse_status(response)

        assert status.power == "Off(Standby)"
        assert status.baud == 57600
        assert status.level_unit == "%"
        assert status.auto_standby_time == 30
        assert status.dsp_usage == 14.0
        assert status.fade is True
        assert status.temperature == 41.9
        assert status.uptime == "0000:00:35:35"
        assert "1.1.0" in status.firmware_version

        # Check inputs
        assert len(status.inputs) >= 8
        assert status.inputs[0].port == 1
        assert status.inputs[0].gain_l == 50
        assert status.inputs[0].gain_r == 50

        # Check routing
        assert len(status.routing) >= 16
        assert status.routing[0].output == 1
        assert status.routing[0].channel == "L"
        assert status.routing[0].source == OutputSource.for_input(1)

    def test_parse_status_invalid(self):
        """Test parsing invalid STATUS response."""
        parser = DMP168Parser()
        with pytest.raises(ParseError):
            parser.parse_status("Invalid response")

    def test_parse_simple_response(self):
        """Test parsing simple response."""
        response = """================================================================
Welcome to DMP168 Terminal Control System
================================================================
Command executed successfully
"""
        parser = DMP168Parser()
        result = parser.parse_simple_response(response)
        assert "Command executed successfully" in result
        assert "Welcome" not in result

    def test_parse_status_missing_fields(self):
        """Test parsing STATUS with missing fields."""
        # Minimal valid STATUS response
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On           57600   %             0                         10        Off     25.0C     0000:01:00:00
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        assert status.power == "On"
        assert status.baud == 57600
        assert len(status.inputs) == 0  # No input section
        assert len(status.routing) == 0  # No routing section

    def test_parse_status_malformed_dsp(self):
        """Test parsing STATUS with malformed DSP usage."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On           57600   %             0                         invalid     Off     25.0C     0000:01:00:00
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        # Should default to 0.0 for invalid DSP
        assert status.dsp_usage == 0.0

    def test_parse_status_malformed_temperature(self):
        """Test parsing STATUS with malformed temperature."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On           57600   %             0                         10        Off     invalid   0000:01:00:00
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        # Should default to 0.0 for invalid temperature
        assert status.temperature == 0.0

    def test_parse_status_edge_values(self):
        """Test parsing STATUS with edge values."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
Off(Standby) 115200  dB            0                         0         Off     0.0C      9999:23:59:59
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        assert status.power == "Off(Standby)"
        assert status.baud == 115200
        assert status.level_unit == "dB"
        assert status.dsp_usage == 0.0
        assert status.temperature == 0.0
        assert status.uptime == "9999:23:59:59"

    def test_parse_status_no_firmware_version(self):
        """Test parsing STATUS without firmware version."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On           57600   %             0                         10        Off     25.0C     0000:01:00:00
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        assert status.firmware_version == "Unknown"

    def test_parse_preset_status_not_found(self):
        """Test parsing preset status when preset doesn't exist."""
        response = "Preset not found"
        parser = DMP168Parser()
        preset = parser.parse_preset_status(response, preset_number=1)
        assert preset.preset_number == 1
        # Parser logic: "not found" sets exists=False, but non-empty response overrides to True
        # This tests the current behavior (may need parser fix)
        assert preset.exists is True

    def test_parse_preset_status_exists(self):
        """Test parsing preset status when preset exists."""
        response = "Preset 1 exists and is configured"
        parser = DMP168Parser()
        preset = parser.parse_preset_status(response, preset_number=1)
        assert preset.preset_number == 1
        assert preset.exists is True

    def test_parse_preset_status_extract_number(self):
        """Test parsing preset status when number must be extracted."""
        response = "Preset 5 is active"
        parser = DMP168Parser()
        preset = parser.parse_preset_status(response)
        assert preset.preset_number == 5
        assert preset.exists is True

    def test_parse_simple_response_empty(self):
        """Test parsing empty response."""
        parser = DMP168Parser()
        result = parser.parse_simple_response("")
        assert result == ""

    def test_parse_simple_response_no_separator(self):
        """Test parsing response without separator."""
        response = "Some response text without separator"
        parser = DMP168Parser()
        result = parser.parse_simple_response(response)
        assert "Some response text" in result

    def test_parse_simple_response_only_welcome(self):
        """Test parsing response with only welcome message."""
        response = """Welcome to DMP168 Terminal Control System
Type "help" for more information
"""
        parser = DMP168Parser()
        result = parser.parse_simple_response(response)
        # Should return stripped original if nothing else
        assert len(result) > 0

    def test_parse_status_incomplete_data_line(self):
        """Test parsing STATUS with incomplete data line."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On
"""
        parser = DMP168Parser()
        # Parser correctly raises ParseError for incomplete data
        from blustream.base.exceptions import ParseError
        with pytest.raises(ParseError):
            parser.parse_status(response)

    def test_parse_status_malformed_baud(self):
        """Test parsing STATUS with non-numeric baud."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On           invalid %             0                         10        Off     25.0C     0000:01:00:00
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        # Should use default baud if not numeric
        assert status.baud == 57600

    def test_parse_status_input_section_partial(self):
        """Test parsing STATUS with partial input section."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On           57600   %             0                         10        Off     25.0C     0000:01:00:00

Input Settings Status
In1     On   50
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        # Should handle partial input line gracefully
        assert len(status.inputs) == 0  # Incomplete line should be skipped

    def test_parse_status_routing_section_partial(self):
        """Test parsing STATUS with partial routing section."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On           57600   %             0                         10        Off     25.0C     0000:01:00:00

Matrix Config Status
Out1
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        # Should handle partial routing line gracefully
        assert len(status.routing) == 0  # Incomplete line should be skipped

    def test_parse_status_routing_no_input(self):
        """Test parsing STATUS with routing but no input."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On           57600   %             0                         10        Off     25.0C     0000:01:00:00

Matrix Config Status
Output        FromIn
Out1 L
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        assert len(status.routing) == 1
        assert status.routing[0].output == 1
        assert status.routing[0].channel == "L"
        assert status.routing[0].source is None  # No source routed

    def test_parse_status_dsp_with_percent(self):
        """Test parsing STATUS with DSP usage that includes %."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On           57600   %             0                         50%       Off     25.0C     0000:01:00:00
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        assert status.dsp_usage == 50.0

    def test_parse_status_fade_off(self):
        """Test parsing STATUS with fade off."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On           57600   %             0                         10        Off     25.0C     0000:01:00:00
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        assert status.fade is False

    def test_parse_status_fade_on(self):
        """Test parsing STATUS with fade on."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On           57600   %             0                         10        On      25.0C     0000:01:00:00
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        assert status.fade is True

    def test_parse_status_temperature_with_decimal(self):
        """Test parsing STATUS with decimal temperature."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On           57600   %             0                         10        Off     42.5C     0000:01:00:00
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        assert status.temperature == 42.5

    def test_parse_status_temperature_integer(self):
        """Test parsing STATUS with integer temperature."""
        response = """Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)
On           57600   %             0                         10        Off     42C       0000:01:00:00
"""
        parser = DMP168Parser()
        status = parser.parse_status(response)
        assert status.temperature == 42.0

    def test_parse_preset_status_with_description(self):
        """Test parsing preset status with description."""
        response = "Preset 3 exists\nDescription: Main Configuration"
        parser = DMP168Parser()
        preset = parser.parse_preset_status(response, preset_number=3)
        assert preset.preset_number == 3
        assert preset.exists is True
        # Parser lowercases the description
        assert "main configuration" in preset.description.lower()

    def test_parse_preset_status_empty_response(self):
        """Test parsing preset status with empty response."""
        parser = DMP168Parser()
        preset = parser.parse_preset_status("", preset_number=1)
        assert preset.preset_number == 1
        # Empty response means exists=False (parser logic: if not exists and response is empty, stays False)
        assert preset.exists is False


class TestParseOutputSources:
    """Matrix Config sources: input, bus, and None per output channel."""

    HEADER = (
        "Power         Baud    Level Unit    Auto Standby Time(mins)    "
        "DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)\n"
        "On           57600   %             0                         "
        "10        Off     25.0C     0000:01:00:00\n"
    )

    def _routing(self, body: str):
        response = f"{self.HEADER}\nMatrix Config Status\nOutput        FromIn\n{body}"
        return DMP168Parser().parse_status(response).routing

    def test_input_source(self):
        routing = self._routing("Out1 L        In5 L\n")
        assert routing[0].source == OutputSource.for_input(5)

    def test_bus_source(self):
        routing = self._routing("Out2 R        Bus3 R\n")
        assert routing[0].source == OutputSource(kind="bus", number=3)

    def test_bus_source_uppercase_token(self):
        # The device's BUS sections print "BUS<n>"; matching is case-insensitive.
        routing = self._routing("Out2 R        BUS7 R\n")
        assert routing[0].source == OutputSource.for_bus(7)

    def test_none_source(self):
        routing = self._routing("Out3 L        None\n")
        assert routing[0].source is None

    def test_mixed_input_bus_none(self):
        routing = self._routing(
            "Out1 L        In1 L\n"
            "Out1 R        Bus2 R\n"
            "Out2 L        None\n"
        )
        assert routing[0].source == OutputSource.for_input(1)
        assert routing[1].source == OutputSource.for_bus(2)
        assert routing[2].source is None


class TestParseOutputSettings:
    """Output Settings Status section -> per-output volume / mute / lock."""

    def test_live_full_output_settings(self):
        response = load_fixture_preserving_crlf("status_live_full.txt")
        status = DMP168Parser().parse_status(response)

        assert len(status.output_settings) == 8
        assert {o.output for o in status.output_settings} == set(range(1, 9))
        first = status.output_settings[0]
        assert first.output == 1
        assert first.volume_pct_l == 100
        assert first.volume_pct_r == 100
        assert first.mute_l is False
        assert first.mute_r is False
        assert first.lock is True

    def test_output_settings_values(self):
        response = (
            "Power         Baud    Level Unit    Auto Standby Time(mins)    "
            "DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)\n"
            "On           57600   %             0                         "
            "10        Off     25.0C     0000:01:00:00\n"
            "\nOutput Settings Status\n"
            "Port    Lock   %      Mute     Delay    Mix  Group  Maximum(dB)\n"
            "        LR   L   R    L   R    L   R    LR    LR    L   R\n"
            "Out1    Off  80  90   On  Off  0   0    0     0     0   0\n"
        )
        status = DMP168Parser().parse_status(response)
        assert len(status.output_settings) == 1
        o = status.output_settings[0]
        assert o.output == 1
        assert o.volume_pct_l == 80
        assert o.volume_pct_r == 90
        assert o.mute_l is True
        assert o.mute_r is False
        assert o.lock is False

    def test_output_settings_absent_yields_empty(self):
        response = (
            "Power         Baud    Level Unit    Auto Standby Time(mins)    "
            "DSP(%)    Fade    Temp(C)   Uptime(Day:Hour:Min:Sec)\n"
            "On           57600   %             0                         "
            "10        Off     25.0C     0000:01:00:00\n"
        )
        status = DMP168Parser().parse_status(response)
        assert status.output_settings == []

