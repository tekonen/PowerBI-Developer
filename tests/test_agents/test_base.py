"""Tests for BaseAgent — API calls, retry logic, token tracking."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pbi_developer.agents.base import BaseAgent


@pytest.fixture
def mock_response():
    """Create a mock Claude API response."""
    response = MagicMock()
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Hello, world!"
    response.content = [text_block]
    return response


@pytest.fixture
def mock_tool_response():
    """Create a mock Claude API response with tool_use."""
    response = MagicMock()
    response.usage.input_tokens = 200
    response.usage.output_tokens = 100
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {"result": "structured data"}
    response.content = [tool_block]
    return response


class TestBaseAgent:
    @patch("pbi_developer.agents.base.anthropic.Anthropic")
    @patch("pbi_developer.agents.base.settings")
    def test_call_returns_text(self, mock_settings, _mock_client_cls, mock_response):
        mock_settings.claude.api_key = "test-key"
        mock_settings.claude.model = "test-model"
        mock_settings.claude.max_tokens = 1024
        mock_settings.claude.temperature = 0.2

        agent = BaseAgent()
        agent.client.messages.create.return_value = mock_response

        result = agent.call("Hello")

        assert result == "Hello, world!"

    @patch("pbi_developer.agents.base.anthropic.Anthropic")
    @patch("pbi_developer.agents.base.settings")
    def test_call_returns_tool_input(self, mock_settings, _mock_client_cls, mock_tool_response):
        mock_settings.claude.api_key = "test-key"
        mock_settings.claude.model = "test-model"
        mock_settings.claude.max_tokens = 1024
        mock_settings.claude.temperature = 0.2

        agent = BaseAgent()
        agent.client.messages.create.return_value = mock_tool_response

        result = agent.call("Hello", tools=[{"name": "test", "description": "test", "input_schema": {}}])

        assert isinstance(result, dict)
        assert result == {"result": "structured data"}

    @patch("pbi_developer.agents.base.anthropic.Anthropic")
    @patch("pbi_developer.agents.base.settings")
    def test_token_tracking(self, mock_settings, _mock_client_cls, mock_response):
        mock_settings.claude.api_key = "test-key"
        mock_settings.claude.model = "test-model"
        mock_settings.claude.max_tokens = 1024
        mock_settings.claude.temperature = 0.2

        agent = BaseAgent()
        agent.client.messages.create.return_value = mock_response

        agent.call("Hello")
        agent.call("World")

        assert agent.token_usage == {"input_tokens": 200, "output_tokens": 100}

    @patch("pbi_developer.agents.base.anthropic.Anthropic")
    @patch("pbi_developer.agents.base.settings")
    def test_call_structured_returns_dict(self, mock_settings, _mock_client_cls, mock_tool_response):
        mock_settings.claude.api_key = "test-key"
        mock_settings.claude.model = "test-model"
        mock_settings.claude.max_tokens = 1024
        mock_settings.claude.temperature = 0.2

        agent = BaseAgent()
        agent.client.messages.create.return_value = mock_tool_response

        result = agent.call_structured("Hello", output_schema={"type": "object"})

        assert isinstance(result, dict)
        assert result == {"result": "structured data"}

    def test_extract_response_text(self):
        response = MagicMock()
        block = MagicMock()
        block.type = "text"
        block.text = "Test output"
        response.content = [block]

        result = BaseAgent._extract_response(response)
        assert result == "Test output"

    def test_extract_response_tool_use(self):
        response = MagicMock()
        block = MagicMock()
        block.type = "tool_use"
        block.input = {"key": "value"}
        response.content = [block]

        result = BaseAgent._extract_response(response)
        assert result == {"key": "value"}

    def test_guess_media_type(self):
        from pathlib import Path

        assert BaseAgent._guess_media_type(Path("image.png")) == "image/png"
        assert BaseAgent._guess_media_type(Path("photo.jpg")) == "image/jpeg"
        assert BaseAgent._guess_media_type(Path("photo.jpeg")) == "image/jpeg"
        assert BaseAgent._guess_media_type(Path("animation.gif")) == "image/gif"
        assert BaseAgent._guess_media_type(Path("image.webp")) == "image/webp"
        assert BaseAgent._guess_media_type(Path("unknown.bmp")) == "image/png"
