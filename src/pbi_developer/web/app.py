"""FastAPI web application for the AI Power BI Developer tool."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pbi_developer.web import sse
from pbi_developer.web.models import DeployRequest, RefineRequest
from pbi_developer.web.run_store import RunStore
from pbi_developer.web.version_control import VersionManager

# Store background task references to prevent garbage collection
_background_tasks: set[asyncio.Task] = set()

_WEB_DIR = Path(__file__).parent
_TEMPLATES_DIR = _WEB_DIR / "templates"
_STATIC_DIR = _WEB_DIR / "static"

app = FastAPI(title="AI Power BI Developer")
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

store = RunStore()
_versions_dir = store.base_dir / "dashboard-versions"
version_mgr = VersionManager(_versions_dir)

STAGE_LABELS = {
    "ingestion": "Ingesting requirements",
    "model_connection": "Loading semantic model",
    "wireframe": "Designing wireframe",
    "field_mapping": "Mapping fields",
    "qa": "Validating (QA)",
    "pbir_generation": "Generating PBIR",
    "publishing": "Publishing",
    "rls": "RLS configuration",
}

ALL_STAGES = list(STAGE_LABELS.keys())


# ---------- Page routes ----------


@app.get("/")
async def page_dashboard(request: Request):
    runs = store.list_runs()
    return templates.TemplateResponse(name="dashboard.html", request=request, context={"runs": runs})


@app.get("/generate")
async def page_generate(request: Request):
    return templates.TemplateResponse(name="generate.html", request=request, context={"stages": STAGE_LABELS})


@app.get("/refine")
async def page_refine(request: Request):
    runs = [r for r in store.list_runs() if r.status in ("completed", "failed")]
    return templates.TemplateResponse(name="refine.html", request=request, context={"runs": runs})


@app.get("/deploy")
async def page_deploy(request: Request):
    runs = [r for r in store.list_runs() if r.status == "completed"]
    return templates.TemplateResponse(name="deploy.html", request=request, context={"runs": runs})


@app.get("/settings")
async def page_settings(request: Request):
    from pbi_developer.config import settings

    config = {
        "claude_model": settings.claude.model,
        "workspace_id": _mask(settings.powerbi.workspace_id),
        "tenant_id": _mask(settings.powerbi.tenant_id),
        "client_id": _mask(settings.powerbi.client_id),
        "api_key_set": bool(settings.claude.api_key),
        "max_qa_retries": settings.pipeline.max_qa_retries,
        "require_human_review": settings.pipeline.require_human_review,
    }
    return templates.TemplateResponse(name="settings.html", request=request, context={"config": config})


# ---------- API routes ----------


@app.get("/api/runs")
async def api_list_runs():
    return [r.model_dump(mode="json") for r in store.list_runs()]


@app.get("/api/runs/{run_id}")
async def api_get_run(run_id: str):
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    return run.model_dump(mode="json")


@app.post("/api/runs")
async def api_create_run(
    brief: UploadFile | None = File(None),
    pptx: UploadFile | None = File(None),
    video: UploadFile | None = File(None),
    image: UploadFile | None = File(None),
    model_metadata: UploadFile | None = File(None),
    style_template: UploadFile | None = File(None),
    report_name: str = Form("Report"),
    dry_run: bool = Form(True),
):
    """Start a new pipeline run."""
    run_id = store.create_run(report_name=report_name, dry_run=dry_run)
    upload_dir = store.get_upload_dir(run_id)

    # Save uploaded files
    inputs: dict[str, Path] = {}
    for name, upload in [
        ("brief", brief),
        ("pptx", pptx),
        ("video", video),
        ("image", image),
        ("model_metadata", model_metadata),
        ("style_template", style_template),
    ]:
        if upload and upload.filename:
            path = upload_dir / upload.filename
            content = await upload.read()
            path.write_bytes(content)
            inputs[name] = path

    if not inputs:
        store.update_run(run_id, status="failed", error="No input files provided")
        return JSONResponse({"run_id": run_id, "error": "No input files provided"}, status_code=400)

    output_dir = store.get_output_dir(run_id)
    loop = asyncio.get_event_loop()
    queue = sse.create_queue(run_id)
    callback = sse.make_progress_callback(run_id, loop)

    async def _run_pipeline_bg():
        from pbi_developer.pipeline.orchestrator import run_pipeline

        store.update_run(run_id, status="running")
        try:
            result = await asyncio.to_thread(
                run_pipeline,
                inputs=inputs,
                output_dir=output_dir,
                report_name=report_name,
                dry_run=dry_run,
                progress_callback=callback,
            )
            store.update_run(
                run_id,
                status="completed" if result.success else "failed",
                output_path=str(result.output_path) if result.output_path else None,
                tokens=result.state.total_tokens if result.state else {},
                error=result.error,
                stages={name: s.status.value for name, s in result.state.stages.items()} if result.state else {},
            )
            if result.success and result.output_path:
                _auto_commit(f"Generate: {report_name}", run_id, result.output_path)
        except Exception as e:
            store.update_run(run_id, status="failed", error=str(e))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    task = asyncio.create_task(_run_pipeline_bg())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return JSONResponse({"run_id": run_id})


@app.get("/api/runs/{run_id}/events")
async def api_run_events(run_id: str):
    """SSE stream of pipeline stage progress events."""
    queue = sse.get_queue(run_id)
    if not queue:
        return JSONResponse({"error": "No active run"}, status_code=404)

    async def event_stream():
        while True:
            event = await queue.get()
            if event is None:
                run = store.get_run(run_id)
                status = run.status if run else "unknown"
                error = run.error if run else None
                done_data = {"type": "done", "status": status, "error": error}
                yield f"data: {json.dumps(done_data)}\n\n"
                break
            yield f"data: {json.dumps({'type': 'stage', **event})}\n\n"
        sse.remove_queue(run_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/runs/{run_id}/refine")
async def api_refine_run(run_id: str, req: RefineRequest):
    """Start refinement on an existing run."""
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    output_dir = store.get_output_dir(run_id)
    loop = asyncio.get_event_loop()
    queue = sse.create_queue(run_id)
    callback = sse.make_progress_callback(run_id, loop)

    async def _refine_bg():
        from pbi_developer.pipeline.orchestrator import run_from_stage

        store.update_run(run_id, status="running")
        try:
            result = await asyncio.to_thread(
                run_from_stage,
                stage=req.stage,
                output_dir=output_dir,
                corrections=req.corrections,
                report_name=run.report_name,
                dry_run=req.dry_run,
                progress_callback=callback,
            )
            store.update_run(
                run_id,
                status="completed" if result.success else "failed",
                output_path=str(result.output_path) if result.output_path else None,
                tokens=result.state.total_tokens if result.state else {},
                error=result.error,
                stages={name: s.status.value for name, s in result.state.stages.items()} if result.state else {},
            )
            if result.success and result.output_path:
                short = req.corrections[:60] if req.corrections else ""
                _auto_commit(f"Refine {req.stage}: {short}", run_id, result.output_path)
        except Exception as e:
            store.update_run(run_id, status="failed", error=str(e))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    task = asyncio.create_task(_refine_bg())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return JSONResponse({"run_id": run_id})


@app.post("/api/deploy")
async def api_deploy(req: DeployRequest):
    """Deploy a report to Power BI Service."""
    from pbi_developer.deployment.deployer import deploy_report

    result = deploy_report(
        Path(req.report_dir),
        workspace_id=req.workspace_id,
        stage=req.stage,
        method=req.method,
    )
    return {
        "success": result.success,
        "error": result.error,
        "report_id": result.report_id,
        "workspace_url": result.workspace_url,
    }


@app.post("/api/validate")
async def api_validate(request: Request):
    """Validate a PBIR folder."""
    from pbi_developer.pbir.validator import validate_pbir_folder

    body = await request.json()
    report_dir = Path(body["report_dir"])
    result = validate_pbir_folder(report_dir)
    return {
        "valid": result.valid,
        "files_checked": result.files_checked,
        "errors": result.errors,
        "warnings": result.warnings,
    }


@app.post("/api/connect/{target}")
async def api_test_connection(target: str):
    """Test connection to Power BI, Snowflake, or XMLA."""
    from pbi_developer.connectors.auth import test_connection

    success, message = test_connection(target)
    return {"success": success, "message": message}


@app.get("/api/runs/{run_id}/output")
async def api_list_output(run_id: str):
    """List files in a run's output directory."""
    output_dir = store.get_output_dir(run_id)
    files = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and "uploads" not in path.parts:
            files.append(str(path.relative_to(output_dir)))
    return {"files": files}


