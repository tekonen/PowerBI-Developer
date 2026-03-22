"""Tests for src/pbi_developer/exceptions.py."""

from __future__ import annotations

import pytest

from pbi_developer.exceptions import (
    AgentError,
    ConfigError,
    PBIDevError,
    PipelineError,
    ValidationError,
)
from pbi_developer.exceptions import (
    ConnectionError as PBIConnectionError,
)

# ---------------------------------------------------------------------------
# Hierarchy
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """All custom exceptions must inherit from PBIDevError."""

    @pytest.mark.parametrize(
        "exc_class",
        [PipelineError, AgentError, ValidationError, PBIConnectionError, ConfigError],
    )
    def test_subclass_of_pbidev_error(self, exc_class: type) -> None:
        assert issubclass(exc_class, PBIDevError)

    @pytest.mark.parametrize(
        "exc_class",
        [PBIDevError, PipelineError, AgentError, ValidationError, PBIConnectionError, ConfigError],
    )
    def test_subclass_of_exception(self, exc_class: type) -> None:
        assert issubclass(exc_class, Exception)

    def test_pbidev_error_is_base(self) -> None:
        assert PBIDevError.__bases__ == (Exception,)


# ---------------------------------------------------------------------------
# Raising and catching
# ---------------------------------------------------------------------------


class TestRaisingAndCatching:
    def test_raise_pipeline_error(self) -> None:
        with pytest.raises(PipelineError):
            raise PipelineError("pipeline broke")

    def test_raise_agent_error(self) -> None:
        with pytest.raises(AgentError):
            raise AgentError("agent failed")

    def test_raise_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            raise ValidationError("invalid schema")

    def test_raise_connection_error(self) -> None:
        with pytest.raises(PBIConnectionError):
            raise PBIConnectionError("timeout")

    def test_raise_config_error(self) -> None:
        with pytest.raises(ConfigError):
            raise ConfigError("bad config")

    def test_catch_subclass_as_base(self) -> None:
        """Catching PBIDevError should catch any subclass."""
        with pytest.raises(PBIDevError):
            raise PipelineError("caught as base")

    def test_catch_all_subclasses_as_base(self) -> None:
        for exc_class in [PipelineError, AgentError, ValidationError, PBIConnectionError, ConfigError]:
            with pytest.raises(PBIDevError):
                raise exc_class("caught")

    def test_does_not_catch_unrelated(self) -> None:
        """A plain ValueError should not be caught by PBIDevError."""
        with pytest.raises(ValueError):
            raise ValueError("unrelated")


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------


class TestMessageFormatting:
    def test_message_preserved(self) -> None:
        msg = "something went wrong"
        exc = PBIDevError(msg)
        assert str(exc) == msg

    def test_message_preserved_subclass(self) -> None:
        msg = "pipeline step 3 failed"
        exc = PipelineError(msg)
        assert str(exc) == msg

    def test_empty_message(self) -> None:
        exc = AgentError()
        assert str(exc) == ""

    def test_multiline_message(self) -> None:
        msg = "line one\nline two\nline three"
        exc = ValidationError(msg)
        assert str(exc) == msg

    def test_args_tuple(self) -> None:
        exc = ConfigError("bad config", 42)
        assert exc.args == ("bad config", 42)

    def test_repr_contains_class_name(self) -> None:
        exc = PipelineError("boom")
        assert "PipelineError" in repr(exc)

    @pytest.mark.parametrize(
        "exc_class,msg",
        [
            (PipelineError, "pipeline issue"),
            (AgentError, "agent issue"),
            (ValidationError, "validation issue"),
            (PBIConnectionError, "connection issue"),
            (ConfigError, "config issue"),
        ],
    )
    def test_str_matches_message(self, exc_class: type, msg: str) -> None:
        assert str(exc_class(msg)) == msg
