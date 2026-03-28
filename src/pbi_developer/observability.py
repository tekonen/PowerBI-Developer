"""AI call observability — per-call metrics, cost estimation, and structured logging.

Captures latency, token usage, retry counts, and estimated cost for each LLM call.
Optionally logs full prompts and responses for debugging (off by default).
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-20250514": {"input_per_mtok": 3.0, "output_per_mtok": 15.0},
    "claude-sonnet-4-6": {"input_per_mtok": 3.0, "output_per_mtok": 15.0},
    "claude-haiku-4-5-20251001": {"input_per_mtok": 0.80, "output_per_mtok": 4.0},
    "claude-opus-4-6": {"input_per_mtok": 15.0, "output_per_mtok": 75.0},
    "default": {"input_per_mtok": 3.0, "output_per_mtok": 15.0},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for an LLM call based on model pricing."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    return (
        input_tokens * pricing["input_per_mtok"] + output_tokens * pricing["output_per_mtok"]
    ) / 1_000_000


# ---------------------------------------------------------------------------
# Call record
# ---------------------------------------------------------------------------


@dataclass
class CallRecord:
    """Per-call metadata captured by the observability layer."""

    call_id: str = ""
    agent_name: str = ""
    model: str = ""
    temperature: float = 0.0
    timestamp: str = ""
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    prompt_length: int = 0
    response_length: int = 0
    retry_count: int = 0
    cost_usd: float = 0.0
    prompt_hash: str = ""

    # Optional capture (off by default)
    system_prompt: str | None = None
    user_prompt: str | None = None
    response_text: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.call_id:
            self.call_id = uuid.uuid4().hex[:12]
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Call log
# ---------------------------------------------------------------------------


@dataclass
class CallLog:
    """Thread-safe collector of CallRecord entries for a pipeline run."""

    _records: list[CallRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, entry: CallRecord) -> None:
        """Append a call record."""
        with self._lock:
            self._records.append(entry)

    def to_list(self) -> list[dict[str, Any]]:
        """Return all records as serializable dicts."""
        with self._lock:
            return [asdict(r) for r in self._records]

    def save(self, path: Path) -> None:
        """Write call log as JSON to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_list()
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Saved {len(data)} call record(s) to {path}")

    def summary(self) -> dict[str, Any]:
        """Aggregate metrics across all records."""
        with self._lock:
            records = list(self._records)
        if not records:
            return {"call_count": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_cost_usd": 0.0}

        return {
            "call_count": len(records),
            "total_input_tokens": sum(r.input_tokens for r in records),
            "total_output_tokens": sum(r.output_tokens for r in records),
            "total_cost_usd": sum(r.cost_usd for r in records),
            "total_latency_ms": sum(r.latency_ms for r in records),
            "total_retries": sum(r.retry_count for r in records),
        }

    def summary_for_agent(self, agent_name: str) -> dict[str, Any]:
        """Aggregate metrics for a specific agent."""
        with self._lock:
            records = [r for r in self._records if r.agent_name == agent_name]
        if not records:
            return {"call_count": 0, "latency_ms": 0.0, "cost_usd": 0.0, "retry_count": 0}

        return {
            "call_count": len(records),
            "input_tokens": sum(r.input_tokens for r in records),
            "output_tokens": sum(r.output_tokens for r in records),
            "latency_ms": sum(r.latency_ms for r in records),
            "cost_usd": sum(r.cost_usd for r in records),
            "retry_count": sum(r.retry_count for r in records),
        }
