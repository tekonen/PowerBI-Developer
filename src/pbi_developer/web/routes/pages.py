"""HTML page routes for the web GUI."""

from __future__ import annotations

from fastapi import APIRouter, Request

from pbi_developer.pipeline.stages import STAGE_LABELS
from pbi_developer.web.run_store import RunStore

router = APIRouter()


def _get_store() -> RunStore:
    from pbi_developer.web.app import store

    return store


def _get_store_for_request(request: Request) -> RunStore:
    """Return user-scoped store when Supabase is configured, otherwise global."""
    from pbi_developer.web.auth import get_current_user_id
    from pbi_developer.web.supabase_client import is_supabase_configured

    if is_supabase_configured():
        user_id = get_current_user_id(request)
        if user_id:
            from pbi_developer.web.store_factory import get_store

            return get_store(user_id)
    return _get_store()


def _get_templates():
    from pbi_developer.web.app import templates

    return templates


def _user_context(request: Request) -> dict:
    """Extract user context for template rendering."""
    user = getattr(request.state, "user", None)
    return {"user_email": user.email if user else None}


def _mask(value: str) -> str:
    if not value or len(value) <= 4:
        return "***"
    return f"***{value[-4:]}"


@router.get("/")
async def page_dashboard(request: Request):
    runs = _get_store_for_request(request).list_runs()
    return _get_templates().TemplateResponse(
        name="dashboard.html", request=request, context={"runs": runs, **_user_context(request)}
    )


@router.get("/generate")
async def page_generate(request: Request):
    return _get_templates().TemplateResponse(
        name="generate.html",
        request=request,
        context={"stages": STAGE_LABELS, "current_step": "init", **_user_context(request)},
    )


@router.get("/refine")
async def page_refine(request: Request):
    runs = [r for r in _get_store_for_request(request).list_runs() if r.status in ("completed", "failed")]
    return _get_templates().TemplateResponse(
        name="refine.html", request=request, context={"runs": runs, **_user_context(request)}
    )


@router.get("/deploy")
async def page_deploy(request: Request):
    runs = [r for r in _get_store_for_request(request).list_runs() if r.status == "completed"]
    return _get_templates().TemplateResponse(
        name="deploy.html", request=request, context={"runs": runs, **_user_context(request)}
    )


@router.get("/settings")
async def page_settings(request: Request):
    from pbi_developer.config import settings
    from pbi_developer.web.auth import get_current_user_id

    config = {
        "claude_model": settings.claude.model,
        "api_base_url": settings.claude.base_url or "(default)",
        "workspace_id": _mask(settings.powerbi.workspace_id),
        "tenant_id": _mask(settings.powerbi.tenant_id),
        "client_id": _mask(settings.powerbi.client_id),
        "api_key_set": bool(settings.claude.api_key),
        "max_qa_retries": settings.pipeline.max_qa_retries,
        "require_human_review": settings.pipeline.require_human_review,
    }

    # Load user-specific overrides if authenticated
    user_config = None
    user_id = get_current_user_id(request)
    if user_id:
        try:
            from pbi_developer.web.supabase_client import is_supabase_configured

            if is_supabase_configured():
                from pbi_developer.web.user_settings_service import get_user_settings

                raw = get_user_settings(user_id)
                if raw:
                    user_config = {
                        "claude_model": raw.get("claude_model", ""),
                        "claude_base_url": raw.get("claude_base_url", ""),
                        "api_key_set": bool(raw.get("claude_api_key")),
                        "pbi_workspace_id": raw.get("pbi_workspace_id", ""),
                        "pbi_tenant_set": bool(raw.get("pbi_tenant_id")),
                        "pbi_client_set": bool(raw.get("pbi_client_id")),
                        "sf_account_set": bool(raw.get("sf_account")),
                        "onboarding_completed": raw.get("onboarding_completed", False),
                    }
        except Exception:
            pass  # Don't break settings page if user settings fail

    return _get_templates().TemplateResponse(
        name="settings.html",
        request=request,
        context={"config": config, "user_config": user_config, **_user_context(request)},
    )


@router.get("/admin")
async def page_admin(request: Request):
    return _get_templates().TemplateResponse(
        name="admin.html",
        request=request,
        context={**_user_context(request)},
    )
