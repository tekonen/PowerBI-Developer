"""Base agent class with shared Claude Sonnet API calling logic via LangChain."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anthropic
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from pbi_developer.config import settings
from pbi_developer.exceptions import AgentError
from pbi_developer.utils.logging import get_logger

if TYPE_CHECKING:
    from pbi_developer.observability import CallLog

logger = get_logger(__name__)


class BaseAgent:
    """Shared Claude Sonnet API logic for all specialist agents.

    Uses LangChain's ChatAnthropic for LLM calls, supporting structured
    output, image inputs, retry logic, and token tracking.

    Each subclass defines its own system_prompt and optionally tools
    for structured JSON output via tool_use.
    """

    system_prompt: str = "You are a helpful assistant."
    agent_name: str = "base"

    def __init__(self, model: str | None = None, max_tokens: int | None = None):
        llm_kwargs: dict[str, Any] = {
            "model": model or settings.claude.model,
            "max_tokens": max_tokens or settings.claude.max_tokens,
            "temperature": settings.claude.temperature,
            "api_key": settings.claude.api_key,
        }
        if settings.claude.base_url:
            llm_kwargs["base_url"] = settings.claude.base_url
        self.llm = ChatAnthropic(**llm_kwargs)
        self.model = llm_kwargs["model"]
        self.max_tokens = llm_kwargs["max_tokens"]
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._call_log: CallLog | None = None

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
        messages = self._build_messages(prompt, images)
        llm = self.llm
        if tools:
            llm = llm.bind_tools(tools)
        if temperature is not None:
            llm = llm.with_config(configurable={"temperature": temperature})

        start = time.perf_counter()
        response, retry_count = self._call_with_retry(llm, messages)
        latency_ms = (time.perf_counter() - start) * 1000

        input_tokens, output_tokens = self._track_tokens(response)
        result = self._extract_response(response)

        if self._call_log is not None:
            self._record_call(
                prompt=prompt,
                result=result,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                retry_count=retry_count,
                temperature=temperature if temperature is not None else settings.claude.temperature,
            )

        return result

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

    def _build_messages(self, prompt: str, images: list[Path | bytes] | None) -> list:
        """Build LangChain message list with system prompt, text, and optional images."""
        messages = [SystemMessage(content=self.system_prompt)]
        content = self._build_content(prompt, images)
        messages.append(HumanMessage(content=content))
        return messages

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

    def _call_with_retry(self, llm: Any, messages: list, max_retries: int = 3) -> tuple[Any, int]:
        """Call LangChain LLM with exponential backoff retry on transient errors.

        Returns (response, retry_count) where retry_count is the number of
        failed attempts before success (0 = succeeded on first try).
        """
        for attempt in range(max_retries):
            try:
                return llm.invoke(messages), attempt
            except (anthropic.RateLimitError, anthropic.APIConnectionError) as e:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** (attempt + 1)
                logger.warning(f"[{self.agent_name}] Retry {attempt + 1}/{max_retries} after {wait}s: {e}")
                time.sleep(wait)
        raise AgentError(f"[{self.agent_name}] API call failed after {max_retries} retries")

    def _track_tokens(self, response: Any) -> tuple[int, int]:
        """Extract and accumulate token usage from LangChain AIMessage.

        Returns (input_tokens, output_tokens).
        """
        usage = getattr(response, "usage_metadata", None)
        if usage:
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
        else:
            # Fallback for raw Anthropic response objects
            raw_usage = getattr(response, "usage", None)
            if raw_usage:
                input_tokens = getattr(raw_usage, "input_tokens", 0)
                output_tokens = getattr(raw_usage, "output_tokens", 0)
            else:
                input_tokens = 0
                output_tokens = 0
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        logger.info(f"[{self.agent_name}] tokens: in={input_tokens} out={output_tokens}")
        return input_tokens, output_tokens

    def _record_call(
        self,
        prompt: str,
        result: Any,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        retry_count: int,
        temperature: float,
    ) -> None:
        """Record a call to the observability log."""
        from pbi_developer.observability import CallRecord, estimate_cost

        record = CallRecord(
            agent_name=self.agent_name,
            model=self.model,
            temperature=temperature,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            prompt_length=len(prompt),
            response_length=len(json.dumps(result)) if isinstance(result, dict) else len(str(result)),
            retry_count=retry_count,
            cost_usd=estimate_cost(self.model, input_tokens, output_tokens),
            prompt_hash=hashlib.sha256(self.system_prompt.encode()).hexdigest()[:16],
            system_prompt=self.system_prompt if settings.observability.capture_prompts else None,
            user_prompt=prompt if settings.observability.capture_prompts else None,
            response_text=json.dumps(result) if settings.observability.capture_prompts and isinstance(result, dict) else None,
        )
        self._call_log.record(record)

    @staticmethod
    def _extract_response(response: Any) -> str | dict[str, Any]:
        """Extract text or tool_use result from the LangChain AIMessage."""
        # LangChain AIMessage with tool calls
        tool_calls = getattr(response, "tool_calls", None)
        if tool_calls:
            return tool_calls[0]["args"]
        # Check for Anthropic-style content blocks (backward compat)
        content = getattr(response, "content", None)
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    return block.get("input", block.get("args", {}))
            # Concatenate text blocks
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block["text"])
                elif isinstance(block, str):
                    texts.append(block)
                elif hasattr(block, "type") and block.type == "text":
                    texts.append(block.text)
            if texts:
                return "\n".join(texts)
        # Plain string content
        if isinstance(content, str):
            return content
        return str(response)

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
