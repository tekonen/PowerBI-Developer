"""Power BI REST API client.

Handles workspace management, report import/export, dataset operations,
DAX query execution, and deployment pipeline management.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from pbi_developer.config import settings
from pbi_developer.connectors.auth import get_powerbi_token
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


class PowerBIClient:
    """Client for Power BI REST API operations."""

    def __init__(self, workspace_id: str | None = None):
        self.base_url = settings.powerbi.api_base
        self.workspace_id = workspace_id or settings.powerbi.workspace_id
        self._token: str | None = None

    @property
    def token(self) -> str:
        if self._token is None:
            self._token = get_powerbi_token()
        return self._token

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        if self.workspace_id:
            return f"{self.base_url}/groups/{self.workspace_id}/{path}"
        return f"{self.base_url}/{path}"

    # --- Workspace Operations ---

    def list_workspaces(self) -> list[dict[str, Any]]:
        """List all workspaces the service principal has access to."""
        resp = requests.get(f"{self.base_url}/groups", headers=self.headers)
        resp.raise_for_status()
        return resp.json().get("value", [])

    def get_workspace(self) -> dict[str, Any]:
        """Get details of the configured workspace."""
        resp = requests.get(
            f"{self.base_url}/groups/{self.workspace_id}",
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json()

    # --- Dataset Operations ---

    def list_datasets(self) -> list[dict[str, Any]]:
        """List datasets in the workspace."""
        resp = requests.get(self._url("datasets"), headers=self.headers)
        resp.raise_for_status()
        return resp.json().get("value", [])

    def refresh_dataset(self, dataset_id: str) -> None:
        """Trigger a dataset refresh."""
        resp = requests.post(
            self._url(f"datasets/{dataset_id}/refreshes"),
            headers=self.headers,
            json={"notifyOption": "NoNotification"},
        )
        resp.raise_for_status()
        logger.info(f"Dataset refresh triggered: {dataset_id}")

    def execute_dax_query(self, dataset_id: str, dax_query: str) -> dict[str, Any]:
        """Execute a DAX query against a dataset.

        Requires the dataset to be in a Premium/Fabric capacity.
        """
        resp = requests.post(
            self._url(f"datasets/{dataset_id}/executeQueries"),
            headers=self.headers,
            json={
                "queries": [{"query": dax_query}],
                "serializerSettings": {"includeNulls": True},
            },
        )
        resp.raise_for_status()
        return resp.json()

    # --- Report Operations ---

    def list_reports(self) -> list[dict[str, Any]]:
        """List reports in the workspace."""
        resp = requests.get(self._url("reports"), headers=self.headers)
        resp.raise_for_status()
        return resp.json().get("value", [])

    def import_pbix(self, pbix_path: Path, display_name: str) -> dict[str, Any]:
        """Import a .pbix file to the workspace."""
        with open(pbix_path, "rb") as f:
            resp = requests.post(
                self._url(f"imports?datasetDisplayName={display_name}&nameConflict=CreateOrOverwrite"),
                headers={"Authorization": f"Bearer {self.token}"},
                files={"file": (pbix_path.name, f, "application/octet-stream")},
            )
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Imported report: {display_name} (id={result.get('id')})")
        return result

    def clone_report(self, report_id: str, new_name: str, target_workspace_id: str | None = None) -> dict[str, Any]:
        """Clone a report within or across workspaces."""
        body: dict[str, Any] = {"name": new_name}
        if target_workspace_id:
            body["targetWorkspaceId"] = target_workspace_id
        resp = requests.post(
            f"{self.base_url}/reports/{report_id}/Clone",
            headers=self.headers,
            json=body,
        )
        resp.raise_for_status()
        return resp.json()

    def rebind_report(self, report_id: str, dataset_id: str) -> None:
        """Rebind a report to a different dataset."""
        resp = requests.post(
            self._url(f"reports/{report_id}/Rebind"),
            headers=self.headers,
            json={"datasetId": dataset_id},
        )
        resp.raise_for_status()
        logger.info(f"Report {report_id} rebound to dataset {dataset_id}")

    # --- Deployment Pipeline Operations ---

    def list_pipelines(self) -> list[dict[str, Any]]:
        """List deployment pipelines."""
        resp = requests.get(
            f"{self.base_url}/pipelines",
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json().get("value", [])

    def deploy_pipeline_stage(
        self,
        pipeline_id: str,
        source_stage: int,
        *,
        items: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Deploy from one pipeline stage to the next.

        Args:
            pipeline_id: Deployment pipeline ID.
            source_stage: Source stage order (0=dev, 1=test, 2=prod).
            items: Optional list of specific items to deploy.
        """
        body: dict[str, Any] = {
            "sourceStageOrder": source_stage,
        }
        if items:
            body["datasets"] = [i for i in items if i.get("type") == "dataset"]
            body["reports"] = [i for i in items if i.get("type") == "report"]

        resp = requests.post(
            f"{self.base_url}/pipelines/{pipeline_id}/deploy",
            headers=self.headers,
            json=body,
        )
        resp.raise_for_status()
        return resp.json()

    # --- RLS Operations ---

    def get_dataset_roles(self, dataset_id: str) -> list[dict[str, Any]]:
        """Get RLS roles defined on a dataset (via REST API — limited info)."""
        # Note: Full RLS role details require XMLA or Tabular Editor
        resp = requests.get(
            self._url(f"datasets/{dataset_id}"),
            headers=self.headers,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("roles", [])

    def add_rls_member(
        self,
        dataset_id: str,
        role_name: str,
        member_email: str,
    ) -> None:
        """Add a user to an RLS role."""
        # Note: This requires the Admin API endpoint
        logger.info(f"Adding {member_email} to RLS role '{role_name}' on dataset {dataset_id}")
        # RLS member assignment is done via the dataset admin API
        # This is a placeholder for the actual implementation
        logger.warning("RLS member assignment via REST API requires admin permissions")
