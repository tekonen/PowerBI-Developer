"""Supabase-backed run store.

Implements the same interface as RunStore but persists to Supabase PostgreSQL.
All operations are scoped to a specific user_id.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from pbi_developer.web.models import RunInfo


class SupabaseRunStore:
    """Manages pipeline run history in Supabase, scoped to a user."""

    def __init__(self, user_id: str, base_dir: Path | None = None):
        self.user_id = user_id
        self.base_dir = base_dir or Path.home() / ".pbi-dev"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _client(self):
        from pbi_developer.web.supabase_client import get_service_client

        client = get_service_client()
        if not client:
            raise RuntimeError("Supabase service client not configured")
        return client

    def create_run(self, *, report_name: str = "Report", dry_run: bool = True) -> str:
        run_id = uuid.uuid4().hex[:12]
        now = datetime.now(UTC).isoformat()
        self._client().table("runs").insert(
            {
                "run_id": run_id,
                "user_id": self.user_id,
                "created_at": now,
                "report_name": report_name,
                "dry_run": dry_run,
                "status": "pending",
                "wizard_step": "init",
            }
        ).execute()
        return run_id

    def update_run(self, run_id: str, **kwargs: object) -> None:
        updates = {}
        for key, value in kwargs.items():
            if key in RunInfo.model_fields:
                updates[key] = value
        if updates:
            self._client().table("runs").update(updates).eq("run_id", run_id).eq("user_id", self.user_id).execute()

    def get_run(self, run_id: str) -> RunInfo | None:
        resp = self._client().table("runs").select("*").eq("run_id", run_id).eq("user_id", self.user_id).execute()
        if not resp.data:
            return None
        row = resp.data[0]
        return RunInfo(
            run_id=row["run_id"],
            created_at=row["created_at"],
            report_name=row.get("report_name", "Report"),
            dry_run=row.get("dry_run", True),
            status=row.get("status", "pending"),
            stages=row.get("stages") or {},
            output_path=row.get("output_path"),
            tokens=row.get("tokens") or {"input_tokens": 0, "output_tokens": 0},
            cost_usd=float(row.get("cost_usd", 0)),
            latency_ms=float(row.get("latency_ms", 0)),
            error=row.get("error"),
            wizard_step=row.get("wizard_step", "init"),
        )

    def list_runs(self) -> list[RunInfo]:
        resp = (
            self._client()
            .table("runs")
            .select("*")
            .eq("user_id", self.user_id)
            .order("created_at", desc=True)
            .execute()
        )
        runs = []
        for row in resp.data or []:
            runs.append(
                RunInfo(
                    run_id=row["run_id"],
                    created_at=row["created_at"],
                    report_name=row.get("report_name", "Report"),
                    dry_run=row.get("dry_run", True),
                    status=row.get("status", "pending"),
                    stages=row.get("stages") or {},
                    output_path=row.get("output_path"),
                    tokens=row.get("tokens") or {"input_tokens": 0, "output_tokens": 0},
                    cost_usd=float(row.get("cost_usd", 0)),
                    latency_ms=float(row.get("latency_ms", 0)),
                    error=row.get("error"),
                    wizard_step=row.get("wizard_step", "init"),
                )
            )
        return runs

    def get_output_dir(self, run_id: str) -> Path:
        path = self.base_dir / "runs" / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_upload_dir(self, run_id: str) -> Path:
        path = self.base_dir / "runs" / run_id / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def record_file(self, run_id: str, file_type: str, storage_path: str, original_name: str) -> None:
        """Record an uploaded file in the run_files table."""
        self._client().table("run_files").insert(
            {
                "run_id": run_id,
                "file_type": file_type,
                "storage_path": storage_path,
                "original_name": original_name,
            }
        ).execute()
