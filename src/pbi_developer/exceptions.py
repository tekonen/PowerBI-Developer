"""Custom exception hierarchy for pbi-developer."""

from __future__ import annotations


class PBIDevError(Exception):
    """Base exception for pbi-developer."""


class PipelineError(PBIDevError):
    """Pipeline execution failure."""


class AgentError(PBIDevError):
    """Agent API call or response failure."""


class ValidationError(PBIDevError):
    """PBIR or QA validation failure."""


class ConnectionError(PBIDevError):
    """External system connection failure."""


class ConfigError(PBIDevError):
    """Configuration loading failure."""
