"""Tests for the wizard step API endpoints and step-runner functions."""

from __future__ import annotations

import io
import json
from unittest.mock import patch

from fastapi.testclient import TestClient


def _get_client():
    from pbi_developer.web.app import app

    return TestClient(app)


def _create_run_with_artifacts(store, brief=None, wireframe=None, field_mapped=None,
                                model_metadata=None, dax=None, rls=None):
    """Helper: create a run and populate its artifacts directory."""
    run_id = store.create_run(report_name="Test Wizard")
    output_dir = store.get_output_dir(run_id)
    artifacts = output_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    if brief is not None:
        (artifacts / "brief.json").write_text(json.dumps(brief))
    if wireframe is not None:
        (artifacts / "wireframe.json").write_text(json.dumps(wireframe))
    if field_mapped is not None:
        (artifacts / "field_mapped.json").write_text(json.dumps(field_mapped))
    if model_metadata is not None:
        (artifacts / "model_metadata.md").write_text(model_metadata)
    if dax is not None:
        (artifacts / "dax_measures.json").write_text(json.dumps(dax))
    if rls is not None:
        (artifacts / "rls_config.json").write_text(json.dumps(rls))

    return run_id, output_dir


class TestGeneratePageWizard:
    """Test that the generate page renders the wizard template."""

    def test_generate_page_has_wizard_steps(self):
        resp = _get_client().get("/generate")
        assert resp.status_code == 200
        assert "step-indicator" in resp.text
        assert "step-init" in resp.text
        assert "wizard.js" in resp.text
        assert "wireframe-mockup.js" in resp.text

    def test_generate_page_has_all_step_panels(self):
        resp = _get_client().get("/generate")
        text = resp.text
        for step in ["init", "ingestion", "metadata", "wireframe",
                      "field_mapping", "dax", "qa", "pbir", "rls", "publish"]:
            assert f'id="step-{step}"' in text


