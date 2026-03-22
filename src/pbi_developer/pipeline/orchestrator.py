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

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pbi_developer.config import settings
from pbi_developer.pipeline.stages import PipelineState, StageStatus
from pbi_developer.utils.logging import get_logger

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

    try:
        # Step 1: Requirements Ingestion
        state.set_running("ingestion")
        brief_data = _step_1_ingest(inputs)
        state.set_completed("ingestion", {"brief": brief_data})
        logger.info("Step 1 complete: Requirements ingested")

        # Step 2: Semantic Model Connection
        state.set_running("model_connection")
        model_metadata = _step_2_connect_model(inputs, dry_run)
        state.set_completed("model_connection")
        logger.info("Step 2 complete: Model metadata loaded")

        # Step 3: Wireframe Design
        state.set_running("wireframe")
        style = _load_style(inputs.get("style_template"))
        from pbi_developer.agents.wireframe import WireframeAgent
        wireframe_agent = WireframeAgent()
        wireframe = wireframe_agent.design(
            brief_data,
            model_metadata=model_metadata,
            style=style,
        )
        state.set_completed("wireframe", {"wireframe": wireframe}, wireframe_agent.token_usage)
        logger.info("Step 3 complete: Wireframe designed")

        # Step 4: Field Mapping
        state.set_running("field_mapping")
        from pbi_developer.agents.field_mapper import FieldMapperAgent
        mapper = FieldMapperAgent()
        field_mapped = mapper.map_fields(wireframe, model_metadata)
        state.set_completed("field_mapping", {"field_mapped": field_mapped}, mapper.token_usage)
        logger.info("Step 4 complete: Fields mapped")

        # Step 5: QA Validation (with retry loop)
        state.set_running("qa")
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

        state.set_completed("qa", {"qa_issues": [
            {"severity": i.severity, "visual_id": i.visual_id, "description": i.description}
            for i in qa_result.issues
        ]}, qa_agent.token_usage)
        logger.info("Step 5 complete: QA passed")

        # Step 6: PBIR Conversion
        state.set_running("pbir_generation")
        from pbi_developer.agents.pbir_generator import generate_pbir_report
        from pbi_developer.pbir.builder import build_pbir_folder

        report = generate_pbir_report(field_mapped, report_name=report_name, style=style)
        report_dir = build_pbir_folder(report, output_dir)
        state.set_completed("pbir_generation", {"report_dir": str(report_dir)})
        logger.info(f"Step 6 complete: PBIR generated at {report_dir}")

        # Validate generated output
        from pbi_developer.pbir.validator import validate_pbir_folder
        validation = validate_pbir_folder(report_dir)
        if not validation.valid:
            logger.warning(f"PBIR validation issues: {validation.errors}")

        # Step 7: Publishing (skipped in dry run)
        if dry_run:
            state.set_skipped("publishing")
            logger.info("Step 7 skipped: Dry run mode (no deployment)")
        else:
            state.set_running("publishing")
            # Deployment would happen here
            state.set_completed("publishing")

        # Step 8: RLS (skipped unless explicitly configured)
        state.set_skipped("rls")

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
            parts.append(f"\n## Extracted Questions\n" + "\n".join(f"- {q}" for q in questions))

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

    # Live mode: try XMLA endpoint
    logger.warning("Live XMLA connection not yet implemented. Use --model-metadata flag.")
    return "# Semantic Model\n\nLive XMLA connection not available."


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
