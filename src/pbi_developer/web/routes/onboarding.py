"""Onboarding wizard routes for new user setup."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

router = APIRouter()


def _get_templates():
    from pbi_developer.web.app import templates

    return templates


@router.get("/onboarding")
async def page_onboarding(request: Request):
    """Render the onboarding wizard page."""
    from pbi_developer.web.supabase_client import is_supabase_configured

    if not is_supabase_configured():
        return RedirectResponse("/", status_code=302)

    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse("/login", status_code=302)

    return _get_templates().TemplateResponse(
        name="onboarding.html",
        request=request,
        context={"user_email": user.email},
    )


@router.post("/api/onboarding/step/{step_num}")
async def api_onboarding_step(step_num: int, request: Request):
    """Save data for a specific onboarding step (1-4)."""
    from pbi_developer.web.auth import get_current_user_id

    user_id = get_current_user_id(request)
    if not user_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    if step_num not in (1, 2, 3, 4):
        return JSONResponse({"error": "Invalid step number"}, status_code=400)

    body = await request.json()
    try:
        from pbi_developer.web.user_settings_service import save_onboarding_step

        save_onboarding_step(user_id, step_num, body)
        return {"success": True, "step": step_num}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/onboarding/status")
async def api_onboarding_status(request: Request):
    """Return which onboarding steps are complete."""
    from pbi_developer.web.auth import get_current_user_id

    user_id = get_current_user_id(request)
    if not user_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        from pbi_developer.web.user_settings_service import get_user_settings

        settings = get_user_settings(user_id)
        if not settings:
            return {"steps_completed": [], "onboarding_completed": False}

        completed = []
        if settings.get("claude_api_key_encrypted") or settings.get("claude_api_key"):
            completed.append(1)
        if settings.get("pbi_tenant_id_encrypted") or settings.get("pbi_workspace_id"):
            completed.append(2)
        if settings.get("sf_account_encrypted") or settings.get("sf_warehouse"):
            completed.append(3)
        if settings.get("color_palette"):
            completed.append(4)

        return {
            "steps_completed": completed,
            "onboarding_completed": settings.get("onboarding_completed", False),
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/onboarding/complete")
async def api_onboarding_complete(request: Request):
    """Mark onboarding as completed for the current user."""
    from pbi_developer.web.auth import get_current_user_id

    user_id = get_current_user_id(request)
    if not user_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        from pbi_developer.web.user_settings_service import complete_onboarding

        complete_onboarding(user_id)
        return {"success": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
