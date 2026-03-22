"""Deployment module.

Deploys PBIR reports to Power BI Service via:
- Option A: fabric-cicd library for PBIP deployment (recommended)
- Option B: pbi-tools compile + REST API upload
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pbi_developer.config import settings
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DeployResult:
    success: bool = False
    error: str | None = None
    report_id: str | None = None
    workspace_url: str | None = None


def deploy_report(
    report_dir: Path,
    *,
    workspace_id: str | None = None,
    stage: str = "dev",
    method: str = "auto",
) -> DeployResult:
    """Deploy a PBIR report to Power BI Service.

    Args:
        report_dir: Path to the .Report PBIR folder.
        workspace_id: Target workspace ID (overrides config).
        stage: Deployment stage (dev, test, prod).
        method: Deployment method (auto, fabric-cicd, rest-api).

    Returns:
        DeployResult with success status and deployed report info.
    """
    ws_id = workspace_id or settings.powerbi.workspace_id
    if not ws_id:
        return DeployResult(
            success=False,
            error="No workspace ID configured. Set POWERBI_WORKSPACE_ID or use --workspace.",
        )

    if settings.pipeline.require_human_review and stage == "prod":
        logger.warning("Production deployment requires human review. Use --stage=dev for testing.")
        # In a real implementation, this would prompt for confirmation
        logger.info("Proceeding with deployment (human review gate placeholder)")

    if method == "auto":
        method = "fabric-cicd"

    if method == "fabric-cicd":
        return _deploy_fabric_cicd(report_dir, ws_id)
    elif method == "rest-api":
        return _deploy_rest_api(report_dir, ws_id)
    else:
        return DeployResult(success=False, error=f"Unknown deployment method: {method}")


def _deploy_fabric_cicd(report_dir: Path, workspace_id: str) -> DeployResult:
    """Deploy using Microsoft's fabric-cicd Python library."""
    try:
        from fabric_cicd import FabricWorkspace

        # Find the PBIP project root (parent of .Report folder)
        project_root = report_dir.parent

        workspace = FabricWorkspace(
            workspace_id=workspace_id,
            repository_directory=str(project_root),
            item_type_in_scope=["Report", "SemanticModel"],
        )
        workspace.publish_all_items()

        logger.info(f"Deployed via fabric-cicd to workspace {workspace_id}")
        return DeployResult(
            success=True,
            workspace_url=f"https://app.powerbi.com/groups/{workspace_id}",
        )

    except ImportError:
        logger.warning("fabric-cicd not installed. Install with: pip install pbi-developer[deploy]")
        return DeployResult(
            success=False,
            error="fabric-cicd not installed. Run: pip install pbi-developer[deploy]",
        )
    except Exception as e:
        return DeployResult(success=False, error=f"fabric-cicd deployment failed: {e}")


def _deploy_rest_api(report_dir: Path, workspace_id: str) -> DeployResult:
    """Deploy via Power BI REST API (requires compiled .pbix)."""
    try:
        from pbi_developer.connectors.powerbi_rest import PowerBIClient

        # Look for compiled .pbix file
        pbix_files = list(report_dir.parent.glob("*.pbix"))
        if not pbix_files:
            return DeployResult(
                success=False,
                error=(
                    "No .pbix file found. REST API deployment requires a compiled .pbix. "
                    "Use pbi-tools to compile: pbi-tools compile <project-folder>"
                ),
            )

        client = PowerBIClient(workspace_id=workspace_id)
        report_name = report_dir.stem.replace(".Report", "")
        result = client.import_pbix(pbix_files[0], report_name)

        return DeployResult(
            success=True,
            report_id=result.get("id"),
            workspace_url=f"https://app.powerbi.com/groups/{workspace_id}",
        )

    except Exception as e:
        return DeployResult(success=False, error=f"REST API deployment failed: {e}")