class TestStepIngest:
    """Test POST /api/runs/{id}/step/ingest."""

    def test_ingest_no_run(self):
        resp = _get_client().post("/api/runs/nonexistent/step/ingest")
        assert resp.status_code == 404

    def test_ingest_no_files(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")

        with patch("pbi_developer.web.app.store", store):
            resp = _get_client().post(f"/api/runs/{run_id}/step/ingest")

        assert resp.status_code == 400

    def test_ingest_success(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")
        upload_dir = store.get_upload_dir(run_id)
        (upload_dir / "brief.txt").write_text("Build a dashboard")

        fake_brief = {"report_title": "Test", "pages": [], "kpis": [], "analytical_questions": []}

        with (
            patch("pbi_developer.web.app.store", store),
            patch("pbi_developer.pipeline.orchestrator.run_step_ingest", return_value=fake_brief),
        ):
            resp = _get_client().post(f"/api/runs/{run_id}/step/ingest")

        assert resp.status_code == 200
        data = resp.json()
        assert "brief" in data
        assert data["brief"]["report_title"] == "Test"


class TestStepMetadata:
    """Test metadata upload and fetch endpoints."""

    def test_metadata_upload(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")

        fake_metadata = "# Semantic Model\n## Table: Sales\n| Column | Type |"

        with (
            patch("pbi_developer.web.app.store", store),
            patch(
                "pbi_developer.pipeline.orchestrator.run_step_metadata_from_file",
                return_value=fake_metadata,
            ),
        ):
            client = _get_client()
            resp = client.post(
                f"/api/runs/{run_id}/step/metadata/upload",
                files={"model_metadata": ("model.md", io.BytesIO(b"# Model"), "text/markdown")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "metadata" in data
        assert "Semantic Model" in data["metadata"]

    def test_metadata_fetch(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")

        with (
            patch("pbi_developer.web.app.store", store),
            patch(
                "pbi_developer.pipeline.orchestrator.run_step_metadata_from_dataset",
                return_value="# Model metadata",
            ),
        ):
            resp = _get_client().post(
                f"/api/runs/{run_id}/step/metadata/fetch",
                json={"dataset_id": "abc-123"},
            )

        assert resp.status_code == 200
        assert "metadata" in resp.json()


class TestStepWireframe:
    """Test POST /api/runs/{id}/step/wireframe."""

    def test_wireframe_success(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")

        fake_wireframe = {"pages": [{"page_name": "Overview", "visuals": []}]}

        with (
            patch("pbi_developer.web.app.store", store),
            patch("pbi_developer.pipeline.orchestrator.run_step_wireframe", return_value=fake_wireframe),
        ):
            resp = _get_client().post(f"/api/runs/{run_id}/step/wireframe")

        assert resp.status_code == 200
        data = resp.json()
        assert "wireframe" in data
        assert data["wireframe"]["pages"][0]["page_name"] == "Overview"


class TestStepFieldMapping:
    """Test POST /api/runs/{id}/step/field-mapping."""

    def test_field_mapping_success(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")

        fake_result = {"pages": [{"page_name": "P1", "visuals": []}]}

        with (
            patch("pbi_developer.web.app.store", store),
            patch("pbi_developer.pipeline.orchestrator.run_step_field_mapping", return_value=fake_result),
        ):
            resp = _get_client().post(f"/api/runs/{run_id}/step/field-mapping")

        assert resp.status_code == 200
        assert "field_mapped" in resp.json()


class TestStepDax:
    """Test POST /api/runs/{id}/step/dax."""

    def test_dax_success(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")

        fake_dax = {"measures": [{"name": "Total Revenue", "table": "Sales", "expression": "SUM(Sales[Revenue])"}]}

        with (
            patch("pbi_developer.web.app.store", store),
            patch("pbi_developer.pipeline.orchestrator.run_step_dax", return_value=fake_dax),
        ):
            resp = _get_client().post(f"/api/runs/{run_id}/step/dax")

        assert resp.status_code == 200
        data = resp.json()
        assert "dax" in data
        assert len(data["dax"]["measures"]) == 1


class TestStepQA:
    """Test POST /api/runs/{id}/step/qa."""

    def test_qa_success(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")

        fake_qa = {"passed": True, "summary": "All checks passed", "issues": []}

        with (
            patch("pbi_developer.web.app.store", store),
            patch("pbi_developer.pipeline.orchestrator.run_step_qa", return_value=fake_qa),
        ):
            resp = _get_client().post(f"/api/runs/{run_id}/step/qa")

        assert resp.status_code == 200
        assert resp.json()["qa"]["passed"] is True


class TestStepCorrect:
    """Test POST /api/runs/{id}/step/{stage}/correct."""

    def test_correct_wireframe(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")

        fake_result = {"pages": [{"page_name": "Updated", "visuals": []}]}

        with (
            patch("pbi_developer.web.app.store", store),
            patch("pbi_developer.pipeline.orchestrator.run_step_wireframe", return_value=fake_result),
        ):
            resp = _get_client().post(
                f"/api/runs/{run_id}/step/wireframe/correct",
                json={"corrections": "Move the card to the top-right"},
            )

        assert resp.status_code == 200
        assert "result" in resp.json()

    def test_correct_invalid_stage(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")

        with patch("pbi_developer.web.app.store", store):
            resp = _get_client().post(
                f"/api/runs/{run_id}/step/ingestion/correct",
                json={"corrections": "change something"},
            )

        assert resp.status_code == 400


class TestStepAccept:
    """Test POST /api/runs/{id}/step/{stage}/accept."""

    def test_accept_advances_step(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")

        with (
            patch("pbi_developer.web.app.store", store),
            patch("pbi_developer.web.app._auto_commit"),
        ):
            resp = _get_client().post(f"/api/runs/{run_id}/step/ingestion/accept")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["next_step"] == "metadata"

    def test_accept_unknown_stage(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")

        with patch("pbi_developer.web.app.store", store):
            resp = _get_client().post(f"/api/runs/{run_id}/step/nonexistent/accept")

        assert resp.status_code == 400


class TestStepData:
    """Test GET /api/runs/{id}/step/{stage}/data."""

    def test_get_brief_data(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id, _output_dir = _create_run_with_artifacts(
            store, brief={"report_title": "Test", "pages": []}
        )

        with patch("pbi_developer.web.app.store", store):
            resp = _get_client().get(f"/api/runs/{run_id}/step/ingestion/data")

        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["report_title"] == "Test"

    def test_get_metadata_text(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id, _output_dir = _create_run_with_artifacts(
            store, model_metadata="# Semantic Model\nTest data"
        )

        with patch("pbi_developer.web.app.store", store):
            resp = _get_client().get(f"/api/runs/{run_id}/step/metadata/data")

        assert resp.status_code == 200
        assert "Semantic Model" in resp.json()["data"]

    def test_get_missing_artifact(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")
        # Ensure artifacts dir exists but is empty
        (store.get_output_dir(run_id) / "artifacts").mkdir(parents=True, exist_ok=True)

        with patch("pbi_developer.web.app.store", store):
            resp = _get_client().get(f"/api/runs/{run_id}/step/ingestion/data")

        assert resp.status_code == 200
        assert resp.json()["data"] is None


class TestDatasetBrowser:
    """Test GET /api/datasets and GET /api/datasets/{id}/metadata."""

    def test_list_datasets(self):
        fake_datasets = [{"id": "ds1", "name": "Sales"}]

        with patch("pbi_developer.connectors.powerbi_rest.PowerBIClient") as MockClient:
            MockClient.return_value.list_datasets.return_value = fake_datasets
            resp = _get_client().get("/api/datasets")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["datasets"]) == 1
        assert data["datasets"][0]["name"] == "Sales"

    def test_list_datasets_error(self):
        with patch("pbi_developer.connectors.powerbi_rest.PowerBIClient") as MockClient:
            MockClient.return_value.list_datasets.side_effect = Exception("Auth failed")
            resp = _get_client().get("/api/datasets")

        assert resp.status_code == 500
        assert "error" in resp.json()

    def test_get_dataset_metadata(self):
        from pbi_developer.connectors.xmla import SemanticModelMetadata

        fake = SemanticModelMetadata(model_name="Sales", tables=["Orders", "Products"])

        with patch("pbi_developer.connectors.xmla.fetch_metadata_via_rest", return_value=fake):
            resp = _get_client().get("/api/datasets/ds1/metadata")

        assert resp.status_code == 200
        data = resp.json()
        assert data["model_name"] == "Sales"
        assert "Orders" in data["tables"]


class TestSemanticModelMetadataToDict:
    """Test the to_dict() method on SemanticModelMetadata."""

    def test_to_dict(self):
        from pbi_developer.connectors.xmla import (
            ColumnMetadata,
            MeasureInfo,
            RelationshipInfo,
            SemanticModelMetadata,
        )

        meta = SemanticModelMetadata(
            model_name="Test",
            tables=["Sales"],
            columns=[ColumnMetadata(name="Revenue", table="Sales", data_type="Decimal")],
            measures=[MeasureInfo(name="Total", table="Sales", expression="SUM(Sales[Revenue])")],
            relationships=[
                RelationshipInfo(
                    from_table="Sales", from_column="ProductID",
                    to_table="Products", to_column="ID",
                )
            ],
        )

        d = meta.to_dict()
        assert d["model_name"] == "Test"
        assert len(d["tables"]) == 1
        assert len(d["columns"]) == 1
        assert d["columns"][0]["name"] == "Revenue"
        assert len(d["measures"]) == 1
        assert d["measures"][0]["expression"] == "SUM(Sales[Revenue])"
        assert len(d["relationships"]) == 1
        assert d["relationships"][0]["from_table"] == "Sales"


class TestWizardStepInRunInfo:
    """Test that wizard_step is tracked in RunInfo."""

    def test_wizard_step_default(self):
        from datetime import datetime

        from pbi_developer.web.models import RunInfo

        run = RunInfo(run_id="test", created_at=datetime.now())
        assert run.wizard_step == "init"

    def test_wizard_step_update(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")
        store.update_run(run_id, wizard_step="wireframe")
        run = store.get_run(run_id)
        assert run.wizard_step == "wireframe"
