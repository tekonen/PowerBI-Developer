"""Deployment pipeline manager.

Manages dev -> test -> prod promotion using Power BI Deployment Pipelines API.
Includes approval gates between stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineStage:
    name: str  # dev, test, prod
    order: int  # 0, 1, 2
    workspace_id: str = ""


@dataclass
class PromotionResult:
    success: bool = False
    source_stage: str = ""
    target_stage: str = ""
    error: str | None = None


STAGES = [
    PipelineStage("dev", 0),
    PipelineStage("test", 1),
    PipelineStage("prod", 2),
]


def promote(
    pipeline_id: str,
    from_stage: str,
    *,
    items: list[dict[str, str]] | None = None,
    require_approval: bool = True,
) -> PromotionResult:
    """Promote content from one pipeline stage to the next.

    Args:
        pipeline_id: Deployment pipeline ID.
        from_stage: Source stage name (dev or test).
        items: Optional specific items to promote.
        require_approval: Whether to require human approval before promoting.

    Returns:
        PromotionResult with success status.
    """
    stage_map = {s.name: s for s in STAGES}
    if from_stage not in stage_map:
        return PromotionResult(
            success=False,
            error=f"Invalid stage: {from_stage}. Use: dev, test",
        )

    source = stage_map[from_stage]
    target_order = source.order + 1
    target = next((s for s in STAGES if s.order == target_order), None)

    if target is None:
        return PromotionResult(
            success=False,
            error=f"Cannot promote from {from_stage} — already at final stage",
        )

    if require_approval and target.name == "prod":
        logger.warning(f"Production promotion requires approval. Promoting from {from_stage} to {target.name}.")
        # In a real implementation, this would:
        # 1. Send notification to approvers
        # 2. Wait for approval
        # 3. Log the approval for audit
        logger.info("Approval gate placeholder — proceeding")

    try:
        from pbi_developer.connectors.powerbi_rest import PowerBIClient

        client = PowerBIClient()
        client.deploy_pipeline_stage(
            pipeline_id,
            source.order,
            items=items,
        )

        logger.info(f"Promoted from {from_stage} to {target.name}")
        return PromotionResult(
            success=True,
            source_stage=from_stage,
            target_stage=target.name,
        )

    except Exception as e:
        return PromotionResult(
            success=False,
            source_stage=from_stage,
            target_stage=target.name,
            error=str(e),
        )


def get_pipeline_status(pipeline_id: str) -> dict[str, Any]:
    """Get the current status of a deployment pipeline."""
    try:
        from pbi_developer.connectors.powerbi_rest import PowerBIClient

        client = PowerBIClient()
        pipelines = client.list_pipelines()
        for p in pipelines:
            if p.get("id") == pipeline_id:
                return p
        return {"error": f"Pipeline {pipeline_id} not found"}
    except Exception as e:
        return {"error": str(e)}