@app.get("/api/runs/{run_id}/output/{file_path:path}")
async def api_download_output(run_id: str, file_path: str):
    """Download a specific output file (path-traversal protected)."""
    output_dir = store.get_output_dir(run_id)
    target = (output_dir / file_path).resolve()
    if not target.is_relative_to(output_dir.resolve()):
        return JSONResponse({"error": "Invalid path"}, status_code=403)
    if not target.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(target)


@app.get("/api/settings")
async def api_settings():
    """Return current configuration (secrets masked)."""
    from pbi_developer.config import settings

    return {
        "claude_model": settings.claude.model,
        "max_tokens": settings.claude.max_tokens,
        "temperature": settings.claude.temperature,
        "api_key_set": bool(settings.claude.api_key),
        "workspace_id": _mask(settings.powerbi.workspace_id),
        "tenant_id": _mask(settings.powerbi.tenant_id),
        "client_id": _mask(settings.powerbi.client_id),
        "page_width": settings.pbir.default_page_width,
        "page_height": settings.pbir.default_page_height,
        "max_qa_retries": settings.pipeline.max_qa_retries,
        "require_human_review": settings.pipeline.require_human_review,
    }


# ---------- Version control routes ----------


@app.get("/versions")
async def page_versions(request: Request):
    versions = version_mgr.list_versions()
    return templates.TemplateResponse(
        name="versions.html",
        request=request,
        context={
            "versions": versions,
            "can_redo": version_mgr.can_redo,
            "remote_url": version_mgr.get_remote(),
        },
    )


