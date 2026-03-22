"""Tests for artifact persistence and run_from_stage."""

from __future__ import annotations

import json


class TestArtifactPersistence:
    """Test _save_artifact and _save_text_artifact helpers."""

    def test_save_artifact_writes_json(self, tmp_path):
        from pbi_developer.pipeline.orchestrator import _save_artifact

        data = {"pages": [{"page_name": "Test"}]}
        _save_artifact(tmp_path, "wireframe", data)

        artifact_path = tmp_path / "artifacts" / "wireframe.json"
        assert artifact_path.exists()
        loaded = json.loads(artifact_path.read_text())
        assert loaded == data

    def test_save_text_artifact_writes_markdown(self, tmp_path):
        from pbi_developer.pipeline.orchestrator import _save_text_artifact

        text = "# Semantic Model\n\nTable: Employee"
        _save_text_artifact(tmp_path, "model_metadata", text)

        artifact_path = tmp_path / "artifacts" / "model_metadata.md"
        assert artifact_path.exists()
        assert artifact_path.read_text(encoding="utf-8") == text

    def test_save_artifact_creates_directories(self, tmp_path):
        from pbi_developer.pipeline.orchestrator import _save_artifact

        _save_artifact(tmp_path, "brief", {"title": "test"})
        assert (tmp_path / "artifacts").is_dir()


class TestRunFromStage:
    """Test run_from_stage validation logic."""

    def test_invalid_stage_returns_error(self, tmp_path):
        from pbi_developer.pipeline.orchestrator import run_from_stage

        result = run_from_stage(
            stage="ingestion",
            output_dir=tmp_path,
            corrections="fix it",
        )
        assert not result.success
        assert "Invalid stage" in result.error

    def test_missing_artifacts_returns_error(self, tmp_path):
        from pbi_developer.pipeline.orchestrator import run_from_stage

        result = run_from_stage(
            stage="wireframe",
            output_dir=tmp_path,
            corrections="fix it",
        )
        assert not result.success
        assert "No artifacts found" in result.error

    def test_refinable_stages_constant(self):
        from pbi_developer.pipeline.orchestrator import REFINABLE_STAGES

        assert {"wireframe", "field_mapping", "dax", "rls"} == REFINABLE_STAGES
