"""Tests for CLI parser generator and kwarg extractor."""

import argparse
from typing import Any

import pytest

from blustream.base.commands import Command, CommandRegistry, Parameter
from blustream.cli.parser import build_parser, extract_kwargs


def _registry(*commands):
    reg = CommandRegistry()
    for cmd in commands:
        reg.register(cmd)
    return reg


class TestBuildParserSubparsers:
    """Subparser presence and naming."""

    def test_subparser_created_for_each_command(self):
        reg = _registry(
            Command(
                name="power_on",
                description="Power on",
                parameters=[],
                handler=lambda **kw: "",
            ),
            Command(
                name="status",
                description="Get status",
                parameters=[],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        assert parser.parse_args(["power-on"]).command == "power_on"
        assert parser.parse_args(["status"]).command == "status"

    def test_snake_case_to_kebab_case(self):
        reg = _registry(
            Command(
                name="output_volume",
                description="Set volume",
                parameters=[],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        assert parser.parse_args(["output-volume"]).command == "output_volume"

    def test_single_word_command_unchanged(self):
        reg = _registry(
            Command(
                name="reboot",
                description="Reboot",
                parameters=[],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        assert parser.parse_args(["reboot"]).command == "reboot"


class TestBuildParserFlags:
    """Flag types, defaults, and choices."""

    def test_int_parameter_with_choices(self):
        reg = _registry(
            Command(
                name="test_cmd",
                description="Test",
                parameters=[
                    Parameter(
                        "output",
                        int,
                        required=True,
                        choices=list(range(9)),
                        help_text="Output channel",
                    ),
                ],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        args = parser.parse_args(["test-cmd", "--output", "3"])
        assert args.output == 3

    def test_str_parameter_with_choices(self):
        reg = _registry(
            Command(
                name="test_cmd",
                description="Test",
                parameters=[
                    Parameter(
                        "channel",
                        str,
                        required=False,
                        default="LR",
                        choices=["L", "R", "LR"],
                    ),
                ],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        args = parser.parse_args(["test-cmd", "--channel", "L"])
        assert args.channel == "L"

    def test_optional_parameter_defaults_to_none(self):
        reg = _registry(
            Command(
                name="test_cmd",
                description="Test",
                parameters=[
                    Parameter(
                        "channel",
                        str,
                        required=False,
                        default="LR",
                        choices=["L", "R", "LR"],
                    ),
                ],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        args = parser.parse_args(["test-cmd"])
        assert args.channel is None

    def test_required_parameter_missing_exits(self):
        reg = _registry(
            Command(
                name="test_cmd",
                description="Test",
                parameters=[
                    Parameter("output", int, required=True),
                ],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        with pytest.raises(SystemExit):
            parser.parse_args(["test-cmd"])

    def test_kebab_case_flag_name(self):
        reg = _registry(
            Command(
                name="route",
                description="Route",
                parameters=[
                    Parameter(
                        "output_channel",
                        str,
                        required=False,
                        default="LR",
                        choices=["L", "R", "LR"],
                    ),
                ],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        args = parser.parse_args(["route", "--output-channel", "L"])
        assert args.output_channel == "L"


class TestBuildParserBoolean:
    """Boolean parameters via BooleanOptionalAction."""

    def test_boolean_mute_flag(self):
        reg = _registry(
            Command(
                name="output_mute",
                description="Set mute",
                parameters=[
                    Parameter("mute", bool, required=True, help_text="Mute toggle"),
                ],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        assert parser.parse_args(["output-mute", "--mute"]).mute is True
        assert parser.parse_args(["output-mute", "--no-mute"]).mute is False

    def test_boolean_optional_with_default(self):
        reg = _registry(
            Command(
                name="test_cmd",
                description="Test",
                parameters=[
                    Parameter("lock", bool, required=False, default=False),
                ],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        args = parser.parse_args(["test-cmd"])
        assert args.lock is False
        args = parser.parse_args(["test-cmd", "--lock"])
        assert args.lock is True


class TestBuildParserRelative:
    """Mutex groups for supports_relative=True parameters."""

    def test_absolute_value(self):
        reg = _registry(
            Command(
                name="output_volume",
                description="Set volume",
                parameters=[
                    Parameter(
                        "level",
                        Any,
                        required=True,
                        supports_relative=True,
                        help_text="Volume level",
                    ),
                ],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        args = parser.parse_args(["output-volume", "--level", "75"])
        assert args.level == 75

    def test_increase_flag(self):
        reg = _registry(
            Command(
                name="output_volume",
                description="Set volume",
                parameters=[
                    Parameter("level", Any, required=True, supports_relative=True),
                ],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        args = parser.parse_args(["output-volume", "--increase-level"])
        assert args.increase_level is True
        assert args.decrease_level is False

    def test_decrease_flag(self):
        reg = _registry(
            Command(
                name="output_volume",
                description="Set volume",
                parameters=[
                    Parameter("level", Any, required=True, supports_relative=True),
                ],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        args = parser.parse_args(["output-volume", "--decrease-level"])
        assert args.decrease_level is True
        assert args.increase_level is False

    def test_mutex_group_required_when_param_required(self):
        reg = _registry(
            Command(
                name="output_volume",
                description="Set volume",
                parameters=[
                    Parameter("level", Any, required=True, supports_relative=True),
                ],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        with pytest.raises(SystemExit):
            parser.parse_args(["output-volume"])

    def test_mutex_group_rejects_both_increase_and_decrease(self):
        reg = _registry(
            Command(
                name="output_volume",
                description="Set volume",
                parameters=[
                    Parameter("level", Any, required=True, supports_relative=True),
                ],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg)
        with pytest.raises(SystemExit):
            parser.parse_args(["output-volume", "--increase-level", "--decrease-level"])


class TestBuildParserParents:
    """build_parser with parent parsers."""

    def test_inherits_parent_flags(self):
        parent = argparse.ArgumentParser(add_help=False)
        parent.add_argument("--host", default="localhost")
        reg = _registry(
            Command(
                name="status",
                description="Status",
                parameters=[],
                handler=lambda **kw: "",
            ),
        )
        parser = build_parser(reg, parents=[parent])
        args = parser.parse_args(["--host", "192.0.2.1", "status"])
        assert args.host == "192.0.2.1"
        assert args.command == "status"


class TestExtractKwargs:
    """Tests for extract_kwargs function."""

    def test_basic_extraction(self):
        cmd = Command(
            name="test_cmd",
            description="Test",
            parameters=[
                Parameter("output", int, required=True),
                Parameter("level", int, required=True),
            ],
            handler=lambda **kw: "",
        )
        ns = argparse.Namespace(command="test_cmd", output=3, level=75)
        assert extract_kwargs(ns, cmd) == {"output": 3, "level": 75}

    def test_increase_translates_to_plus(self):
        cmd = Command(
            name="output_volume",
            description="Set volume",
            parameters=[
                Parameter("level", Any, required=True, supports_relative=True),
            ],
            handler=lambda **kw: "",
        )
        ns = argparse.Namespace(
            command="output_volume",
            level=None,
            increase_level=True,
            decrease_level=False,
        )
        assert extract_kwargs(ns, cmd) == {"level": "+"}

    def test_decrease_translates_to_minus(self):
        cmd = Command(
            name="output_volume",
            description="Set volume",
            parameters=[
                Parameter("level", Any, required=True, supports_relative=True),
            ],
            handler=lambda **kw: "",
        )
        ns = argparse.Namespace(
            command="output_volume",
            level=None,
            increase_level=False,
            decrease_level=True,
        )
        assert extract_kwargs(ns, cmd) == {"level": "-"}

    def test_absolute_value_for_relative_param(self):
        cmd = Command(
            name="output_volume",
            description="Set volume",
            parameters=[
                Parameter("level", Any, required=True, supports_relative=True),
            ],
            handler=lambda **kw: "",
        )
        ns = argparse.Namespace(
            command="output_volume",
            level=75,
            increase_level=False,
            decrease_level=False,
        )
        assert extract_kwargs(ns, cmd) == {"level": 75}

    def test_omits_none_optional_params(self):
        cmd = Command(
            name="test_cmd",
            description="Test",
            parameters=[
                Parameter("output", int, required=True),
                Parameter("channel", str, required=False, default="LR"),
            ],
            handler=lambda **kw: "",
        )
        ns = argparse.Namespace(command="test_cmd", output=1, channel=None)
        assert extract_kwargs(ns, cmd) == {"output": 1}

    def test_includes_explicitly_set_optional_params(self):
        cmd = Command(
            name="test_cmd",
            description="Test",
            parameters=[
                Parameter("output", int, required=True),
                Parameter("channel", str, required=False, default="LR"),
            ],
            handler=lambda **kw: "",
        )
        ns = argparse.Namespace(command="test_cmd", output=1, channel="L")
        assert extract_kwargs(ns, cmd) == {"output": 1, "channel": "L"}
