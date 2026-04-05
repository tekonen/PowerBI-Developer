"""Authentication middleware for Supabase JWT validation.

When Supabase is not configured, all requests pass through unauthenticated
(local development mode). When configured, validates JWT from cookies or
Authorization header and redirects unauthenticated users to /login.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = frozenset({"/login", "/auth/callback", "/health"})
_PUBLIC_PREFIXES = ("/static/", "/auth/")


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate Supabase JWT on every request (skipped in local mode)."""

    async def dispatch(self, request: Request, call_next):
        from pbi_developer.web.supabase_client import is_supabase_configured

        # Local dev mode — no auth required
        if not is_supabase_configured():
            request.state.user = None
            return await call_next(request)

        path = request.url.path

        # Public routes — no auth needed
        if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            request.state.user = None
            return await call_next(request)

        # Extract JWT from cookie or Authorization header
        token = request.cookies.get("sb-access-token") or ""
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        if not token:
            return self._unauthorized(request)

        # Validate token with Supabase
        try:
            from pbi_developer.web.supabase_client import get_supabase

            client = get_supabase()
            user_resp = client.auth.get_user(token)
            request.state.user = user_resp.user
        except Exception:
            return self._unauthorized(request)

        # Check onboarding (skip for onboarding routes and API)
        if not path.startswith("/onboarding") and not path.startswith("/api/onboarding"):
            try:
                from pbi_developer.web.user_settings_service import has_completed_onboarding

                if not has_completed_onboarding(request.state.user.id) and self._is_html_request(request):
                    return RedirectResponse("/onboarding", status_code=302)
            except Exception:
                pass  # Don't block on onboarding check failure

        return await call_next(request)

    def _unauthorized(self, request: Request):
        if self._is_html_request(request):
            return RedirectResponse("/login", status_code=302)
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    @staticmethod
    def _is_html_request(request: Request) -> bool:
        accept = request.headers.get("Accept", "")
        return "text/html" in accept


def get_current_user(request: Request):
    """Extract the current user from request state. Returns None in local mode."""
    return getattr(request.state, "user", None)


def get_current_user_id(request: Request) -> str | None:
    """Extract the current user ID string from request state."""
    user = get_current_user(request)
    if user is None:
        return None
    return str(user.id)


def is_user_admin(user_id: str) -> bool:
    """Check whether *user_id* has admin privileges.

    Queries the ``user_settings`` table for an ``is_admin`` column.  Returns
    ``True`` in local mode (no Supabase configured) and ``False`` when the
    column does not exist yet or any error occurs.
    """
    from pbi_developer.web.supabase_client import is_supabase_configured

    if not is_supabase_configured():
        return True

    try:
        from pbi_developer.web.supabase_client import get_service_client

        client = get_service_client()
        if client is None:
            return False
        row = (
            client.table("user_settings")
            .select("is_admin")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if row.data and row.data.get("is_admin"):
            return True
    except Exception:
        logger.debug("is_user_admin check failed for %s", user_id, exc_info=True)
    return False


async def require_admin(request: Request):
    """FastAPI dependency that restricts access to admin users.

    Raises :class:`~fastapi.HTTPException` with status 403 when the
    authenticated user is not an admin.
    """
    from pbi_developer.web.supabase_client import is_supabase_configured

    # Local dev mode — always allow
    if not is_supabase_configured():
        return getattr(request.state, "user", None)

    user = getattr(request.state, "user", None)
    if user is None or not is_user_admin(str(user.id)):
        raise HTTPException(status_code=403, detail="Admin access required")

    return user
