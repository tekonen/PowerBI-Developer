"""Style extractor agent.

Uses Claude vision to analyze existing dashboard screenshots or PBIR exports
and extract visual styling: colors, fonts, chart types, layouts, filter patterns.

This agent supplements the programmatic extraction in pbir/theme.py with
AI-powered analysis of visual design patterns.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pbi_developer.agents.base import BaseAgent
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)

STYLE_EXTRACTOR_SYSTEM_PROMPT = """\
You are a Power BI visual design analyst. Your job is to analyze existing
dashboard screenshots or descriptions and extract the visual style elements.

Extract:
1. Color palette (primary, secondary, accent colors as hex codes)
2. Font families and sizes
3. Chart types used and their formatting patterns
4. Page layout structure (grid patterns, margins, visual arrangement)
5. Filter/slicer configurations visible
6. Background colors and visual borders
7. Title styling patterns
8. Any branding elements

Be precise with hex color codes. Describe layout patterns in terms of
grid positions and pixel dimensions on a 1280x720 canvas.
"""

STYLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "color_palette": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Hex color codes extracted from the design",
        },
        "font_family": {"type": "string"},
        "font_size": {"type": "integer"},
        "title_font_size": {"type": "integer"},
        "background_color": {"type": "string"},
        "border_enabled": {"type": "boolean"},
        "theme_name": {"type": "string"},
        "layout_pattern": {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "grid_columns": {"type": "integer"},
                "header_height": {"type": "integer"},
                "margin": {"type": "integer"},
                "slicer_position": {"type": "string"},
            },
        },
        "visual_types_used": {
            "type": "array",
            "items": {"type": "string"},
        },
        "filter_patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "position": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
    },
    "required": ["color_palette", "font_family", "visual_types_used"],
}


class StyleExtractorAgent(BaseAgent):
    """Extracts visual style from dashboard images or descriptions."""

    system_prompt = STYLE_EXTRACTOR_SYSTEM_PROMPT
    agent_name = "style_extractor"

    def extract_from_images(self, images: list[Path | bytes]) -> dict[str, Any]:
        """Extract style from dashboard screenshot images.

        Args:
            images: List of dashboard screenshot images.

        Returns:
            Style specification matching STYLE_SCHEMA.
        """
        prompt = (
            "Analyze these dashboard screenshots and extract the complete visual style. "
            "Pay special attention to:\n"
            "- Exact hex color codes used for chart data series, backgrounds, text\n"
            "- Font families and sizes\n"
            "- Layout patterns (where KPIs, charts, slicers are positioned)\n"
            "- Filter/slicer types and positions\n"
        )
        logger.info(f"Extracting style from {len(images)} image(s)")
        result = self.call_structured(prompt, output_schema=STYLE_SCHEMA, images=images)
        logger.info(f"Style extracted: {len(result.get('color_palette', []))} colors")
        return result

    def extract_from_description(self, description: str) -> dict[str, Any]:
        """Extract style from a text description of a dashboard.

        Args:
            description: Text describing the visual style to adopt.

        Returns:
            Style specification matching STYLE_SCHEMA.
        """
        prompt = (
            "Based on this dashboard description, extract a complete visual style specification:\n\n"
            f"{description}"
        )
        logger.info("Extracting style from description")
        return self.call_structured(prompt, output_schema=STYLE_SCHEMA)
