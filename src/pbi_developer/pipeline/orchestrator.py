"""End-to-end pipeline orchestrator.

Connects all 8 pipeline stages:
1. Requirements Ingestion
2. Semantic Model Connection
3. Wireframe Design
4. Field Mapping
5. QA Validation (with retry loop)
6. PBIR Conversion
7. Report Publishing
8. RLS Configuration

Manages state between steps, handles retries, and reports progress.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pbi_developer.config import settings
from pbi_developer.pipeline.stages import PipelineState
from pbi_developer.utils.logging import get_logger

ProgressCallback = Callable[[str, str], None] | None

REFINABLE_STAGES = {"wireframe", "field_mapping", "dax", "rls"}

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    """Final result of the pipeline execution."""

    success: bool = False
    output_path: Path | None = None
    error: str | None = None
    state: PipelineState | None = None


def run_pipeline(
    *,
    inputs: dict[str, Path],
    output_dir: Path,
    report_name: str = "Report",
    dry_run: bool = True,
    progress_callback: ProgressCallback = None,
) -> PipelineResult:
    """Run the full pipeline from inputs to PBIR output.

    Args:
        inputs: Dict of input type -> path (brief, pptx, video, image, model_metadata, style_template).
        output_dir: Where to write the PBIR output.
        report_name: Name for the generated report.
        dry_run: If True, skip live connections and deployment.

    Returns:
        PipelineResult with success status and output path.
    """
    state = PipelineState()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    def _notify(stage: str, status: str) -> None:
        if progress_callback:
            progress_callback(stage, status)

    try:
        # Step 1: Requirements Ingestion
        state.set_running("ingestion")
        _notify("ingestion", "running")
        brief_data = _step_1_ingest(inputs)
        state.set_completed("ingestion", {"brief": brief_data})
        _save_artifact(output_dir, "brief", brief_data)
        _notify("ingestion", "completed")
        logger.info("Step 1 complete: Requirements ingested")

        # Step 2: Semantic Model Connection
        state.set_running("model_connection")
        _notify("model_connection", "running")
        model_metadata = _step_2_connect_model(inputs, dry_run)
        state.set_completed("model_connection")
        _save_text_artifact(output_dir, "model_metadata", model_metadata)
        _notify("model_connection", "completed")
        logger.info("Step 2 complete: Model metadata loaded")

        # Step 3: Wireframe Design
        state.set_running("wireframe")
        _notify("wireframe", "running")
        style = _load_style(inputs.get("style_template"))
        from pbi_developer.agents.wireframe import WireframeAgent

        wireframe_agent = WireframeAgent()
        wireframe = wireframe_agent.design(
            brief_data,
            model_metadata=model_metadata,
            style=style,
        )
        state.set_completed("wireframe", {"wireframe": wireframe}, wireframe_agent.token_usage)
        _save_artifact(output_dir, "wireframe", wireframe)
        if style is not None:
            _save_artifact(output_dir, "style", style)
        _notify("wireframe", "completed")
        logger.info("Step 3 complete: Wireframe designed")

        # Step 4: Field Mapping
        state.set_running("field_mapping")
        _notify("field_mapping", "running")
        from pbi_developer.agents.field_mapper import FieldMapperAgent

        mapper = FieldMapperAgent()
        field_mapped = mapper.map_fields(wireframe, model_metadata)
        state.set_completed("field_mapping", {"field_mapped": field_mapped}, mapper.token_usage)
        _save_artifact(output_dir, "field_mapped", field_mapped)
        _notify("field_mapping", "completed")
        logger.info("Step 4 complete: Fields mapped")

        # Step 5: QA Validation (with retry loop)
        state.set_running("qa")
        _notify("qa", "running")
        from pbi_developer.agents.qa import QAAgent

        qa_agent = QAAgent()
        max_retries = settings.pipeline.max_qa_retries

        for attempt in range(max_retries + 1):
            qa_result = qa_agent.validate(field_mapped, model_metadata)
            if qa_result.passed:
                break
            if attempt < max_retries:
                logger.warning(f"QA failed (attempt {attempt + 1}/{max_retries + 1}), retrying field mapping...")
                field_mapped = mapper.map_fields(wireframe, model_metadata)
            else:
                logger.error("QA failed after max retries")
                state.set_failed("qa", qa_result.summary)
                return PipelineResult(
                    success=False,
                    error=f"QA validation failed: {qa_result.summary}",
                    state=state,
                )

        state.set_completed(
            "qa",
            {
                "qa_issues": [
                    {"severity": i.severity, "visual_id": i.visual_id, "description": i.description}
                    for i in qa_result.issues
                ]
            },
            qa_agent.token_usage,
        )
        _save_artifact(output_dir, "field_mapped", field_mapped)
        _notify("qa", "completed")
        logger.info("Step 5 complete: QA passed")

        # Step 6: PBIR Conversion
        state.set_running("pbir_generation")
        _notify("pbir_generation", "running")
        from pbi_developer.agents.pbir_generator import generate_pbir_report
        from pbi_developer.pbir.builder import build_pbir_folder

        report = generate_pbir_report(field_mapped, report_name=report_name, style=style)
        report_dir = build_pbir_folder(report, output_dir)
        state.set_completed("pbir_generation", {"report_dir": str(report_dir)})
        _notify("pbir_generation", "completed")
        logger.info(f"Step 6 complete: PBIR generated at {report_dir}")

        # Validate generated output
        from pbi_developer.pbir.validator import validate_pbir_folder

        validation = validate_pbir_folder(report_dir)
        if not validation.valid:
            logger.warning(f"PBIR validation issues: {validation.errors}")

        # Step 7: Publishing (skipped in dry run)
        if dry_run:
            state.set_skipped("publishing")
            _notify("publishing", "completed")
            logger.info("Step 7 skipped: Dry run mode (no deployment)")
        else:
            state.set_running("publishing")
            _notify("publishing", "running")
            from pbi_developer.deployment.deployer import deploy_report

            deploy_result = deploy_report(report_dir)
            if deploy_result.success:
                state.set_completed("publishing", {"report_id": deploy_result.report_id})
                logger.info(f"Step 7 complete: Report published ({deploy_result.workspace_url})")
            else:
                state.set_failed("publishing", deploy_result.error)
                logger.warning(f"Step 7: Publishing failed: {deploy_result.error}")
            _notify("publishing", "completed")

        # Step 8: RLS (run if requirements exist in brief)
        rls_requirements = brief_data.get("rls_requirements", "")
        rls_examples = brief_data.get("rls_examples", [])
        if rls_requirements and model_metadata:
            state.set_running("rls")
            _notify("rls", "running")
            from pbi_developer.agents.rls import RLSAgent

            rls_agent = RLSAgent()
            rls_result = rls_agent.generate_rls(rls_requirements, rls_examples, model_metadata)
            _save_artifact(output_dir, "rls_config", rls_result)
            state.set_completed("rls", {"rls": rls_result}, rls_agent.token_usage)
            _notify("rls", "completed")
            logger.info("Step 8 complete: RLS rules generated")
        else:
            state.set_skipped("rls")
            _notify("rls", "completed")
            logger.info("Step 8 skipped: No RLS requirements in brief")

        # Save pipeline state
        _save_state(state, output_dir)

        # Log token usage
        total = state.total_tokens
        logger.info(f"Total tokens: in={total['input_tokens']}, out={total['output_tokens']}")

        return PipelineResult(
            success=True,
            output_path=report_dir,
            state=state,
        )

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        state.set_failed(state.current_stage, str(e))
        return PipelineResult(success=False, error=str(e), state=state)


def run_wireframe_only(
    *,
    inputs: dict[str, Path],
    output_path: Path,
) -> bool:
    """Run only the wireframe generation step.

    Args:
        inputs: Dict of input type -> path.
        output_path: Where to write the wireframe JSON.

    Returns:
        True if successful.
    """
    from pbi_developer.utils.files import write_json

    brief_data = _step_1_ingest(inputs)

    from pbi_developer.agents.wireframe import WireframeAgent

    agent = WireframeAgent()
    wireframe = agent.design(brief_data)

    write_json(output_path, wireframe)
    return True


def run_from_stage(
    *,
    stage: str,
    output_dir: Path,
    corrections: str,
    report_name: str = "Report",
    dry_run: bool = True,
    progress_callback: ProgressCallback = None,
) -> PipelineResult:
    """Re-run a pipeline stage with corrections, then cascade downstream.

    Loads previously saved artifacts from output_dir/artifacts/, re-runs the
    specified stage with the user's corrective instructions, and re-runs all
    downstream stages to maintain consistency.

    Args:
        stage: Which stage to refine (wireframe, field_mapping, dax, rls).
        output_dir: Output directory from a previous pipeline run.
        corrections: Natural language description of what to change.
        report_name: Name for the generated report.
        dry_run: If True, skip live connections and deployment.
        progress_callback: Optional callback for progress updates.

    Returns:
        PipelineResult with success status and output path.
    """
    from pbi_developer.utils.files import read_json

    if stage not in REFINABLE_STAGES:
        return PipelineResult(
            success=False,
            error=f"Invalid stage '{stage}'. Must be one of: {', '.join(sorted(REFINABLE_STAGES))}",
        )

    artifacts_dir = Path(output_dir) / "artifacts"
    if not artifacts_dir.exists():
        return PipelineResult(
            success=False,
            error=f"No artifacts found in {output_dir}. Run 'generate' first.",
        )

    state = PipelineState()

    def _notify(stage_name: str, status: str) -> None:
        if progress_callback:
            progress_callback(stage_name, status)

    try:
        # Load common artifacts
        model_metadata_path = artifacts_dir / "model_metadata.md"
        model_metadata = model_metadata_path.read_text(encoding="utf-8") if model_metadata_path.exists() else ""

        style_path = artifacts_dir / "style.json"
        style = read_json(style_path) if style_path.exists() else None

        if stage == "wireframe":
            brief = read_json(artifacts_dir / "brief.json")
            previous = (
                read_json(artifacts_dir / "wireframe.json") if (artifacts_dir / "wireframe.json").exists() else None
            )

            state.set_running("wireframe")
            _notify("wireframe", "running")
            from pbi_developer.agents.wireframe import WireframeAgent

            wireframe_agent = WireframeAgent()
            wireframe = wireframe_agent.design(
                brief,
                model_metadata=model_metadata,
                style=style,
                corrections=corrections,
                previous_output=previous,
            )
            _save_artifact(output_dir, "wireframe", wireframe)
            state.set_completed("wireframe", {"wireframe": wireframe}, wireframe_agent.token_usage)
            _notify("wireframe", "completed")

            # Cascade: field_mapping -> qa -> pbir_generation
            field_mapped = _run_field_mapping(wireframe, model_metadata, output_dir, state, _notify)
            field_mapped = _run_qa(field_mapped, model_metadata, wireframe, output_dir, state, _notify)
            report_dir = _run_pbir_generation(field_mapped, report_name, style, output_dir, state, _notify)

        elif stage == "field_mapping":
            wireframe = read_json(artifacts_dir / "wireframe.json")
            previous = (
                read_json(artifacts_dir / "field_mapped.json")
                if (artifacts_dir / "field_mapped.json").exists()
                else None
            )

            field_mapped = _run_field_mapping(
                wireframe,
                model_metadata,
                output_dir,
                state,
                _notify,
                corrections=corrections,
                previous_output=previous,
            )
            field_mapped = _run_qa(field_mapped, model_metadata, wireframe, output_dir, state, _notify)
            report_dir = _run_pbir_generation(field_mapped, report_name, style, output_dir, state, _notify)

        elif stage == "dax":
            brief = read_json(artifacts_dir / "brief.json")
            previous = (
                read_json(artifacts_dir / "dax_measures.json")
                if (artifacts_dir / "dax_measures.json").exists()
                else None
            )

            state.set_running("dax")
            _notify("dax", "running")
            from pbi_developer.agents.dax_generator import DaxGeneratorAgent

            dax_agent = DaxGeneratorAgent()
            metric_definitions = brief.get("kpis", [])
            dax_result = dax_agent.generate_measures(
                metric_definitions,
                model_metadata,
                corrections=corrections,
                previous_output=previous,
            )
            _save_artifact(output_dir, "dax_measures", dax_result)
            state.set_completed("dax", {"measures": dax_result}, dax_agent.token_usage)
            _notify("dax", "completed")
            report_dir = output_dir

        elif stage == "rls":
            brief = read_json(artifacts_dir / "brief.json")
            previous = (
                read_json(artifacts_dir / "rls_config.json") if (artifacts_dir / "rls_config.json").exists() else None
            )

            state.set_running("rls")
            _notify("rls", "running")
            from pbi_developer.agents.rls import RLSAgent

            rls_agent = RLSAgent()
            rls_requirements = brief.get("rls_requirements", "")
            rls_examples = brief.get("rls_examples", [])
            rls_result = rls_agent.generate_rls(
                rls_requirements,
                rls_examples,
                model_metadata,
                corrections=corrections,
                previous_output=previous,
            )
            _save_artifact(output_dir, "rls_config", rls_result)
            state.set_completed("rls", {"rls": rls_result}, rls_agent.token_usage)
            _notify("rls", "completed")
            report_dir = output_dir

        _save_state(state, output_dir)

        total = state.total_tokens
        logger.info(f"Refinement tokens: in={total['input_tokens']}, out={total['output_tokens']}")

        return PipelineResult(
            success=True,
            output_path=Path(report_dir),
            state=state,
        )

    except Exception as e:
        logger.error(f"Refinement failed: {e}")
        state.set_failed(state.current_stage, str(e))
        return PipelineResult(success=False, error=str(e), state=state)


def _run_field_mapping(
    wireframe: dict[str, Any],
    model_metadata: str,
    output_dir: Path,
    state: PipelineState,
    _notify: Callable[[str, str], None],
    *,
    corrections: str | None = None,
    previous_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the field mapping stage."""
    state.set_running("field_mapping")
    _notify("field_mapping", "running")
    from pbi_developer.agents.field_mapper import FieldMapperAgent

    mapper = FieldMapperAgent()
    field_mapped = mapper.map_fields(
        wireframe,
        model_metadata,
        corrections=corrections,
        previous_output=previous_output,
    )
    _save_artifact(output_dir, "field_mapped", field_mapped)
    state.set_completed("field_mapping", {"field_mapped": field_mapped}, mapper.token_usage)
    _notify("field_mapping", "completed")
    return field_mapped


