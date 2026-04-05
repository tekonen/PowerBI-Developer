"""Tests for auth middleware and helpers."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


class TestAuthHelpers:
    """Test get_current_user and get_current_user_id helpers."""

    def test_get_current_user_none(self):
        from pbi_developer.web.auth import get_current_user

        request = MagicMock()
        request.state = MagicMock(spec=[])  # no 'user' attribute
        assert get_current_user(request) is None

    def test_get_current_user_id_none(self):
        from pbi_developer.web.auth import get_current_user_id

        request = MagicMock()
        request.state = MagicMock(spec=[])
        assert get_current_user_id(request) is None

    def test_get_current_user_with_user(self):
        from pbi_developer.web.auth import get_current_user

        user = MagicMock()
        request = MagicMock()
        request.state.user = user
        assert get_current_user(request) is user

    def test_get_current_user_id_with_user(self):
        from pbi_developer.web.auth import get_current_user_id

        user = MagicMock()
        user.id = "abc-123"
        request = MagicMock()
        request.state.user = user
        assert get_current_user_id(request) == "abc-123"


class TestIsUserAdmin:
    """Test is_user_admin function."""

    @patch("pbi_developer.web.supabase_client.is_supabase_configured", return_value=False)
    def test_local_mode_returns_true(self, mock_configured):
        from pbi_developer.web.auth import is_user_admin

        assert is_user_admin("any-user") is True

    @patch("pbi_developer.web.supabase_client.is_supabase_configured", return_value=True)
    @patch("pbi_developer.web.supabase_client.get_service_client", return_value=None)
    def test_returns_false_when_no_service_client(self, mock_client, mock_configured):
        from pbi_developer.web.auth import is_user_admin

        assert is_user_admin("user-1") is False


class TestRequireAdmin:
    """Test require_admin FastAPI dependency."""

    @patch("pbi_developer.web.supabase_client.is_supabase_configured", return_value=False)
    def test_local_mode_allows_all(self, mock_configured):
        from pbi_developer.web.auth import require_admin

        request = MagicMock()
        request.state = MagicMock(spec=[])
        result = asyncio.run(require_admin(request))
        assert result is None

    @patch("pbi_developer.web.supabase_client.is_supabase_configured", return_value=True)
    def test_raises_403_when_no_user(self, mock_configured):
        from pbi_developer.web.auth import require_admin

        request = MagicMock()
        request.state = MagicMock(spec=[])  # no user
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_admin(request))
        assert exc_info.value.status_code == 403


class TestAuthMiddlewareLocalMode:
    """In local mode (no Supabase), all routes should pass through."""

    @patch("pbi_developer.web.supabase_client.is_supabase_configured", return_value=False)
    def test_local_mode_passes_through(self, mock_configured):
        from pbi_developer.web.app import app

        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200

    @patch("pbi_developer.web.supabase_client.is_supabase_configured", return_value=False)
    def test_local_mode_sets_user_none(self, mock_configured):
        """In local mode, middleware sets request.state.user to None."""
        from pbi_developer.web.app import app

        client = TestClient(app)
        resp = client.get("/settings")
        assert resp.status_code == 200
