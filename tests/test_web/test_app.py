"""Tests for the web GUI FastAPI application."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _get_client():
    from pbi_developer.web.app import app

    return TestClient(app)


class TestPageRoutes:
    """Test that page routes return 200 and render HTML."""

    def test_dashboard(self):
        resp = _get_client().get("/")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text

    def test_generate(self):
        resp = _get_client().get("/generate")
        assert resp.status_code == 200
        assert "Generate Report" in resp.text

    def test_refine(self):
        resp = _get_client().get("/refine")
        assert resp.status_code == 200
        assert "Refine" in resp.text

    def test_deploy(self):
        resp = _get_client().get("/deploy")
        assert resp.status_code == 200
        assert "Deploy" in resp.text

    def test_settings(self):
        resp = _get_client().get("/settings")
        assert resp.status_code == 200
        assert "Settings" in resp.text


class TestAPIRoutes:
    """Test API endpoints."""

    def test_list_runs_empty(self):
        resp = _get_client().get("/api/runs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_run_not_found(self):
        resp = _get_client().get("/api/runs/nonexistent")
        assert resp.status_code == 404

    def test_create_run_no_files(self):
        resp = _get_client().post("/api/runs", data={"report_name": "Test", "dry_run": "true"})
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data

    def test_settings_api(self):
        resp = _get_client().get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "claude_model" in data
        assert "api_key_set" in data

    def test_static_css(self):
        resp = _get_client().get("/static/app.css")
        assert resp.status_code == 200

    def test_static_js(self):
        resp = _get_client().get("/static/app.js")
        assert resp.status_code == 200


class TestRunStore:
    """Test the run store."""

    def test_create_and_get(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test Report")
        run = store.get_run(run_id)
        assert run is not None
        assert run.report_name == "Test Report"
        assert run.status == "pending"

    def test_update_run(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run()
        store.update_run(run_id, status="running")
        assert store.get_run(run_id).status == "running"

    def test_list_runs_sorted(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        store.create_run(report_name="First")
        store.create_run(report_name="Second")
        runs = store.list_runs()
        assert len(runs) == 2
        assert runs[0].report_name == "Second"  # most recent first

    def test_persistence(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store1 = RunStore(base_dir=tmp_path)
        run_id = store1.create_run(report_name="Persisted")

        # Reload from disk
        store2 = RunStore(base_dir=tmp_path)
        run = store2.get_run(run_id)
        assert run is not None
        assert run.report_name == "Persisted"

    def test_output_and_upload_dirs(self, tmp_path):
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run()
        assert store.get_output_dir(run_id).exists()
        assert store.get_upload_dir(run_id).exists()


class TestSSE:
    """Test SSE queue management."""

    def test_create_and_get_queue(self):
        from pbi_developer.web import sse

        q = sse.create_queue("test-run-1")
        assert q is not None
        assert sse.get_queue("test-run-1") is q
        sse.remove_queue("test-run-1")
        assert sse.get_queue("test-run-1") is None

    def test_remove_nonexistent(self):
        from pbi_developer.web import sse

        sse.remove_queue("does-not-exist")  # Should not raise


# ---------- Extended API tests ----------


class TestCreateRunWithFile:
    """Test POST /api/runs with a real file upload."""

    def test_create_run_with_brief_file(self, monkeypatch):
        """Uploading a brief file should create a run and return a run_id."""
        # Patch run_pipeline so the background task does not actually execute
        with patch("pbi_developer.web.app.asyncio.create_task") as mock_task:
            mock_task.return_value = MagicMock()
            mock_task.return_value.add_done_callback = MagicMock()

            client = _get_client()
            file_content = b"Build a sales dashboard with revenue KPIs."
            resp = client.post(
                "/api/runs",
                data={"report_name": "Sales Report", "dry_run": "true"},
                files={"brief": ("brief.txt", io.BytesIO(file_content), "text/plain")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert "error" not in data

    def test_create_run_with_multiple_files(self, monkeypatch):
        """Uploading multiple files should succeed."""
        with patch("pbi_developer.web.app.asyncio.create_task") as mock_task:
            mock_task.return_value = MagicMock()
            mock_task.return_value.add_done_callback = MagicMock()

            client = _get_client()
            resp = client.post(
                "/api/runs",
                data={"report_name": "Multi Report", "dry_run": "true"},
                files={
                    "brief": ("brief.txt", io.BytesIO(b"requirements"), "text/plain"),
                    "image": ("mockup.png", io.BytesIO(b"\x89PNGfake"), "image/png"),
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data

    def test_create_run_no_files_returns_400(self):
        """Submitting without files should return 400."""
        client = _get_client()
        resp = client.post(
            "/api/runs",
            data={"report_name": "Empty", "dry_run": "true"},
        )
        assert resp.status_code == 400
        assert "error" in resp.json()


class TestOutputListing:
    """Test GET /api/runs/{id}/output."""

    def test_output_listing_empty_run(self, tmp_path):
        """A fresh run with no output files returns an empty list."""
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")

        # Patch the app-level store so the endpoint uses our store
        with patch("pbi_developer.web.app.store", store):
            client = _get_client()
            resp = client.get(f"/api/runs/{run_id}/output")

        assert resp.status_code == 200
        data = resp.json()
        assert "files" in data
        assert isinstance(data["files"], list)
        assert len(data["files"]) == 0

    def test_output_listing_with_files(self, tmp_path):
        """Output listing should include files in the output directory."""
        from pbi_developer.web.run_store import RunStore

        store = RunStore(base_dir=tmp_path)
        run_id = store.create_run(report_name="Test")
        output_dir = store.get_output_dir(run_id)

        # Create some output files
        (output_dir / "report.json").write_text('{"name": "test"}')
        sub = output_dir / "definition"
        sub.mkdir()
        (sub / "page.json").write_text('{"page": 1}')

        with patch("pbi_developer.web.app.store", store):
            client = _get_client()
            resp = client.get(f"/api/runs/{run_id}/output")

        assert resp.status_code == 200
        files = resp.json()["files"]
        assert len(files) == 2
        assert "report.json" in files
        assert "definition/page.json" in files


class TestValidateEndpoint:
    """Test POST /api/validate."""

    def test_validate_valid_folder(self, tmp_path):
        """Validate endpoint should return results from validate_pbir_folder."""

        @dataclass
        class FakeResult:
            valid: bool = True
            files_checked: int = 5
            errors: list = field(default_factory=list)
            warnings: list = field(default_factory=list)

        # The validate endpoint imports validate_pbir_folder lazily inside the handler
        with patch(
            "pbi_developer.pbir.validator.validate_pbir_folder",
            return_value=FakeResult(),
        ):
            client = _get_client()
            resp = client.post(
                "/api/validate",
                json={"report_dir": str(tmp_path)},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["files_checked"] == 5
        assert data["errors"] == []
        assert data["warnings"] == []

    def test_validate_invalid_folder(self, tmp_path):
        """Validate endpoint should report errors for invalid PBIR."""

        @dataclass
        class FakeResult:
            valid: bool = False
            files_checked: int = 2
            errors: list = field(default_factory=lambda: ["Missing definition.pbir"])
            warnings: list = field(default_factory=list)

        with patch(
            "pbi_developer.pbir.validator.validate_pbir_folder",
            return_value=FakeResult(),
        ):
            client = _get_client()
            resp = client.post(
                "/api/validate",
                json={"report_dir": str(tmp_path)},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) == 1
        assert "definition.pbir" in data["errors"][0]


class TestConnectEndpoint:
    """Test POST /api/connect/{target} with mocked auth."""

    def test_connect_powerbi_success(self):
        """Successful Power BI connection test."""
        with patch(
            "pbi_developer.connectors.auth.test_connection",
            return_value=(True, "Power BI authentication successful"),
        ):
            client = _get_client()
            resp = client.post("/api/connect/powerbi")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "successful" in data["message"]

    def test_connect_powerbi_failure(self):
        """Failed Power BI connection test."""
        with patch(
            "pbi_developer.connectors.auth.test_connection",
            return_value=(False, "Power BI auth failed: Missing credentials"),
        ):
            client = _get_client()
            resp = client.post("/api/connect/powerbi")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "failed" in data["message"]

    def test_connect_unknown_target(self):
        """Connecting to an unknown target should still call test_connection."""
        with patch(
            "pbi_developer.connectors.auth.test_connection",
            return_value=(False, "Unknown target: foobar"),
        ):
            client = _get_client()
            resp = client.post("/api/connect/foobar")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