def _run_qa(
    field_mapped: dict[str, Any],
    model_metadata: str,
    wireframe: dict[str, Any],
    output_dir: Path,
    state: PipelineState,
    _notify: Callable[[str, str], None],
) -> dict[str, Any]:
    """Run QA validation with retry loop."""
    state.set_running("qa")
    _notify("qa", "running")
    from pbi_developer.agents.field_mapper import FieldMapperAgent
    from pbi_developer.agents.qa import QAAgent

    qa_agent = QAAgent()
    max_retries = settings.pipeline.max_qa_retries

    for attempt in range(max_retries + 1):
        qa_result = qa_agent.validate(field_mapped, model_metadata)
        if qa_result.passed:
            break
        if attempt < max_retries:
            logger.warning(f"QA failed (attempt {attempt + 1}/{max_retries + 1}), retrying field mapping...")
            mapper = FieldMapperAgent()
            field_mapped = mapper.map_fields(wireframe, model_metadata)
        else:
            logger.error("QA failed after max retries")
            state.set_failed("qa", qa_result.summary)
            raise RuntimeError(f"QA validation failed: {qa_result.summary}")

    _save_artifact(output_dir, "field_mapped", field_mapped)
    state.set_completed(
        "qa",
        {
            "qa_issues": [
                {"severity": i.severity, "visual_id": i.visual_id, "description": i.description}
                for i in qa_result.issues
            ]
        },
        qa_agent.token_usage,
    )
    _notify("qa", "completed")
    return field_mapped


