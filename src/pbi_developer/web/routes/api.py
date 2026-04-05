"""Core API routes: runs, deploy, validate, connect, graph, settings."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from pbi_developer.web import sse
from pbi_developer.web.models import DeployRequest, RefineRequest

router = APIRouter(prefix="/api")


def _get_store():
    from pbi_developer.web.app import store

    return store


def _get_store_for_request(request: Request):
    """Return user-scoped store when Supabase is configured, otherwise global."""
    from pbi_developer.web.auth import get_current_user_id
    from pbi_developer.web.supabase_client import is_supabase_configured

    if is_supabase_configured():
        user_id = get_current_user_id(request)
        if user_id:
            from pbi_developer.web.store_factory import get_store

            return get_store(user_id)
    return _get_store()


def _get_user_settings(request: Request):
    """Build user-specific settings if authenticated, otherwise global."""
    from pbi_developer.web.auth import get_current_user_id
    from pbi_developer.web.supabase_client import is_supabase_configured

    if is_supabase_configured():
        user_id = get_current_user_id(request)
        if user_id:
            try:
                from pbi_developer.web.user_settings_service import build_settings_for_user

                return build_settings_for_user(user_id)
            except Exception:
                pass
    from pbi_developer.config import settings

    return settings


def _get_version_mgr():
    from pbi_developer.web.app import version_mgr

    return version_mgr


def _get_versions_dir():
    from pbi_developer.web.app import _versions_dir

    return _versions_dir


def _get_background_tasks():
    from pbi_developer.web.app import _background_tasks

    return _background_tasks


def _auto_commit(message: str, run_id: str, output_path: Path | str) -> None:
    from pbi_developer.web.app import _auto_commit

    _auto_commit(message, run_id, output_path)


def _mask(value: str) -> str:
    if not value or len(value) <= 4:
        return "***"
    return f"***{value[-4:]}"


@router.get("/runs")
async def api_list_runs(request: Request):
    return [r.model_dump(mode="json") for r in _get_store_for_request(request).list_runs()]


@router.get("/runs/{run_id}")
async def api_get_run(request: Request, run_id: str):
    run = _get_store_for_request(request).get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    return run.model_dump(mode="json")


@router.post("/runs")
async def api_create_run(
    request: Request,
    brief: UploadFile | None = File(None),
    pptx: UploadFile | None = File(None),
    video: UploadFile | None = File(None),
    image: UploadFile | None = File(None),
    svg: UploadFile | None = File(None),
    model_metadata: UploadFile | None = File(None),
    style_template: UploadFile | None = File(None),
    report_name: str = Form("Report"),
    dry_run: bool = Form(True),
    wizard: bool = Form(False),
):
    """Start a new pipeline run.

    When wizard=True, files are saved but the pipeline is NOT started.
    The wizard UI drives execution step-by-step via /step/* endpoints.
    """
    store = _get_store_for_request(request)
    run_id = store.create_run(report_name=report_name, dry_run=dry_run)
    upload_dir = store.get_upload_dir(run_id)

    # Save uploaded files
    inputs: dict[str, Path] = {}
    for name, upload in [
        ("brief", brief),
        ("pptx", pptx),
        ("video", video),
        ("image", image),
        ("svg", svg),
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

    # Wizard mode: save files only, don't start the pipeline
    if wizard:
        store.update_run(run_id, wizard_step="init")
        return JSONResponse({"run_id": run_id, "wizard": True})

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

    bg_tasks = _get_background_tasks()
    task = asyncio.create_task(_run_pipeline_bg())
    bg_tasks.add(task)
    task.add_done_callback(bg_tasks.discard)
    return JSONResponse({"run_id": run_id})


@router.get("/runs/{run_id}/events")
async def api_run_events(run_id: str):
    """SSE stream of pipeline stage progress events."""
    queue = sse.get_queue(run_id)
    if not queue:
        return JSONResponse({"error": "No active run"}, status_code=404)

    async def event_stream():
        while True:
            event = await queue.get()
            if event is None:
                store = _get_store()
                run = store.get_run(run_id)
                status = run.status if run else "unknown"
                error = run.error if run else None
                done_data = {"type": "done", "status": status, "error": error}
                yield f"data: {json.dumps(done_data)}\n\n"
                break
            yield f"data: {json.dumps({'type': 'stage', **event})}\n\n"
        sse.remove_queue(run_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/runs/{run_id}/refine")
async def api_refine_run(request: Request, run_id: str, req: RefineRequest):
    """Start refinement on an existing run."""
    store = _get_store_for_request(request)
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

    bg_tasks = _get_background_tasks()
    task = asyncio.create_task(_refine_bg())
    bg_tasks.add(task)
    task.add_done_callback(bg_tasks.discard)
    return JSONResponse({"run_id": run_id})


@router.post("/deploy")
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


@router.post("/validate")
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


@router.post("/connect/{target}")
async def api_test_connection(target: str):
    """Test connection to Power BI, Snowflake, or XMLA."""
    from pbi_developer.connectors.auth import test_connection

    success, message = test_connection(target)
    return {"success": success, "message": message}


@router.get("/runs/{run_id}/output")
async def api_list_output(request: Request, run_id: str):
    """List files in a run's output directory."""
    store = _get_store_for_request(request)
    output_dir = store.get_output_dir(run_id)
    files = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and "uploads" not in path.parts:
            files.append(str(path.relative_to(output_dir)))
    return {"files": files}


@router.get("/runs/{run_id}/output/{file_path:path}")
async def api_download_output(request: Request, run_id: str, file_path: str):
    """Download a specific output file (path-traversal protected)."""
    store = _get_store_for_request(request)
    output_dir = store.get_output_dir(run_id)
    target = (output_dir / file_path).resolve()
    if not target.is_relative_to(output_dir.resolve()):
        return JSONResponse({"error": "Invalid path"}, status_code=403)
    if not target.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(target)


@router.get("/graph")
async def api_graph():
    """Return knowledge graph summary."""
    from pbi_developer.knowledge_graph import KnowledgeGraphStore

    kg = KnowledgeGraphStore()
    return {
        "node_count": kg.graph.number_of_nodes(),
        "edge_count": kg.graph.number_of_edges(),
        "tables": kg.get_tables(),
        "relationships": kg.get_relationships(),
        "brief_context": kg.to_brief_context(),
    }


@router.get("/settings")
async def api_settings(request: Request):
    """Return current configuration (secrets masked), using user overrides if authenticated."""
    cfg = _get_user_settings(request)

    return {
        "claude_model": cfg.claude.model,
        "api_base_url": cfg.claude.base_url or "(default)",
        "max_tokens": cfg.claude.max_tokens,
        "temperature": cfg.claude.temperature,
        "api_key_set": bool(cfg.claude.api_key),
        "workspace_id": _mask(cfg.powerbi.workspace_id),
        "tenant_id": _mask(cfg.powerbi.tenant_id),
        "client_id": _mask(cfg.powerbi.client_id),
        "page_width": cfg.pbir.default_page_width,
        "page_height": cfg.pbir.default_page_height,
        "max_qa_retries": cfg.pipeline.max_qa_retries,
        "require_human_review": cfg.pipeline.require_human_review,
    }
