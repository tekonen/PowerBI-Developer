"""Pydantic request/response models for the web API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

WIZARD_STEPS = [
    "init",
    "ingestion",
    "metadata",
    "wireframe",
    "field_mapping",
    "dax",
    "qa",
    "pbir",
    "rls",
    "publish",
]


class RunInfo(BaseModel):
    """Metadata for a single pipeline run."""

    run_id: str
    created_at: datetime
    report_name: str = "Report"
    dry_run: bool = True
    status: str = "pending"  # pending | running | completed | failed
    stages: dict[str, str] = Field(default_factory=dict)
    output_path: str | None = None
    tokens: dict[str, int] = Field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None
    wizard_step: str = "init"


class RefineRequest(BaseModel):
    """Request body for the refine endpoint."""

    stage: str  # wireframe | field_mapping | dax | rls
    corrections: str
    dry_run: bool = True


class DeployRequest(BaseModel):
    """Request body for the deploy endpoint."""

    report_dir: str
    workspace_id: str | None = None
    stage: str = "dev"
    method: str = "auto"


class StepCorrectRequest(BaseModel):
    """Request body for correcting a wizard step."""

    corrections: str


class MetadataFetchRequest(BaseModel):
    """Request body for fetching metadata from a Power BI dataset."""

    dataset_id: str
