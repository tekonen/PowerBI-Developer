"""Tests for store factory."""

from __future__ import annotations

from unittest.mock import patch


class TestStoreFactory:
    """Test that get_store returns the correct backend."""

    @patch("pbi_developer.web.supabase_client.is_supabase_configured", return_value=False)
    def test_returns_local_store_when_no_supabase(self, mock):
        from pbi_developer.web.run_store import RunStore
        from pbi_developer.web.store_factory import get_store

        store = get_store(user_id=None)
        assert isinstance(store, RunStore)

    @patch("pbi_developer.web.supabase_client.is_supabase_configured", return_value=False)
    def test_returns_local_store_even_with_user_id(self, mock):
        from pbi_developer.web.run_store import RunStore
        from pbi_developer.web.store_factory import get_store

        store = get_store(user_id="some-user")
        assert isinstance(store, RunStore)

    @patch("pbi_developer.web.supabase_client.is_supabase_configured", return_value=False)
    def test_returns_local_store_no_user(self, mock):
        from pbi_developer.web.run_store import RunStore
        from pbi_developer.web.store_factory import get_store

        store = get_store()
        assert isinstance(store, RunStore)

    @patch("pbi_developer.web.supabase_client.is_supabase_configured", return_value=True)
    def test_returns_supabase_store_when_configured(self, mock):
        from pbi_developer.web.store_factory import get_store
        from pbi_developer.web.supabase_run_store import SupabaseRunStore

        store = get_store(user_id="user-123")
        assert isinstance(store, SupabaseRunStore)

    @patch("pbi_developer.web.supabase_client.is_supabase_configured", return_value=True)
    def test_returns_local_store_when_configured_but_no_user(self, mock):
        from pbi_developer.web.run_store import RunStore
        from pbi_developer.web.store_factory import get_store

        store = get_store(user_id=None)
        assert isinstance(store, RunStore)