@app.get("/api/versions")
async def api_list_versions():
    versions = version_mgr.list_versions()
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


@app.post("/api/versions/undo")
async def api_undo_version():
    result = version_mgr.undo()
    if result:
        return {"success": True, "version": {"message": result.message, "hash": result.short_hash}}
    return JSONResponse({"success": False, "error": "Nothing to undo"}, status_code=400)


@app.post("/api/versions/redo")
async def api_redo_version():
    result = version_mgr.redo()
    if result:
        return {"success": True, "version": {"message": result.message, "hash": result.short_hash}}
    return JSONResponse({"success": False, "error": "Nothing to redo"}, status_code=400)


@app.post("/api/versions/{commit_hash}")
async def api_checkout_version(commit_hash: str):
    result = version_mgr.checkout_version(commit_hash)
    if result:
        return {"success": True, "version": {"message": result.message, "hash": result.short_hash}}
    return JSONResponse({"success": False, "error": "Failed to checkout"}, status_code=400)


@app.post("/api/versions/push")
async def api_push_to_remote():
    success, message = version_mgr.push_to_remote()
    if success:
        return {"success": True, "message": message}
    return JSONResponse({"success": False, "error": message}, status_code=400)


@app.post("/api/versions/remote")
async def api_set_remote(request: Request):
    body = await request.json()
    url = body.get("url", "")
    if not url:
        return JSONResponse({"success": False, "error": "URL is required"}, status_code=400)
    version_mgr.set_remote(url)
    return {"success": True}


@app.get("/api/versions/diff")
async def api_get_diff(from_hash: str, to_hash: str):
    diff = version_mgr.get_diff(from_hash, to_hash)
    return {"diff": diff}


# ---------- Helpers ----------


def _auto_commit(message: str, run_id: str, output_path: Path | str) -> None:
    """Copy output to version-controlled dir and commit."""
    import shutil

    output = Path(output_path) if isinstance(output_path, str) else output_path
    if not output.exists():
        return

    # Copy output into the version-controlled directory
    dest = _versions_dir / output.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(output, dest)

    version_mgr.commit_version(message, run_id)


def _mask(value: str) -> str:
    """Mask a secret, showing only the last 4 characters."""
    if not value or len(value) <= 4:
        return "***"
    return f"***{value[-4:]}"
