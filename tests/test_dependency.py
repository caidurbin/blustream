"""Tests for cross-parameter dependency validation."""

import pytest

from bluestream.base.commands import (
    Command,
    CommandRegistry,
    Dependency,
    Parameter,
)
from bluestream.base.exceptions import ValidationError
from bluestream.base.validator import validate


@pytest.fixture
def registry():
    """Registry with commands that exercise dependency scenarios."""
    reg = CommandRegistry()

    # Command with presence-based dependency (string shorthand)
    reg.register(
        Command(
            name="presence_dep",
            description="Command where param B requires param A to be present",
            parameters=[
                Parameter("a", int, required=False, default=None),
                Parameter(
                    "b",
                    int,
                    required=False,
                    default=None,
                    depends_on="a",
                ),
            ],
            handler=lambda **kwargs: "OK",
        )
    )

    # Command with predicate-based dependency (Dependency with when)
    reg.register(
        Command(
            name="predicate_dep",
            description="Command where unit is rejected when level is relative",
            parameters=[
                Parameter("level", str, required=True),
                Parameter(
                    "unit",
                    str,
                    required=False,
                    default=None,
                    choices=["percent", "dB"],
                    depends_on=Dependency(
                        on="level",
                        when=lambda v: isinstance(v, str) and v in ["+", "-"],
                    ),
                ),
            ],
            handler=lambda **kwargs: "OK",
        )
    )

    # Command with multiple dependencies (list)
    reg.register(
        Command(
            name="multi_dep",
            description="Command where param C depends on both A and B",
            parameters=[
                Parameter("a", int, required=False, default=None),
                Parameter("b", int, required=False, default=None),
                Parameter(
                    "c",
                    int,
                    required=False,
                    default=None,
                    depends_on=[
                        Dependency(on="a"),
                        Dependency(on="b"),
                    ],
                ),
            ],
            handler=lambda **kwargs: "OK",
        )
    )

    # Command with both pass-one validation and dependencies
    reg.register(
        Command(
            name="two_pass",
            description="Command with both per-param and dependency checks",
            parameters=[
                Parameter(
                    "level",
                    int,
                    required=True,
                    choices=[1, 2, 3],
                ),
                Parameter(
                    "extra",
                    str,
                    required=False,
                    default=None,
                    depends_on=Dependency(
                        on="level",
                        when=lambda v: v == 99,
                    ),
                ),
            ],
            handler=lambda **kwargs: "OK",
        )
    )

    return reg


class TestDependencyDataclass:
    """Tests for the Dependency dataclass itself."""

    def test_dependency_with_on_only(self):
        """Dependency with only 'on' should have when=None."""
        dep = Dependency(on="level")
        assert dep.on == "level"
        assert dep.when is None

    def test_dependency_with_when(self):
        """Dependency with 'when' predicate should store it."""

        def pred(v):
            return v > 10

        dep = Dependency(on="level", when=pred)
        assert dep.on == "level"
        assert dep.when is pred


class TestStringNormalization:
    """Test that a plain string depends_on is treated as presence-based."""

    def test_string_dep_passes_when_target_present(self, registry):
        """String dep should pass when the target param is provided."""
        validate(registry, "presence_dep", {"a": 1, "b": 2})

    def test_string_dep_fails_when_target_absent(self, registry):
        """String dep should fail when the target param is missing."""
        with pytest.raises(ValidationError) as exc_info:
            validate(registry, "presence_dep", {"b": 2})
        error = exc_info.value
        assert len(error.errors) == 1
        param_name, msg = error.errors[0]
        assert param_name == "b"
        assert "a" in msg

    def test_string_dep_skipped_when_param_not_provided(self, registry):
        """Dependency check skipped when the dependent param itself is absent."""
        validate(registry, "presence_dep", {"a": 1})

    def test_string_dep_skipped_when_param_is_none(self, registry):
        """Dependency check skipped when the dependent param value is None."""
        validate(registry, "presence_dep", {"a": 1, "b": None})


class TestPredicateDependency:
    """Test predicate-based (when) dependencies."""

    def test_predicate_passes_when_condition_false(self, registry):
        """unit should be allowed when level is NOT relative."""
        validate(registry, "predicate_dep", {"level": "50", "unit": "dB"})

    def test_predicate_fails_when_condition_true(self, registry):
        """unit should be rejected when level IS relative."""
        with pytest.raises(ValidationError) as exc_info:
            validate(registry, "predicate_dep", {"level": "+", "unit": "dB"})
        error = exc_info.value
        assert len(error.errors) == 1
        param_name, _ = error.errors[0]
        assert param_name == "unit"

    def test_predicate_skipped_when_dep_param_absent(self, registry):
        """Predicate dep skipped when the dependent param itself is absent."""
        validate(registry, "predicate_dep", {"level": "+"})

    def test_predicate_skipped_when_dep_param_is_none(self, registry):
        """Predicate dep skipped when the dependent param is None."""
        validate(registry, "predicate_dep", {"level": "+", "unit": None})


