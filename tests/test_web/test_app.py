"""Tests for the web GUI FastAPI application."""

from __future__ import annotations

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
