"""Wireframe / Architect agent — Step 3 of the pipeline.

Reads the structured brief + model metadata + optional style template and
proposes a concrete wireframe: page layouts, visual types, positions, sizes,
and which analytical questions each visual answers.

Output is a simplified PBIR-like JSON spec that the field mapper and PBIR
generator consume downstream.
"""

from __future__ import annotations

from typing import Any

from pbi_developer.agents.base import BaseAgent
from pbi_developer.config import settings
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)

WIREFRAME_SYSTEM_PROMPT = """\
You are a Power BI report architect. Given a structured dashboard brief and
semantic model metadata, you design precise report wireframes.

Your wireframe output must include:
1. Exact page definitions with dimensions
2. For each page, exact visual definitions with:
   - A unique visual_id (format: p{{page_num}}_v{{visual_num}}, e.g. "p1_v1", "p1_v2")
   - Visual type (using Power BI native type names)
   - Position (x, y) and size (width, height) in pixels on a {page_width}x{page_height} canvas
   - Data intent (what the visual shows, which question it answers)
   - A position that doesn't overlap with other visuals on the same page
3. For each page, a filters array describing filter relationships:
   - For every slicer visual, list which other visuals it filters
   - Include the field being filtered and a plain-language description
   - Filter types: "slicer" (user-controlled), "cross_filter" (visual interaction),
     "drill_through" (navigation between pages)
4. A cross_page_filters array for filters that span multiple pages

Layout rules:
- Canvas size: {page_width}x{page_height} pixels
- KPI cards go at the top of the page in a row
- Charts and tables go in the main body
- Slicers go along the left or top edge
- Leave at least {margin}px margin between visuals
- Max {max_visuals} visuals per page
- Use standard Power BI visual types: card, clusteredBarChart, clusteredColumnChart,
  lineChart, areaChart, tableEx, pivotTable, slicer, donutChart, treemap,
  filledMap, gauge, waterfallChart, scatterChart

Follow these house style rules if provided:
- Use preferred visual types when appropriate
- Follow naming conventions for page titles
"""

WIREFRAME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page_name": {"type": "string"},
                    "page_purpose": {"type": "string"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                    "visuals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "visual_id": {"type": "string"},
                                "visual_type": {"type": "string"},
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "data_intent": {"type": "string"},
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "width": {"type": "integer"},
                                "height": {"type": "integer"},
                            },
                            "required": ["visual_id", "visual_type", "data_intent", "x", "y", "width", "height"],
                        },
                    },
                    "filters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "slicer_visual_id": {"type": "string"},
                                "target_visual_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "filter_field": {"type": "string"},
                                "filter_type": {
                                    "type": "string",
                                    "enum": ["slicer", "cross_filter", "drill_through"],
                                },
                                "description": {"type": "string"},
                            },
                            "required": ["slicer_visual_id", "target_visual_ids", "filter_type", "description"],
                        },
                    },
                },
                "required": ["page_name", "visuals"],
            },
        },
        "cross_page_filters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_page": {"type": "string"},
                    "source_visual_id": {"type": "string"},
                    "target_page": {"type": "string"},
                    "target_visual_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "filter_type": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["source_page", "target_page", "filter_type", "description"],
            },
        },
    },
    "required": ["pages"],
}


class WireframeAgent(BaseAgent):
    """Designs report wireframes from structured briefs."""

    agent_name = "wireframe"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        standards = settings.report_standards
        page = settings.pbir
        self.system_prompt = WIREFRAME_SYSTEM_PROMPT.format(
            page_width=page.default_page_width,
            page_height=page.default_page_height,
            margin=standards.page_structure.get("margin", 20),
            max_visuals=standards.page_structure.get("max_visuals_per_page", 8),
        )

    def design(
        self,
        brief: dict[str, Any],
        *,
        model_metadata: str | None = None,
        style: dict[str, Any] | None = None,
        corrections: str | None = None,
        previous_output: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Design a wireframe from a structured brief.

        Args:
            brief: Structured brief from PlannerAgent.
            model_metadata: Semantic model metadata as text.
            style: Optional extracted style specification.
            corrections: Natural language corrections to apply to previous output.
            previous_output: Previous wireframe output to refine.

        Returns:
            Wireframe spec matching WIREFRAME_SCHEMA.
        """
        prompt_parts = [
            "Design a Power BI report wireframe based on this brief:\n\n",
            f"## Report Brief\n```json\n{_compact_json(brief)}\n```\n",
        ]

        if model_metadata:
            prompt_parts.append(f"\n## Available Semantic Model\n{model_metadata}\n")

        if style:
            prompt_parts.append(
                f"\n## Style Guide\nPreferred visuals: {style.get('preferred_visuals', [])}\n"
                f"Color palette: {style.get('color_palette', [])}\n"
                f"Page layout: {style.get('page_layout', {})}\n"
            )

        if corrections and previous_output:
            prompt_parts.append(
                f"\n## Previous Wireframe\n```json\n{_compact_json(previous_output)}\n```\n"
                f"\n## Corrections Requested\n{corrections}\n\n"
                "Revise the wireframe based on the corrections. "
                "Keep everything not mentioned in the corrections unchanged."
            )

        prompt = "".join(prompt_parts)
        logger.info("Designing wireframe...")

        result = self.call_structured(prompt, output_schema=WIREFRAME_SCHEMA)

        total_visuals = sum(len(p.get("visuals", [])) for p in result.get("pages", []))
        logger.info(f"Wireframe: {len(result.get('pages', []))} pages, {total_visuals} visuals")
        return result


def _compact_json(data: Any) -> str:
    import json

    return json.dumps(data, indent=2, ensure_ascii=False)