class TestMultipleDependencies:
    """Test list of multiple dependencies."""

    def test_all_deps_satisfied(self, registry):
        """All deps satisfied should pass."""
        validate(registry, "multi_dep", {"a": 1, "b": 2, "c": 3})

    def test_first_dep_fails_short_circuits(self, registry):
        """First failing dep should short-circuit — only one error."""
        with pytest.raises(ValidationError) as exc_info:
            validate(registry, "multi_dep", {"c": 3})
        error = exc_info.value
        assert len(error.errors) == 1
        param_name, msg = error.errors[0]
        assert param_name == "c"
        assert "a" in msg


class TestTwoPassOrdering:
    """Test that pass two is suppressed when pass one fails."""

    def test_pass_two_suppressed_when_pass_one_fails(self, registry):
        """Dependency check should NOT run when per-param validation failed."""
        # level=99 is invalid (choices are 1,2,3) — pass one fails.
        # extra="x" would trigger the dependency (when level==99),
        # but pass two should be suppressed entirely.
        with pytest.raises(ValidationError) as exc_info:
            validate(
                registry, "two_pass", {"level": 99, "extra": "x"}
            )
        error = exc_info.value
        # Only pass-one error should appear
        assert len(error.errors) == 1
        param_name, _ = error.errors[0]
        assert param_name == "level"

    def test_pass_two_runs_when_pass_one_clean(self, registry):
        """Dependency check should run when pass one has no errors."""
        # level=2 is valid; the when predicate checks v==99 so it won't fire
        validate(registry, "two_pass", {"level": 2, "extra": "x"})


class TestDMP168UnitDependency:
    """Integration: unit rejected when level/gain is relative via DMP168 registry."""

    @pytest.fixture
    def dmp168_registry(self):
        from bluestream.base.commands import CommandRegistry
        from bluestream.devices.dmp168.commands import _register_commands

        reg = CommandRegistry()
        _register_commands(reg)
        return reg

    def test_output_volume_unit_rejected_with_relative_level(
        self, dmp168_registry
    ):
        """unit=dB should be rejected when level is '+' (relative)."""
        with pytest.raises(ValidationError) as exc_info:
            validate(
                dmp168_registry,
                "output_volume",
                {"output": 1, "level": "+", "unit": "dB"},
            )
        error = exc_info.value
        assert any("unit" == name for name, _ in error.errors)

    def test_output_volume_unit_allowed_with_absolute_level(
        self, dmp168_registry
    ):
        """unit=dB should be allowed when level is an absolute value."""
        validate(
            dmp168_registry,
            "output_volume",
            {"output": 1, "level": -10, "unit": "dB"},
        )

    def test_input_gain_unit_rejected_with_relative_gain(
        self, dmp168_registry
    ):
        """unit=dB should be rejected when gain is '-' (relative)."""
        with pytest.raises(ValidationError) as exc_info:
            validate(
                dmp168_registry,
                "input_gain",
                {"input_ch": 1, "gain": "-", "unit": "dB"},
            )
        error = exc_info.value
        assert any("unit" == name for name, _ in error.errors)

    def test_input_gain_unit_allowed_with_absolute_gain(
        self, dmp168_registry
    ):
        """unit=dB should be allowed when gain is an absolute value."""
        validate(
            dmp168_registry,
            "input_gain",
            {"input_ch": 1, "gain": 5, "unit": "dB"},
        )

    def test_output_master_volume_unit_rejected_relative(
        self, dmp168_registry
    ):
        """unit=dB rejected when level is relative on master volume."""
        with pytest.raises(ValidationError) as exc_info:
            validate(
                dmp168_registry,
                "output_master_volume",
                {"level": "+", "unit": "dB"},
            )
        error = exc_info.value
        assert any("unit" == name for name, _ in error.errors)

    def test_group_volume_unit_rejected_relative(self, dmp168_registry):
        """unit=dB rejected when level is relative on group volume."""
        with pytest.raises(ValidationError) as exc_info:
            validate(
                dmp168_registry,
                "group_volume",
                {"group": 1, "level": "-", "unit": "percent"},
            )
        error = exc_info.value
        assert any("unit" == name for name, _ in error.errors)
