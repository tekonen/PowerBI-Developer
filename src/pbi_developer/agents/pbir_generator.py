"""PBIR generator agent — Step 6 of the pipeline.

Converts a validated, field-mapped wireframe into valid PBIR visual.json and
page.json files. Uses pre-validated templates with Claude filling parameters
to reduce hallucination risk.
"""

from __future__ import annotations

from typing import Any

from pbi_developer.pbir.models import (
    DataFieldBinding,
    PBIRDefinition,
    PBIRPage,
    PBIRReport,
    PBIRVisual,
    ReportSettings,
    VisualDataRole,
    VisualFormatting,
    VisualPosition,
)
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


def generate_pbir_report(
    field_mapped_wireframe: dict[str, Any],
    report_name: str = "Report",
    style: dict[str, Any] | None = None,
) -> PBIRReport:
    """Convert a field-mapped wireframe to a PBIRReport model.

    This is a deterministic conversion step — no LLM calls needed.
    The wireframe has already been validated by the QA agent.

    Args:
        field_mapped_wireframe: Validated wireframe with field mappings.
        report_name: Name for the report.
        style: Optional style specification to apply.

    Returns:
        PBIRReport model ready for folder building.
    """
    report_settings = ReportSettings()
    if style and "theme_name" in style:
        report_settings.theme_name = style["theme_name"]

    report = PBIRReport(
        name=report_name,
        definition=PBIRDefinition(),
        settings=report_settings,
        pages=[],
    )

    for page_spec in field_mapped_wireframe.get("pages", []):
        page = _build_page(page_spec, style)
        report.pages.append(page)

    total_visuals = sum(len(p.visuals) for p in report.pages)
    logger.info(f"Generated PBIR report: {len(report.pages)} pages, {total_visuals} visuals")
    return report


def _build_page(page_spec: dict[str, Any], style: dict[str, Any] | None) -> PBIRPage:
    """Build a PBIRPage from a page specification."""
    from pbi_developer.config import settings as app_settings

    page = PBIRPage(
        display_name=page_spec.get("page_name", "Page"),
        width=page_spec.get("width", app_settings.pbir.default_page_width),
        height=page_spec.get("height", app_settings.pbir.default_page_height),
    )

    for visual_spec in page_spec.get("visuals", []):
        visual = _build_visual(visual_spec, style)
        page.visuals.append(visual)

    return page


def _build_visual(visual_spec: dict[str, Any], style: dict[str, Any] | None) -> PBIRVisual:
    """Build a PBIRVisual from a visual specification with field mappings."""
    position = VisualPosition(
        x=visual_spec.get("x", 0),
        y=visual_spec.get("y", 0),
        width=visual_spec.get("width", 300),
        height=visual_spec.get("height", 200),
    )

    # Build data roles from field mappings
    data_roles: list[VisualDataRole] = []
    role_bindings: dict[str, list[DataFieldBinding]] = {}

    for mapping in visual_spec.get("field_mappings", []):
        if mapping.get("unmapped_reason"):
            continue
        role = mapping.get("role", "Values")
        binding = DataFieldBinding(
            table=mapping.get("table", ""),
            column=mapping.get("field") if mapping.get("field_type") == "column" else None,
            measure=mapping.get("field") if mapping.get("field_type") == "measure" else None,
        )
        role_bindings.setdefault(role, []).append(binding)

    for role_name, bindings in role_bindings.items():
        data_roles.append(VisualDataRole(role=role_name, bindings=bindings))

    # Build formatting
    formatting = VisualFormatting(
        title=visual_spec.get("title", ""),
        show_title=bool(visual_spec.get("title")),
    )

    # Apply style if provided
    if style:
        if style.get("font_family"):
            formatting.font_family = style["font_family"]
        if style.get("background_color"):
            formatting.background_color = style["background_color"]

    return PBIRVisual(
        visual_type=visual_spec.get("visual_type", "card"),
        position=position,
        data_roles=data_roles,
        formatting=formatting,
    )
