"""Tests for the version control module."""

from __future__ import annotations

from pbi_developer.web.version_control import VersionManager


class TestVersionManager:
    def test_init_creates_repo(self, tmp_path):
        repo = tmp_path / "test-repo"
        VersionManager(repo)
        assert (repo / ".git").is_dir()

    def test_initial_commit_exists(self, tmp_path):
        repo = tmp_path / "test-repo"
        vm = VersionManager(repo)
        versions = vm.list_versions()
        assert len(versions) >= 1
        assert "Initial commit" in versions[-1].message

    def test_commit_version(self, tmp_path):
        repo = tmp_path / "test-repo"
        vm = VersionManager(repo)
        (repo / "test.json").write_text('{"key": "value"}')
        commit_hash = vm.commit_version("Added test file", "run-123")
        assert commit_hash is not None
        versions = vm.list_versions()
        assert versions[0].message == "Added test file"
        assert versions[0].run_id == "run-123"

    def test_commit_no_changes(self, tmp_path):
        repo = tmp_path / "test-repo"
        vm = VersionManager(repo)
        result = vm.commit_version("No changes")
        assert result is None

    def test_list_versions(self, tmp_path):
        repo = tmp_path / "test-repo"
        vm = VersionManager(repo)
        (repo / "a.txt").write_text("a")
        vm.commit_version("First change")
        (repo / "b.txt").write_text("b")
        vm.commit_version("Second change")
        versions = vm.list_versions()
        assert len(versions) >= 3  # initial + 2 changes
        assert versions[0].message == "Second change"
        assert versions[1].message == "First change"

    def test_undo(self, tmp_path):
        repo = tmp_path / "test-repo"
        vm = VersionManager(repo)
        (repo / "file.txt").write_text("v1")
        vm.commit_version("Version 1")
        (repo / "file.txt").write_text("v2")
        vm.commit_version("Version 2")

        result = vm.undo()
        assert result is not None
        # File should be reverted
        assert (repo / "file.txt").read_text() == "v1"

    def test_redo(self, tmp_path):
        repo = tmp_path / "test-repo"
        vm = VersionManager(repo)
        (repo / "file.txt").write_text("v1")
        vm.commit_version("Version 1")
        (repo / "file.txt").write_text("v2")
        vm.commit_version("Version 2")

        vm.undo()
        assert (repo / "file.txt").read_text() == "v1"

        result = vm.redo()
        assert result is not None
        assert (repo / "file.txt").read_text() == "v2"

    def test_undo_at_start_returns_none(self, tmp_path):
        repo = tmp_path / "test-repo"
        vm = VersionManager(repo)
        result = vm.undo()
        assert result is None

    def test_redo_without_undo_returns_none(self, tmp_path):
        repo = tmp_path / "test-repo"
        vm = VersionManager(repo)
        result = vm.redo()
        assert result is None

    def test_set_and_get_remote(self, tmp_path):
        repo = tmp_path / "test-repo"
        vm = VersionManager(repo)
        vm.set_remote("https://bitbucket.org/test/repo.git")
        assert vm.get_remote() == "https://bitbucket.org/test/repo.git"

    def test_get_remote_none(self, tmp_path):
        repo = tmp_path / "test-repo"
        vm = VersionManager(repo)
        assert vm.get_remote() is None

    def test_can_redo_property(self, tmp_path):
        repo = tmp_path / "test-repo"
        vm = VersionManager(repo)
        assert not vm.can_redo
        (repo / "file.txt").write_text("v1")
        vm.commit_version("Version 1")
        (repo / "file.txt").write_text("v2")
        vm.commit_version("Version 2")
        vm.undo()
        assert vm.can_redo

    def test_get_current_version(self, tmp_path):
        repo = tmp_path / "test-repo"
        vm = VersionManager(repo)
        v = vm.get_current_version()
        assert v is not None
        assert v.commit_hash

    def test_get_diff(self, tmp_path):
        repo = tmp_path / "test-repo"
        vm = VersionManager(repo)
        (repo / "file.txt").write_text("old content")
        vm.commit_version("Old")
        hash1 = vm.list_versions()[0].commit_hash
        (repo / "file.txt").write_text("new content")
        vm.commit_version("New")
        hash2 = vm.list_versions()[0].commit_hash
        diff = vm.get_diff(hash1, hash2)
        assert "old content" in diff or "new content" in diff


class TestVersionsPage:
    def test_versions_page_renders(self):
        from fastapi.testclient import TestClient

        from pbi_developer.web.app import app

        client = TestClient(app)
        resp = client.get("/versions")
        assert resp.status_code == 200
        assert "Version History" in resp.text

    def test_versions_api(self):
        from fastapi.testclient import TestClient

        from pbi_developer.web.app import app

        client = TestClient(app)
        resp = client.get("/api/versions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
