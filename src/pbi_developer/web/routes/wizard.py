"""Wizard step-by-step routes for interactive report generation."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from pbi_developer.web.models import WIZARD_STEPS, MetadataFetchRequest, StepCorrectRequest

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


def _auto_commit(message: str, run_id: str, output_path: Path | str) -> None:
    from pbi_developer.web.app import _auto_commit

    _auto_commit(message, run_id, output_path)


@router.get("/datasets")
async def api_list_datasets():
    """List datasets in the configured Power BI workspace."""
    try:
        from pbi_developer.connectors.powerbi_rest import PowerBIClient

        client = PowerBIClient()
        datasets = client.list_datasets()
        return {"datasets": datasets}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/datasets/{dataset_id}/metadata")
async def api_get_dataset_metadata(dataset_id: str):
    """Fetch and return metadata preview for a Power BI dataset."""
    try:
        from pbi_developer.connectors.xmla import fetch_metadata_via_rest

        metadata = fetch_metadata_via_rest(dataset_id)
        return metadata.to_dict()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/runs/{run_id}/step/ingest")
async def api_step_ingest(request: Request, run_id: str):
    """Run ingestion step only, return structured brief."""
    store = _get_store_for_request(request)
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    upload_dir = store.get_upload_dir(run_id)
    output_dir = store.get_output_dir(run_id)

    # Collect uploaded files
    inputs: dict[str, Path] = {}
    for path in upload_dir.iterdir():
        if path.is_file():
            if path.suffix in (".md", ".txt"):
                inputs["brief"] = path
            elif path.suffix == ".pptx":
                inputs["pptx"] = path
            elif path.suffix in (".mp4", ".mov", ".avi"):
                inputs["video"] = path
            elif path.suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                inputs["image"] = path
            elif path.suffix == ".svg":
                inputs["svg"] = path
            elif path.name == "model_metadata.md":
                inputs["model_metadata"] = path
            elif path.suffix == ".json" and "style" in path.name.lower():
                inputs["style_template"] = path

    if not inputs:
        return JSONResponse({"error": "No input files found"}, status_code=400)

    try:
        from pbi_developer.pipeline.orchestrator import run_step_ingest

        brief = await asyncio.to_thread(run_step_ingest, inputs=inputs, output_dir=output_dir)
        store.update_run(run_id, wizard_step="ingestion", status="running")
        return {"brief": brief}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/runs/{run_id}/step/metadata/upload")
async def api_step_metadata_upload(
    request: Request,
    run_id: str,
    model_metadata: UploadFile = File(...),
):
    """Upload a metadata file for the semantic model step."""
    store = _get_store_for_request(request)
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    output_dir = store.get_output_dir(run_id)
    upload_dir = store.get_upload_dir(run_id)

    path = upload_dir / (model_metadata.filename or "model_metadata.md")
    content = await model_metadata.read()
    path.write_bytes(content)

    try:
        from pbi_developer.pipeline.orchestrator import run_step_metadata_from_file

        metadata_text = await asyncio.to_thread(run_step_metadata_from_file, file_path=path, output_dir=output_dir)
        store.update_run(run_id, wizard_step="metadata")
        return {"metadata": metadata_text}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/runs/{run_id}/step/metadata/fetch")
async def api_step_metadata_fetch(request: Request, run_id: str, req: MetadataFetchRequest):
    """Fetch metadata from a Power BI dataset for the semantic model step."""

    store = _get_store_for_request(request)
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    output_dir = store.get_output_dir(run_id)

    try:
        from pbi_developer.pipeline.orchestrator import run_step_metadata_from_dataset

        metadata_text = await asyncio.to_thread(
            run_step_metadata_from_dataset,
            dataset_id=req.dataset_id,
            output_dir=output_dir,
        )
        store.update_run(run_id, wizard_step="metadata")
        return {"metadata": metadata_text}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/runs/{run_id}/step/wireframe")
async def api_step_wireframe(request: Request, run_id: str):
    """Run wireframe design step, return wireframe JSON."""
    store = _get_store_for_request(request)
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    output_dir = store.get_output_dir(run_id)

    try:
        from pbi_developer.pipeline.orchestrator import run_step_wireframe

        wireframe = await asyncio.to_thread(run_step_wireframe, output_dir=output_dir)
        store.update_run(run_id, wizard_step="wireframe")
        return {"wireframe": wireframe}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/runs/{run_id}/step/field-mapping")
async def api_step_field_mapping(request: Request, run_id: str):
    """Run field mapping step, return field-mapped wireframe JSON."""
    store = _get_store_for_request(request)
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    output_dir = store.get_output_dir(run_id)

    try:
        from pbi_developer.pipeline.orchestrator import run_step_field_mapping

        field_mapped = await asyncio.to_thread(run_step_field_mapping, output_dir=output_dir)
        store.update_run(run_id, wizard_step="field_mapping")
        return {"field_mapped": field_mapped}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/runs/{run_id}/step/dax")
async def api_step_dax(request: Request, run_id: str):
    """Run DAX measure generation step, return measures JSON."""
    store = _get_store_for_request(request)
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    output_dir = store.get_output_dir(run_id)

    try:
        from pbi_developer.pipeline.orchestrator import run_step_dax

        dax_result = await asyncio.to_thread(run_step_dax, output_dir=output_dir)
        store.update_run(run_id, wizard_step="dax")
        return {"dax": dax_result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/runs/{run_id}/step/qa")
async def api_step_qa(request: Request, run_id: str):
    """Run QA validation step, return pass/fail results."""
    store = _get_store_for_request(request)
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    output_dir = store.get_output_dir(run_id)

    try:
        from pbi_developer.pipeline.orchestrator import run_step_qa

        qa_result = await asyncio.to_thread(run_step_qa, output_dir=output_dir)
        store.update_run(run_id, wizard_step="qa")
        return {"qa": qa_result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/runs/{run_id}/step/pbir")
async def api_step_pbir(request: Request, run_id: str):
    """Run PBIR generation step."""
    store = _get_store_for_request(request)
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    output_dir = store.get_output_dir(run_id)

    try:
        from pbi_developer.pipeline.orchestrator import run_step_pbir

        report_dir = await asyncio.to_thread(run_step_pbir, output_dir=output_dir, report_name=run.report_name)
        store.update_run(run_id, wizard_step="pbir", output_path=report_dir)
        return {"report_dir": report_dir}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/runs/{run_id}/step/rls")
async def api_step_rls(request: Request, run_id: str):
    """Run RLS generation step, return RLS config JSON."""
    store = _get_store_for_request(request)
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    output_dir = store.get_output_dir(run_id)

    try:
        from pbi_developer.pipeline.orchestrator import run_step_rls

        rls_result = await asyncio.to_thread(run_step_rls, output_dir=output_dir)
        store.update_run(run_id, wizard_step="rls")
        return {"rls": rls_result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/runs/{run_id}/step/{stage}/correct")
async def api_step_correct(request: Request, run_id: str, stage: str, req: StepCorrectRequest):
    """Re-run a wizard step with user corrections."""
    store = _get_store_for_request(request)
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    output_dir = store.get_output_dir(run_id)

    step_runners = {
        "wireframe": "run_step_wireframe",
        "field_mapping": "run_step_field_mapping",
        "dax": "run_step_dax",
        "rls": "run_step_rls",
    }
    runner_name = step_runners.get(stage)
    if not runner_name:
        return JSONResponse(
            {"error": f"Stage '{stage}' does not support corrections"},
            status_code=400,
        )

    try:
        import pbi_developer.pipeline.orchestrator as orch

        runner = getattr(orch, runner_name)
        result = await asyncio.to_thread(runner, output_dir=output_dir, corrections=req.corrections)
        return {"result": result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/runs/{run_id}/step/{stage}/accept")
async def api_step_accept(request: Request, run_id: str, stage: str):
    """Accept a wizard step's output, git-commit, and advance to next step."""
    store = _get_store_for_request(request)
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    if stage not in WIZARD_STEPS:
        return JSONResponse({"error": f"Unknown stage '{stage}'"}, status_code=400)

    output_dir = store.get_output_dir(run_id)

    # Commit to version control: use PBIR report path if available, else artifacts
    commit_path = None
    if run.output_path:
        commit_path = Path(run.output_path)
    else:
        artifacts_dir = output_dir / "artifacts"
        if artifacts_dir.exists():
            commit_path = artifacts_dir

    if commit_path:
        _auto_commit(
            f"Accept {stage}: {run.report_name}",
            run_id,
            commit_path,
        )

    # Advance to next wizard step
    try:
        idx = WIZARD_STEPS.index(stage)
        next_step = WIZARD_STEPS[idx + 1] if idx + 1 < len(WIZARD_STEPS) else "publish"
    except ValueError:
        next_step = stage

    store.update_run(run_id, wizard_step=next_step)

    # Mark run completed if we've reached the end
    if next_step == "publish":
        store.update_run(run_id, status="completed")

    return {"success": True, "next_step": next_step}


@router.get("/runs/{run_id}/step/{stage}/data")
async def api_step_data(request: Request, run_id: str, stage: str):
    """Retrieve the current artifact data for a wizard step."""
    store = _get_store_for_request(request)
    run = store.get_run(run_id)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    output_dir = store.get_output_dir(run_id)
    artifacts = output_dir / "artifacts"

    from pbi_developer.utils.files import read_json

    artifact_map = {
        "ingestion": "brief.json",
        "wireframe": "wireframe.json",
        "field_mapping": "field_mapped.json",
        "dax": "dax_measures.json",
        "rls": "rls_config.json",
    }

    filename = artifact_map.get(stage)
    if not filename:
        if stage == "metadata":
            md_path = artifacts / "model_metadata.md"
            if md_path.exists():
                return {"data": md_path.read_text(encoding="utf-8")}
            return {"data": None}
        return JSONResponse({"error": f"No artifact for stage '{stage}'"}, status_code=400)

    path = artifacts / filename
    if not path.exists():
        return {"data": None}

    return {"data": read_json(path)}
