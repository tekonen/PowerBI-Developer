"""Run history persistence.

Stores pipeline run metadata in memory and persists to ~/.pbi-dev/runs.json.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pbi_developer.web.models import RunInfo


class RunStore:
    """Manages pipeline run history."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or Path.home() / ".pbi-dev"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self.base_dir / "runs.json"
        self._runs: dict[str, RunInfo] = {}
        self._load()

    def _load(self) -> None:
        if self._db_path.exists():
            data = json.loads(self._db_path.read_text(encoding="utf-8"))
            for item in data:
                run = RunInfo(**item)
                self._runs[run.run_id] = run

    def _persist(self) -> None:
        data = [run.model_dump(mode="json") for run in self._runs.values()]
        tmp = self._db_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(self._db_path)

    def create_run(self, *, report_name: str = "Report", dry_run: bool = True) -> str:
        run_id = uuid.uuid4().hex[:12]
        run = RunInfo(
            run_id=run_id,
            created_at=datetime.now(UTC),
            report_name=report_name,
            dry_run=dry_run,
            status="pending",
        )
        self._runs[run_id] = run
        self._persist()
        return run_id

    def update_run(self, run_id: str, **kwargs: object) -> None:
        run = self._runs.get(run_id)
        if not run:
            return
        for key, value in kwargs.items():
            if hasattr(run, key):
                setattr(run, key, value)
        self._persist()

    def get_run(self, run_id: str) -> RunInfo | None:
        return self._runs.get(run_id)

    def list_runs(self) -> list[RunInfo]:
        return sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)

    def get_output_dir(self, run_id: str) -> Path:
        path = self.base_dir / "runs" / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_upload_dir(self, run_id: str) -> Path:
        path = self.base_dir / "runs" / run_id / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path