def _run_pbir_generation(
    field_mapped: dict[str, Any],
    report_name: str,
    style: dict[str, Any] | None,
    output_dir: Path,
    state: PipelineState,
    _notify: Callable[[str, str], None],
) -> Path:
    """Run PBIR conversion stage."""
    state.set_running("pbir_generation")
    _notify("pbir_generation", "running")
    from pbi_developer.agents.pbir_generator import generate_pbir_report
    from pbi_developer.pbir.builder import build_pbir_folder

    report = generate_pbir_report(field_mapped, report_name=report_name, style=style)
    report_dir = build_pbir_folder(report, Path(output_dir))
    state.set_completed("pbir_generation", {"report_dir": str(report_dir)})
    _notify("pbir_generation", "completed")

    from pbi_developer.pbir.validator import validate_pbir_folder

    validation = validate_pbir_folder(report_dir)
    if not validation.valid:
        logger.warning(f"PBIR validation issues: {validation.errors}")

    return report_dir


def _step_1_ingest(inputs: dict[str, Path]) -> dict[str, Any]:
    """Step 1: Ingest and parse all input sources into a structured brief."""
    from pbi_developer.agents.planner import PlannerAgent
    from pbi_developer.inputs.brief import load_brief, parse_user_questions
    from pbi_developer.inputs.image import load_image

    parts: list[str] = []
    images: list[Path | bytes] = []

    # Load text brief
    if "brief" in inputs:
        text = load_brief(inputs["brief"])
        parts.append(text)
        questions = parse_user_questions(text)
        if questions:
            parts.append("\n## Extracted Questions\n" + "\n".join(f"- {q}" for q in questions))

    # Load PowerPoint
    if "pptx" in inputs:
        from pbi_developer.inputs.pptx_parser import parse_pptx, slides_to_text

        pptx_result = parse_pptx(inputs["pptx"])
        parts.append(f"\n## PowerPoint Mockup\n{slides_to_text(pptx_result)}")

    # Load video frames
    if "video" in inputs:
        from pbi_developer.inputs.video import extract_key_frames

        frames = extract_key_frames(inputs["video"])
        images.extend(frames)
        parts.append(f"\n## Video Recording\n{len(frames)} key frames extracted (attached as images)")

    # Load images
    if "image" in inputs:
        img_data = load_image(inputs["image"])
        images.append(img_data)
        parts.append("\n## Screenshot/Mockup\nImage attached for analysis")

    brief_text = "\n".join(parts)
    planner = PlannerAgent()
    return planner.plan(brief_text, mockup_images=images if images else None)


