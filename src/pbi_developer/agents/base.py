"""Base agent class with shared Claude Sonnet API calling logic."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import anthropic

from pbi_developer.config import settings
from pbi_developer.exceptions import AgentError
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


class BaseAgent:
    """Shared Claude Sonnet API logic for all specialist agents.

    Each subclass defines its own system_prompt and optionally tools
    for structured JSON output via tool_use.
    """

    system_prompt: str = "You are a helpful assistant."
    agent_name: str = "base"

    def __init__(self, model: str | None = None, max_tokens: int | None = None):
        self.client = anthropic.Anthropic(api_key=settings.claude.api_key)
        self.model = model or settings.claude.model
        self.max_tokens = max_tokens or settings.claude.max_tokens
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def call(
        self,
        prompt: str,
        *,
        images: list[Path | bytes] | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> str | dict[str, Any]:
        """Call Claude with text and optional images.

        If tools are provided and Claude uses one, returns the tool input dict.
        Otherwise returns the text response.
        """
        content = self._build_content(prompt, images)
        messages = [{"role": "user", "content": content}]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self.system_prompt,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.claude.temperature,
        }
        if tools:
            kwargs["tools"] = tools
        response = self._call_with_retry(**kwargs)
        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens
        logger.info(f"[{self.agent_name}] tokens: in={response.usage.input_tokens} out={response.usage.output_tokens}")
        return self._extract_response(response)

    def call_structured(
        self,
        prompt: str,
        output_schema: dict[str, Any],
        *,
        images: list[Path | bytes] | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Call Claude and force structured JSON output via tool_use.

        The output_schema defines the expected JSON structure as a tool input_schema.
        Returns the parsed dict matching the schema.
        """
        tool = {
            "name": "structured_output",
            "description": "Return the result in the specified structured format.",
            "input_schema": output_schema,
        }
        result = self.call(
            prompt,
            images=images,
            tools=[tool],
            temperature=temperature,
        )
        if isinstance(result, dict):
            return result
        # Fallback: try to parse as JSON from text
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.warning(f"[{self.agent_name}] Could not parse structured output, returning raw text")
            return {"raw_text": result}

    @property
    def token_usage(self) -> dict[str, int]:
        return {
            "input_tokens": self._total_input_tokens,
            "output_tokens": self._total_output_tokens,
        }

    def _build_content(self, prompt: str, images: list[Path | bytes] | None) -> list[dict[str, Any]]:
        """Build message content with text and optional images."""
        content: list[dict[str, Any]] = []
        if images:
            for img in images:
                if isinstance(img, Path):
                    img_bytes = img.read_bytes()
                    media_type = self._guess_media_type(img)
                else:
                    img_bytes = img
                    media_type = "image/png"
                b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    }
                )
        content.append({"type": "text", "text": prompt})
        return content

    def _call_with_retry(self, max_retries: int = 3, **kwargs: Any) -> Any:
        """Call Claude API with exponential backoff retry on transient errors."""
        for attempt in range(max_retries):
            try:
                return self.client.messages.create(**kwargs)
            except (anthropic.RateLimitError, anthropic.APIConnectionError) as e:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** (attempt + 1)
                logger.warning(f"[{self.agent_name}] Retry {attempt + 1}/{max_retries} after {wait}s: {e}")
                time.sleep(wait)
        raise AgentError(f"[{self.agent_name}] API call failed after {max_retries} retries")

    @staticmethod
    def _extract_response(response: Any) -> str | dict[str, Any]:
        """Extract text or tool_use result from the API response."""
        for block in response.content:
            if block.type == "tool_use":
                return block.input
        # Concatenate all text blocks
        texts = [b.text for b in response.content if b.type == "text"]
        return "\n".join(texts)

    @staticmethod
    def _guess_media_type(path: Path) -> str:
        suffix = path.suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "image/png")
