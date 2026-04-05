"""Authentication middleware for Supabase JWT validation.

When Supabase is not configured, all requests pass through unauthenticated
(local development mode). When configured, validates JWT from cookies or
Authorization header and redirects unauthenticated users to /login.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

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