def _step_2_connect_model(inputs: dict[str, Path], dry_run: bool) -> str:
    """Step 2: Load or fetch semantic model metadata."""
    if "model_metadata" in inputs:
        from pbi_developer.connectors.xmla import load_metadata_from_file

        return load_metadata_from_file(inputs["model_metadata"])

    if dry_run:
        logger.warning("No model metadata provided in dry run mode. Using empty metadata.")
        return "# Semantic Model\n\nNo model metadata provided. Run with --model-metadata flag."

    # Live mode: try REST API metadata fetch
    try:
        from pbi_developer.connectors.powerbi_rest import PowerBIClient
        from pbi_developer.connectors.xmla import fetch_metadata_via_rest

        client = PowerBIClient()
        datasets = client.list_datasets()
        if datasets:
            dataset_id = datasets[0]["id"]
            logger.info(f"Fetching metadata for dataset {dataset_id} via REST API")
            metadata = fetch_metadata_via_rest(dataset_id)
            return metadata.to_markdown()
        logger.warning("No datasets found in workspace. Use --model-metadata flag.")
        return "# Semantic Model\n\nNo datasets found in workspace."
    except Exception as e:
        logger.warning(f"REST API metadata fetch failed: {e}. Use --model-metadata flag.")
        return f"# Semantic Model\n\nMetadata fetch failed: {e}"


