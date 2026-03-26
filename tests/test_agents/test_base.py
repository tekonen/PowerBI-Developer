"""Tests for BaseAgent — LangChain API calls, retry logic, token tracking."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pbi_developer.agents.base import BaseAgent


def _make_ai_message(text="Hello, world!", input_tokens=100, output_tokens=50):
    """Create a mock LangChain AIMessage."""
    msg = MagicMock()
    msg.content = text
    msg.usage_metadata = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    msg.tool_calls = []
    return msg


def _make_tool_message(tool_args=None, input_tokens=200, output_tokens=100):
    """Create a mock LangChain AIMessage with tool calls."""
    if tool_args is None:
        tool_args = {"result": "structured data"}
    msg = MagicMock()
    msg.content = ""
    msg.usage_metadata = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    msg.tool_calls = [{"name": "structured_output", "args": tool_args, "id": "call_1"}]
    return msg


class TestBaseAgent:
    @patch("pbi_developer.agents.base.ChatAnthropic")
    @patch("pbi_developer.agents.base.settings")
    def test_call_returns_text(self, mock_settings, mock_llm_cls):
        mock_settings.claude.api_key = "test-key"
        mock_settings.claude.model = "test-model"
        mock_settings.claude.max_tokens = 1024
        mock_settings.claude.temperature = 0.2
        mock_settings.claude.base_url = ""

        mock_llm = mock_llm_cls.return_value
        mock_llm.invoke.return_value = _make_ai_message()

        agent = BaseAgent()
        result = agent.call("Hello")

        assert result == "Hello, world!"

    @patch("pbi_developer.agents.base.ChatAnthropic")
    @patch("pbi_developer.agents.base.settings")
    def test_call_returns_tool_input(self, mock_settings, mock_llm_cls):
        mock_settings.claude.api_key = "test-key"
        mock_settings.claude.model = "test-model"
        mock_settings.claude.max_tokens = 1024
        mock_settings.claude.temperature = 0.2
        mock_settings.claude.base_url = ""

        mock_llm = mock_llm_cls.return_value
        bound_llm = MagicMock()
        mock_llm.bind_tools.return_value = bound_llm
        bound_llm.invoke.return_value = _make_tool_message()

        agent = BaseAgent()
        result = agent.call("Hello", tools=[{"name": "test", "description": "test", "input_schema": {}}])

        assert isinstance(result, dict)
        assert result == {"result": "structured data"}

    @patch("pbi_developer.agents.base.ChatAnthropic")
    @patch("pbi_developer.agents.base.settings")
    def test_token_tracking(self, mock_settings, mock_llm_cls):
        mock_settings.claude.api_key = "test-key"
        mock_settings.claude.model = "test-model"
        mock_settings.claude.max_tokens = 1024
        mock_settings.claude.temperature = 0.2
        mock_settings.claude.base_url = ""

        mock_llm = mock_llm_cls.return_value
        mock_llm.invoke.return_value = _make_ai_message()

        agent = BaseAgent()
        agent.call("Hello")
        agent.call("World")

        assert agent.token_usage == {"input_tokens": 200, "output_tokens": 100}

    @patch("pbi_developer.agents.base.ChatAnthropic")
    @patch("pbi_developer.agents.base.settings")
    def test_call_structured_returns_dict(self, mock_settings, mock_llm_cls):
        mock_settings.claude.api_key = "test-key"
        mock_settings.claude.model = "test-model"
        mock_settings.claude.max_tokens = 1024
        mock_settings.claude.temperature = 0.2
        mock_settings.claude.base_url = ""

        mock_llm = mock_llm_cls.return_value
        bound_llm = MagicMock()
        mock_llm.bind_tools.return_value = bound_llm
        bound_llm.invoke.return_value = _make_tool_message()

        agent = BaseAgent()
        result = agent.call_structured("Hello", output_schema={"type": "object"})

        assert isinstance(result, dict)
        assert result == {"result": "structured data"}

    def test_extract_response_text(self):
        msg = _make_ai_message("Test output")
        result = BaseAgent._extract_response(msg)
        assert result == "Test output"

    def test_extract_response_tool_use(self):
        msg = _make_tool_message({"key": "value"})
        result = BaseAgent._extract_response(msg)
        assert result == {"key": "value"}

    def test_guess_media_type(self):
        assert BaseAgent._guess_media_type(Path("image.png")) == "image/png"
        assert BaseAgent._guess_media_type(Path("photo.jpg")) == "image/jpeg"
        assert BaseAgent._guess_media_type(Path("photo.jpeg")) == "image/jpeg"
        assert BaseAgent._guess_media_type(Path("animation.gif")) == "image/gif"
        assert BaseAgent._guess_media_type(Path("image.webp")) == "image/webp"
        assert BaseAgent._guess_media_type(Path("unknown.bmp")) == "image/png"
