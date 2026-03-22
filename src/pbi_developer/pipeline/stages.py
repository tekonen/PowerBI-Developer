"""Pipeline stage definitions.

Each stage represents a step in the 8-step pipeline:
1. Requirements Ingestion
2. Semantic Model Connection
3. Wireframe Design (Architect Agent)
4. Field Mapping
5. QA Validation
6. PBIR Conversion
7. Report Publishing
8. RLS Configuration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


STAGE_LABELS: dict[str, str] = {
    "ingestion": "Ingesting requirements",
    "model_connection": "Loading semantic model",
    "wireframe": "Designing wireframe",
    "field_mapping": "Mapping fields",
    "qa": "Validating (QA)",
    "pbir_generation": "Generating PBIR",
    "publishing": "Publishing",
    "rls": "RLS configuration",
    "dax": "Generating DAX measures",
}


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """Result of a pipeline stage execution."""

    stage_name: str
    status: StageStatus = StageStatus.PENDING
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    token_usage: dict[str, int] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == StageStatus.COMPLETED


@dataclass
class PipelineState:
    """Tracks the state of the entire pipeline."""

    stages: dict[str, StageResult] = field(default_factory=dict)
    current_stage: str = ""

    def set_running(self, stage: str) -> None:
        self.current_stage = stage
        self.stages[stage] = StageResult(stage_name=stage, status=StageStatus.RUNNING)

    def set_completed(
        self, stage: str, data: dict[str, Any] | None = None, tokens: dict[str, int] | None = None
    ) -> None:
        if stage in self.stages:
            self.stages[stage].status = StageStatus.COMPLETED
            if data:
                self.stages[stage].data = data
            if tokens:
                self.stages[stage].token_usage = tokens

    def set_failed(self, stage: str, error: str) -> None:
        if stage in self.stages:
            self.stages[stage].status = StageStatus.FAILED
            self.stages[stage].error = error

    def set_skipped(self, stage: str) -> None:
        self.stages[stage] = StageResult(stage_name=stage, status=StageStatus.SKIPPED)

    @property
    def all_completed(self) -> bool:
        return all(s.status in (StageStatus.COMPLETED, StageStatus.SKIPPED) for s in self.stages.values())

    @property
    def total_tokens(self) -> dict[str, int]:
        total_in = sum(s.token_usage.get("input_tokens", 0) for s in self.stages.values())
        total_out = sum(s.token_usage.get("output_tokens", 0) for s in self.stages.values())
        return {"input_tokens": total_in, "output_tokens": total_out}
