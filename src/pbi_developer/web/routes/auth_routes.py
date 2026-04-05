"""Authentication routes: login, register, OAuth callback, logout."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter()


def _get_templates():
    from pbi_developer.web.app import templates

    return templates


@router.get("/login")
async def page_login(request: Request):
    """Render the login page."""
    from pbi_developer.web.supabase_client import is_supabase_configured

    if not is_supabase_configured():
        return RedirectResponse("/", status_code=302)

    from pbi_developer.config import settings

    return _get_templates().TemplateResponse(
        name="login.html",
        request=request,
        context={
            "supabase_url": settings.supabase.url,
            "supabase_anon_key": settings.supabase.anon_key,
        },
    )


@router.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle OAuth redirect. The actual token exchange happens client-side
    via the Supabase JS SDK; this page extracts tokens from the URL hash
    and sets the cookie."""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head><title>Signing in...</title></head>
    <body>
    <p>Signing in...</p>
    <script>
        // Supabase OAuth returns tokens in the URL hash
        const hash = window.location.hash.substring(1);
        const params = new URLSearchParams(hash);
        const accessToken = params.get('access_token');
        const refreshToken = params.get('refresh_token');

        if (accessToken) {
            // Set cookie for server-side auth
            document.cookie = `sb-access-token=${accessToken}; path=/; SameSite=Lax; max-age=3600`;
            if (refreshToken) {
                document.cookie = `sb-refresh-token=${refreshToken}; path=/; SameSite=Lax; max-age=604800`;
            }
            window.location.href = '/';
        } else {
            // Try query params (email confirmation flow)
            const qp = new URLSearchParams(window.location.search);
            if (qp.get('error')) {
                document.body.innerHTML = '<p>Login error: ' + qp.get('error_description') + '</p>';
            } else {
                window.location.href = '/login';
            }
        }
    </script>
    </body>
    </html>
    """)


@router.post("/auth/login")
async def auth_login(request: Request):
    """Email/password login via Supabase."""
    from pbi_developer.web.supabase_client import get_supabase

    client = get_supabase()
    if not client:
        return JSONResponse({"error": "Auth not configured"}, status_code=500)

    body = await request.json()
    email = body.get("email", "")
    password = body.get("password", "")

    try:
        resp = client.auth.sign_in_with_password({"email": email, "password": password})
        session = resp.session
        return JSONResponse(
            {
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
                "user": {"id": str(resp.user.id), "email": resp.user.email},
            }
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=401)


@router.post("/auth/register")
async def auth_register(request: Request):
    """Email/password registration via Supabase."""
    from pbi_developer.web.supabase_client import get_supabase

    client = get_supabase()
    if not client:
        return JSONResponse({"error": "Auth not configured"}, status_code=500)

    body = await request.json()
    email = body.get("email", "")
    password = body.get("password", "")

    try:
        resp = client.auth.sign_up({"email": email, "password": password})
        return JSONResponse(
            {
                "message": "Registration successful. Check your email for confirmation.",
                "user": {"id": str(resp.user.id), "email": resp.user.email} if resp.user else None,
            }
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/auth/logout")
async def auth_logout():
    """Clear auth cookies and redirect to login."""
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("sb-access-token")
    response.delete_cookie("sb-refresh-token")
    return response


@router.get("/health")
async def health():
    """Unprotected health check endpoint."""
    return {"status": "ok"}
