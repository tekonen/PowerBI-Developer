"""Theme/style extraction and application.

Extracts visual styling (colors, fonts, chart types, layouts, filters) from:
- JSON style template files
- Existing PBIR dashboard folders
- Power BI theme JSON files

Applies extracted styles to new reports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


class ExtractedStyle(BaseModel):
    """Extracted visual style specification."""
    color_palette: list[str] = Field(default_factory=list)
    font_family: str = "Segoe UI"
    font_size: int = 10
    title_font_size: int = 14
    background_color: str | None = None
    border_enabled: bool = False
    theme_name: str = "default"
    visual_defaults: dict[str, dict[str, Any]] = Field(default_factory=dict)
    filter_configs: list[dict[str, Any]] = Field(default_factory=list)
    page_layout: dict[str, Any] = Field(default_factory=dict)
    custom_properties: dict[str, Any] = Field(default_factory=dict)


def extract_style_from_pbir(report_dir: Path) -> ExtractedStyle:
    """Extract style from an existing PBIR report folder."""
    style = ExtractedStyle()

    # Read report.json for theme info
    report_json = report_dir / "report.json"
    if report_json.exists():
        with open(report_json) as f:
            data = json.load(f)
        theme_coll = data.get("themeCollection", {})
        base_theme = theme_coll.get("baseTheme", {})
        style.theme_name = base_theme.get("name", "default")

    # Scan visuals for common formatting patterns
    pages_dir = report_dir / "definition" / "pages"
    if pages_dir.exists():
        colors_seen: list[str] = []
        fonts_seen: list[str] = []

        for page_dir in pages_dir.iterdir():
            if not page_dir.is_dir():
                continue

            # Extract page layout
            page_json = page_dir / "page.json"
            if page_json.exists():
                with open(page_json) as f:
                    page_data = json.load(f)
                style.page_layout = {
                    "width": page_data.get("width", 1280),
                    "height": page_data.get("height", 720),
                    "display_option": page_data.get("displayOption", "FitToPage"),
                }

            # Extract visual formatting
            visuals_dir = page_dir / "visuals"
            if not visuals_dir.exists():
                continue

            for visual_dir in visuals_dir.iterdir():
                visual_json = visual_dir / "visual.json"
                if not visual_json.exists():
                    continue
                with open(visual_json) as f:
                    visual_data = json.load(f)
                _extract_visual_formatting(visual_data, colors_seen, fonts_seen, style)

        # Deduplicate
        if colors_seen:
            style.color_palette = list(dict.fromkeys(colors_seen))
        if fonts_seen:
            style.font_family = fonts_seen[0]

    logger.info(f"Extracted style: {len(style.color_palette)} colors, theme={style.theme_name}")
    return style


def extract_style_from_json(template_path: Path) -> ExtractedStyle:
    """Extract style from a JSON template file."""
    with open(template_path) as f:
        data = json.load(f)
    return ExtractedStyle(**data)


def extract_style_from_theme(theme_path: Path) -> ExtractedStyle:
    """Extract style from a Power BI theme JSON file."""
    with open(theme_path) as f:
        data = json.load(f)

    style = ExtractedStyle()
    style.theme_name = data.get("name", "custom")

    # Extract data colors
    data_colors = data.get("dataColors", [])
    if data_colors:
        style.color_palette = data_colors

    # Extract text styles
    text_classes = data.get("textClasses", {})
    if "label" in text_classes:
        style.font_family = text_classes["label"].get("fontFace", "Segoe UI")
        style.font_size = text_classes["label"].get("fontSize", 10)

    return style


def apply_style_to_visual(visual_data: dict[str, Any], style: ExtractedStyle) -> dict[str, Any]:
    """Apply extracted style to a visual JSON definition."""
    objects = visual_data.get("visual", {}).get("objects", {})

    # Apply font
    if style.font_family != "Segoe UI":
        objects.setdefault("labels", [{}])
        if objects["labels"]:
            objects["labels"][0].setdefault("properties", {})
            objects["labels"][0]["properties"]["fontFamily"] = {
                "expr": {"Literal": {"Value": f"'{style.font_family}'"}}
            }

    # Apply background
    if style.background_color:
        objects["background"] = [{"properties": {
            "color": {"solid": {"color": style.background_color}},
        }}]

    if "visual" in visual_data:
        visual_data["visual"]["objects"] = objects
    return visual_data


def _extract_visual_formatting(
    visual_data: dict[str, Any],
    colors: list[str],
    fonts: list[str],
    style: ExtractedStyle,
) -> None:
    """Extract formatting details from a single visual."""
    visual = visual_data.get("visual", {})
    objects = visual.get("objects", {})

    # Extract colors from various properties
    for key in ("dataPoint", "fill", "background"):
        items = objects.get(key, [])
        for item in items:
            props = item.get("properties", {})
            for prop_val in props.values():
                if isinstance(prop_val, dict):
                    solid = prop_val.get("solid", {})
                    color = solid.get("color")
                    if color and isinstance(color, str):
                        colors.append(color)

    # Extract fonts
    for key in ("labels", "categoryAxis", "valueAxis"):
        items = objects.get(key, [])
        for item in items:
            props = item.get("properties", {})
            font = props.get("fontFamily")
            if font and isinstance(font, dict):
                literal = font.get("expr", {}).get("Literal", {}).get("Value", "")
                if literal:
                    fonts.append(literal.strip("'"))

    # Extract filters
    filters = visual_data.get("filters", [])
    if filters:
        style.filter_configs.extend(filters)

    # Record visual type defaults
    visual_type = visual.get("visualType", "")
    if visual_type and objects:
        style.visual_defaults[visual_type] = objects
