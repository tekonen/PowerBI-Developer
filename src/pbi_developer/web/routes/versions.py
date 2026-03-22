"""Version control routes for undo/redo and remote push."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


def _get_version_mgr():
    from pbi_developer.web.app import version_mgr

    return version_mgr


def _get_templates():
    from pbi_developer.web.app import templates

    return templates


@router.get("/versions")
async def page_versions(request: Request):
    mgr = _get_version_mgr()
    versions = mgr.list_versions()
    return _get_templates().TemplateResponse(
        name="versions.html",
        request=request,
        context={
            "versions": versions,
            "can_redo": mgr.can_redo,
            "remote_url": mgr.get_remote(),
        },
    )


@router.get("/api/versions")
async def api_list_versions():
    versions = _get_version_mgr().list_versions()
    return [
        {
            "commit_hash": v.commit_hash,
            "short_hash": v.short_hash,
            "message": v.message,
            "timestamp": v.timestamp,
            "run_id": v.run_id,
        }
        for v in versions
    ]


@router.post("/api/versions/undo")
async def api_undo_version():
    result = _get_version_mgr().undo()
    if result:
        return {"success": True, "version": {"message": result.message, "hash": result.short_hash}}
    return JSONResponse({"success": False, "error": "Nothing to undo"}, status_code=400)


@router.post("/api/versions/redo")
async def api_redo_version():
    result = _get_version_mgr().redo()
    if result:
        return {"success": True, "version": {"message": result.message, "hash": result.short_hash}}
    return JSONResponse({"success": False, "error": "Nothing to redo"}, status_code=400)


@router.post("/api/versions/{commit_hash}")
async def api_checkout_version(commit_hash: str):
    result = _get_version_mgr().checkout_version(commit_hash)
    if result:
        return {"success": True, "version": {"message": result.message, "hash": result.short_hash}}
    return JSONResponse({"success": False, "error": "Failed to checkout"}, status_code=400)


@router.post("/api/versions/push")
async def api_push_to_remote():
    success, message = _get_version_mgr().push_to_remote()
    if success:
        return {"success": True, "message": message}
    return JSONResponse({"success": False, "error": message}, status_code=400)


@router.post("/api/versions/remote")
async def api_set_remote(request: Request):
    body = await request.json()
    url = body.get("url", "")
    if not url:
        return JSONResponse({"success": False, "error": "URL is required"}, status_code=400)
    _get_version_mgr().set_remote(url)
    return {"success": True}


@router.get("/api/versions/diff")
async def api_get_diff(from_hash: str, to_hash: str):
    diff = _get_version_mgr().get_diff(from_hash, to_hash)
    return {"diff": diff}
