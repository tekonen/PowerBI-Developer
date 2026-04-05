"""Tests for Supabase run store (mocked)."""

from __future__ import annotations

from pbi_developer.web.supabase_run_store import SupabaseRunStore


class TestSupabaseRunStoreInit:
    """Test store initialisation and directory helpers."""

    def test_init_creates_base_dir(self, tmp_path):
        store = SupabaseRunStore(user_id="test-user", base_dir=tmp_path / "new")
        assert store.base_dir.exists()

    def test_stores_user_id(self, tmp_path):
        store = SupabaseRunStore(user_id="u-42", base_dir=tmp_path)
        assert store.user_id == "u-42"

    def test_get_output_dir(self, tmp_path):
        store = SupabaseRunStore(user_id="test-user", base_dir=tmp_path)
        d = store.get_output_dir("run123")
        assert d.exists()
        assert "run123" in str(d)

    def test_get_upload_dir(self, tmp_path):
        store = SupabaseRunStore(user_id="test-user", base_dir=tmp_path)
        d = store.get_upload_dir("run123")
        assert d.exists()
        assert "uploads" in str(d)

    def test_output_dir_is_under_runs(self, tmp_path):
        store = SupabaseRunStore(user_id="test-user", base_dir=tmp_path)
        d = store.get_output_dir("abc")
        assert d == tmp_path / "runs" / "abc"

    def test_upload_dir_is_under_output(self, tmp_path):
        store = SupabaseRunStore(user_id="test-user", base_dir=tmp_path)
        d = store.get_upload_dir("abc")
        assert d == tmp_path / "runs" / "abc" / "uploads"