def _load_style(style_path: Path | None) -> dict[str, Any] | None:
    """Load style template if provided."""
    if style_path is None:
        return None

    if style_path.is_dir():
        from pbi_developer.pbir.theme import extract_style_from_pbir

        return extract_style_from_pbir(style_path).model_dump()
    elif style_path.suffix == ".json":
        from pbi_developer.pbir.theme import extract_style_from_json

        return extract_style_from_json(style_path).model_dump()
    return None


def _save_artifact(output_dir: Path, name: str, data: Any) -> None:
    """Save an intermediate pipeline artifact as JSON."""
    from pbi_developer.utils.files import write_json

    write_json(output_dir / "artifacts" / f"{name}.json", data)


def _save_text_artifact(output_dir: Path, name: str, text: str) -> None:
    """Save an intermediate pipeline artifact as text."""
    path = output_dir / "artifacts" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _save_state(state: PipelineState, output_dir: Path) -> None:
    """Save pipeline state for debugging and audit."""
    from pbi_developer.utils.files import write_json

    state_data = {}
    for name, stage in state.stages.items():
        state_data[name] = {
            "status": stage.status.value,
            "error": stage.error,
            "token_usage": stage.token_usage,
        }

    write_json(output_dir / "pipeline_state.json", state_data)


# ---------- Wizard step-runner functions ----------
# Each runs a single pipeline stage, reading inputs from and writing outputs
# to the artifacts directory. Used by the web wizard for interactive step-by-step
# execution. The existing run_pipeline() is unchanged for CLI use.


