"""HTML page routes for the web GUI."""

from __future__ import annotations

from fastapi import APIRouter, Request

from pbi_developer.pipeline.stages import STAGE_LABELS
from pbi_developer.web.run_store import RunStore

router = APIRouter()


def _get_store() -> RunStore:
    from pbi_developer.web.app import store

    return store


def _get_templates():
    from pbi_developer.web.app import templates

    return templates


def _mask(value: str) -> str:
    if not value or len(value) <= 4:
        return "***"
    return f"***{value[-4:]}"


@router.get("/")
async def page_dashboard(request: Request):
    runs = _get_store().list_runs()
    return _get_templates().TemplateResponse(name="dashboard.html", request=request, context={"runs": runs})


@router.get("/generate")
async def page_generate(request: Request):
    return _get_templates().TemplateResponse(
        name="generate.html",
        request=request,
        context={"stages": STAGE_LABELS, "current_step": "init"},
    )


@router.get("/refine")
async def page_refine(request: Request):
    runs = [r for r in _get_store().list_runs() if r.status in ("completed", "failed")]
    return _get_templates().TemplateResponse(name="refine.html", request=request, context={"runs": runs})


@router.get("/deploy")
async def page_deploy(request: Request):
    runs = [r for r in _get_store().list_runs() if r.status == "completed"]
    return _get_templates().TemplateResponse(name="deploy.html", request=request, context={"runs": runs})


@router.get("/settings")
async def page_settings(request: Request):
    from pbi_developer.config import settings

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
    return _get_templates().TemplateResponse(name="settings.html", request=request, context={"config": config})
