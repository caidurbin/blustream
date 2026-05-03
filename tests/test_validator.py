"""Tests for the centralized validator module."""

import pytest

from bluestream.base.commands import Command, CommandRegistry, Parameter
from bluestream.base.exceptions import ValidationError
from bluestream.base.validator import validate


@pytest.fixture
def registry():
    """Create a registry with test commands."""
    reg = CommandRegistry()

    reg.register(
        Command(
            name="test_cmd",
            description="A test command",
            parameters=[
                Parameter(
                    "output",
                    int,
                    required=True,
                    choices=list(range(9)),
                    help_text="Output channel (0-8)",
                ),
                Parameter(
                    "level",
                    int,
                    required=True,
                    help_text="Volume level",
                ),
                Parameter(
                    "channel",
                    str,
                    required=False,
                    default="LR",
                    choices=["L", "R", "LR"],
                    help_text="Channel",
                ),
            ],
            handler=lambda **kwargs: "OK",
        )
    )

    reg.register(
        Command(
            name="validated_cmd",
            description="Command with validation callables",
            parameters=[
                Parameter(
                    "delay_ms",
                    int,
                    required=True,
                    help_text="Delay in ms (0-500)",
                    validation=lambda v: (
                        f"Delay must be between 0-500, got {v}"
                        if not (0 <= v <= 500)
                        else None
                    ),
                ),
                Parameter(
                    "name",
                    str,
                    required=True,
                    help_text="Name (non-empty)",
                    validation=lambda v: (
                        "Name must not be empty" if not v else None
                    ),
                ),
            ],
            handler=lambda **kwargs: "OK",
        )
    )

    reg.register(
        Command(
            name="no_params",
            description="Command with no parameters",
            parameters=[],
            handler=lambda **kwargs: "OK",
        )
    )

    return reg


class TestValidate:
    """Tests for the validate() function."""

    def test_valid_kwargs_pass(self, registry):
        """Valid kwargs should not raise."""
        validate(registry, "test_cmd", {"output": 1, "level": 50})

    def test_valid_kwargs_with_optional(self, registry):
        """Valid kwargs including optional params should not raise."""
        validate(
            registry, "test_cmd", {"output": 1, "level": 50, "channel": "L"}
        )

    def test_no_params_command(self, registry):
        """Command with no parameters should pass with empty kwargs."""
        validate(registry, "no_params", {})

    def test_unknown_command_raises(self, registry):
        """Unknown command name should raise CommandError."""
        from bluestream.base.exceptions import CommandError

        with pytest.raises(CommandError, match="Unknown command"):
            validate(registry, "nonexistent", {})

    def test_missing_required_parameter(self, registry):
        """Missing required parameter should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate(registry, "test_cmd", {"output": 1})
        assert "level" in str(exc_info.value)

    def test_missing_multiple_required_parameters(self, registry):
        """Missing multiple required params should all appear in error."""
        with pytest.raises(ValidationError) as exc_info:
            validate(registry, "test_cmd", {})
        error = exc_info.value
        assert hasattr(error, "errors")
        assert len(error.errors) >= 2
        param_names = [name for name, _ in error.errors]
        assert "output" in param_names
        assert "level" in param_names

    def test_invalid_choice(self, registry):
        """Invalid choice value should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate(registry, "test_cmd", {"output": 99, "level": 50})
        assert "output" in str(exc_info.value)

    def test_multiple_failures_collected(self, registry):
        """Multiple validation failures should be collected into one error."""
        with pytest.raises(ValidationError) as exc_info:
            validate(
                registry,
                "test_cmd",
                {"output": 99, "level": 50, "channel": "X"},
            )
        error = exc_info.value
        assert hasattr(error, "errors")
        assert len(error.errors) == 2
        param_names = [name for name, _ in error.errors]
        assert "output" in param_names
        assert "channel" in param_names

    def test_validation_callable_valid(self, registry):
        """Validation callable returning None should pass."""
        validate(
            registry, "validated_cmd", {"delay_ms": 250, "name": "test"}
        )

    def test_validation_callable_invalid(self, registry):
        """Validation callable returning error string should fail."""
        with pytest.raises(ValidationError) as exc_info:
            validate(
                registry, "validated_cmd", {"delay_ms": 999, "name": "test"}
            )
        assert "Delay must be between 0-500" in str(exc_info.value)

    def test_validation_callable_error_message_preserved(self, registry):
        """Error message from validation callable should be in errors list."""
        with pytest.raises(ValidationError) as exc_info:
            validate(
                registry, "validated_cmd", {"delay_ms": 999, "name": "test"}
            )
        error = exc_info.value
        assert any(
            "Delay must be between 0-500" in msg
            for _, msg in error.errors
        )

    def test_multiple_validation_callable_failures(self, registry):
        """Multiple validation callable failures collected together."""
        with pytest.raises(ValidationError) as exc_info:
            validate(
                registry, "validated_cmd", {"delay_ms": 999, "name": ""}
            )
        error = exc_info.value
        assert len(error.errors) == 2
        messages = [msg for _, msg in error.errors]
        assert any("Delay" in m for m in messages)
        assert any("Name" in m for m in messages)

    def test_choices_and_validation_callable_combined(self):
        """Both choices failure and validation callable failure collected."""
        reg = CommandRegistry()
        reg.register(
            Command(
                name="combo",
                description="Combo test",
                parameters=[
                    Parameter(
                        "mode",
                        str,
                        required=True,
                        choices=["a", "b"],
                    ),
                    Parameter(
                        "value",
                        int,
                        required=True,
                        validation=lambda v: (
                            "Value must be positive" if v < 0 else None
                        ),
                    ),
                ],
                handler=lambda **kwargs: "OK",
            )
        )

        with pytest.raises(ValidationError) as exc_info:
            validate(reg, "combo", {"mode": "z", "value": -5})
        error = exc_info.value
        assert len(error.errors) == 2

    def test_optional_param_none_skips_validation(self):
        """Optional param with None value should skip validation."""
        reg = CommandRegistry()
        reg.register(
            Command(
                name="opt_cmd",
                description="Optional test",
                parameters=[
                    Parameter(
                        "name",
                        str,
                        required=True,
                    ),
                    Parameter(
                        "tag",
                        str,
                        required=False,
                        default=None,
                        choices=["x", "y"],
                        validation=lambda v: "bad" if not v else None,
                    ),
                ],
                handler=lambda **kwargs: "OK",
            )
        )
        validate(reg, "opt_cmd", {"name": "test", "tag": None})

    def test_validation_error_str_contains_all_messages(self, registry):
        """str(ValidationError) should contain all error messages."""
        with pytest.raises(ValidationError) as exc_info:
            validate(
                registry,
                "validated_cmd",
                {"delay_ms": 999, "name": ""},
            )
        error_str = str(exc_info.value)
        assert "delay_ms" in error_str or "Delay" in error_str
        assert "name" in error_str or "Name" in error_str