def run_step_ingest(
    *,
    inputs: dict[str, Path],
    output_dir: Path,
) -> dict[str, Any]:
    """Run only the ingestion stage, returning the structured brief."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    brief_data = _step_1_ingest(inputs)
    _save_artifact(output_dir, "brief", brief_data)
    logger.info("Wizard step: ingestion complete")
    return brief_data


def run_step_metadata_from_file(
    *,
    file_path: Path,
    output_dir: Path,
) -> str:
    """Load model metadata from an uploaded file and save as artifact."""
    from pbi_developer.connectors.xmla import load_metadata_from_file

    output_dir = Path(output_dir)
    metadata_text = load_metadata_from_file(file_path)
    _save_text_artifact(output_dir, "model_metadata", metadata_text)
    logger.info("Wizard step: metadata loaded from file")
    return metadata_text


def run_step_metadata_from_dataset(
    *,
    dataset_id: str,
    output_dir: Path,
) -> str:
    """Fetch model metadata from a Power BI dataset and save as artifact."""
    from pbi_developer.connectors.xmla import fetch_metadata_via_rest

    output_dir = Path(output_dir)
    metadata = fetch_metadata_via_rest(dataset_id)
    metadata_text = metadata.to_markdown()
    _save_text_artifact(output_dir, "model_metadata", metadata_text)
    logger.info(f"Wizard step: metadata fetched for dataset {dataset_id}")
    return metadata_text


def run_step_wireframe(
    *,
    output_dir: Path,
    corrections: str | None = None,
) -> dict[str, Any]:
    """Run the wireframe design stage from saved artifacts."""
    from pbi_developer.agents.wireframe import WireframeAgent
    from pbi_developer.utils.files import read_json

    output_dir = Path(output_dir)
    artifacts = output_dir / "artifacts"

    brief = read_json(artifacts / "brief.json")
    model_metadata_path = artifacts / "model_metadata.md"
    model_metadata = model_metadata_path.read_text(encoding="utf-8") if model_metadata_path.exists() else None

    style_path = artifacts / "style.json"
    style = read_json(style_path) if style_path.exists() else None

    previous = read_json(artifacts / "wireframe.json") if (artifacts / "wireframe.json").exists() else None

    agent = WireframeAgent()
    wireframe = agent.design(
        brief,
        model_metadata=model_metadata,
        style=style,
        corrections=corrections,
        previous_output=previous if corrections else None,
    )
    _save_artifact(output_dir, "wireframe", wireframe)
    if style is not None:
        _save_artifact(output_dir, "style", style)
    logger.info("Wizard step: wireframe complete")
    return wireframe


def run_step_field_mapping(
    *,
    output_dir: Path,
    corrections: str | None = None,
) -> dict[str, Any]:
    """Run the field mapping stage from saved artifacts."""
    from pbi_developer.agents.field_mapper import FieldMapperAgent
    from pbi_developer.utils.files import read_json

    output_dir = Path(output_dir)
    artifacts = output_dir / "artifacts"

    wireframe = read_json(artifacts / "wireframe.json")
    model_metadata_path = artifacts / "model_metadata.md"
    model_metadata = model_metadata_path.read_text(encoding="utf-8") if model_metadata_path.exists() else ""

    previous = read_json(artifacts / "field_mapped.json") if (artifacts / "field_mapped.json").exists() else None

    mapper = FieldMapperAgent()
    field_mapped = mapper.map_fields(
        wireframe,
        model_metadata,
        corrections=corrections,
        previous_output=previous if corrections else None,
    )
    _save_artifact(output_dir, "field_mapped", field_mapped)
    logger.info("Wizard step: field mapping complete")
    return field_mapped


def run_step_dax(
    *,
    output_dir: Path,
    corrections: str | None = None,
) -> dict[str, Any]:
    """Run the DAX measure generation stage from saved artifacts."""
    from pbi_developer.agents.dax_generator import DaxGeneratorAgent
    from pbi_developer.utils.files import read_json

    output_dir = Path(output_dir)
    artifacts = output_dir / "artifacts"

    brief = read_json(artifacts / "brief.json")
    model_metadata_path = artifacts / "model_metadata.md"
    model_metadata = model_metadata_path.read_text(encoding="utf-8") if model_metadata_path.exists() else ""

    previous = read_json(artifacts / "dax_measures.json") if (artifacts / "dax_measures.json").exists() else None

    metric_definitions = brief.get("kpis", [])
    agent = DaxGeneratorAgent()
    dax_result = agent.generate_measures(
        metric_definitions,
        model_metadata,
        corrections=corrections,
        previous_output=previous if corrections else None,
    )
    _save_artifact(output_dir, "dax_measures", dax_result)
    logger.info("Wizard step: DAX generation complete")
    return dax_result


def run_step_qa(*, output_dir: Path) -> dict[str, Any]:
    """Run QA validation from saved artifacts."""
    from pbi_developer.agents.field_mapper import FieldMapperAgent
    from pbi_developer.agents.qa import QAAgent
    from pbi_developer.utils.files import read_json

    output_dir = Path(output_dir)
    artifacts = output_dir / "artifacts"

    field_mapped = read_json(artifacts / "field_mapped.json")
    wireframe = read_json(artifacts / "wireframe.json")
    model_metadata_path = artifacts / "model_metadata.md"
    model_metadata = model_metadata_path.read_text(encoding="utf-8") if model_metadata_path.exists() else ""

    qa_agent = QAAgent()
    max_retries = settings.pipeline.max_qa_retries

    for attempt in range(max_retries + 1):
        qa_result = qa_agent.validate(field_mapped, model_metadata)
        if qa_result.passed:
            break
        if attempt < max_retries:
            logger.warning(f"QA failed (attempt {attempt + 1}/{max_retries + 1}), retrying field mapping...")
            mapper = FieldMapperAgent()
            field_mapped = mapper.map_fields(wireframe, model_metadata)
        else:
            logger.error("QA failed after max retries")

    _save_artifact(output_dir, "field_mapped", field_mapped)
    result = {
        "passed": qa_result.passed,
        "summary": qa_result.summary,
        "issues": [
            {"severity": i.severity, "visual_id": i.visual_id, "description": i.description} for i in qa_result.issues
        ],
    }
    logger.info(f"Wizard step: QA {'passed' if qa_result.passed else 'failed'}")
    return result


def run_step_pbir(
    *,
    output_dir: Path,
    report_name: str = "Report",
) -> str:
    """Run PBIR generation from saved artifacts. Returns report directory path."""
    from pbi_developer.agents.pbir_generator import generate_pbir_report
    from pbi_developer.pbir.builder import build_pbir_folder
    from pbi_developer.utils.files import read_json

    output_dir = Path(output_dir)
    artifacts = output_dir / "artifacts"

    field_mapped = read_json(artifacts / "field_mapped.json")
    style_path = artifacts / "style.json"
    style = read_json(style_path) if style_path.exists() else None

    report = generate_pbir_report(field_mapped, report_name=report_name, style=style)
    report_dir = build_pbir_folder(report, output_dir)

    from pbi_developer.pbir.validator import validate_pbir_folder

    validation = validate_pbir_folder(report_dir)
    if not validation.valid:
        logger.warning(f"PBIR validation issues: {validation.errors}")

    logger.info(f"Wizard step: PBIR generated at {report_dir}")
    return str(report_dir)


def run_step_rls(
    *,
    output_dir: Path,
    corrections: str | None = None,
) -> dict[str, Any]:
    """Run RLS generation from saved artifacts."""
    from pbi_developer.agents.rls import RLSAgent
    from pbi_developer.utils.files import read_json

    output_dir = Path(output_dir)
    artifacts = output_dir / "artifacts"

    brief = read_json(artifacts / "brief.json")
    model_metadata_path = artifacts / "model_metadata.md"
    model_metadata = model_metadata_path.read_text(encoding="utf-8") if model_metadata_path.exists() else ""

    previous = read_json(artifacts / "rls_config.json") if (artifacts / "rls_config.json").exists() else None

    rls_requirements = brief.get("rls_requirements", "")
    rls_examples = brief.get("rls_examples", [])

    agent = RLSAgent()
    rls_result = agent.generate_rls(
        rls_requirements,
        rls_examples,
        model_metadata,
        corrections=corrections,
        previous_output=previous if corrections else None,
    )
    _save_artifact(output_dir, "rls_config", rls_result)
    logger.info("Wizard step: RLS generation complete")
    return rls_result
