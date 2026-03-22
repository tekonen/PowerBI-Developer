"""SVG diagram parser.

Parses SVG files to extract text labels and rasterize to PNG for Claude vision.
Handles business information models and physical table relationship diagrams.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from pbi_developer.exceptions import PBIDevError
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)

SVG_NS = "{http://www.w3.org/2000/svg}"


@dataclass
class SvgTextElement:
    """A text label extracted from an SVG file."""

    text: str
    x: float = 0.0
    y: float = 0.0


@dataclass
class SvgParseResult:
    """Result of parsing an SVG file."""

    raster_png: bytes = b""
    text_elements: list[SvgTextElement] = field(default_factory=list)
    raw_text_labels: list[str] = field(default_factory=list)


def parse_svg(path: Path) -> SvgParseResult:
    """Parse an SVG file: rasterize to PNG and extract text labels.

    Args:
        path: Path to the SVG file.

    Returns:
        SvgParseResult with rasterized PNG and extracted text.

    Raises:
        PBIDevError: If the SVG cannot be parsed at all.
    """
    if not path.exists():
        raise PBIDevError(f"SVG file not found: {path}")

    svg_bytes = path.read_bytes()

    # Rasterize to PNG (graceful degradation if cairosvg fails)
    raster_png = _rasterize_svg(svg_bytes)

    # Extract text elements from SVG XML
    text_elements = _extract_text_elements(svg_bytes)
    raw_labels = list(dict.fromkeys(el.text for el in text_elements if el.text.strip()))

    if not raster_png and not text_elements:
        raise PBIDevError(f"Cannot parse SVG file: no rasterization and no text elements found in {path}")

    logger.info(f"Parsed SVG: {len(text_elements)} text elements, raster={'yes' if raster_png else 'no'}")
    return SvgParseResult(
        raster_png=raster_png,
        text_elements=text_elements,
        raw_text_labels=raw_labels,
    )


def _rasterize_svg(svg_bytes: bytes, max_dimension: int = 2048) -> bytes:
    """Rasterize SVG to PNG bytes using cairosvg.

    Returns empty bytes if rasterization fails (degraded mode).
    """
    try:
        import cairosvg

        png_bytes = cairosvg.svg2png(bytestring=svg_bytes, output_width=max_dimension)
        if not png_bytes:
            return b""

        from pbi_developer.inputs.image import resize_if_needed

        return resize_if_needed(png_bytes, max_dimension)
    except Exception as e:
        logger.warning(f"SVG rasterization failed, proceeding with text-only: {e}")
        return b""


def _extract_text_elements(svg_bytes: bytes) -> list[SvgTextElement]:
    """Extract text labels from SVG XML elements.

    Parses <text>, <tspan>, <title>, and <desc> elements.
    """
    try:
        root = ET.fromstring(svg_bytes)
    except ET.ParseError as e:
        raise PBIDevError(f"Invalid SVG: not valid XML — {e}") from e

    elements: list[SvgTextElement] = []

    # Extract <text> and <tspan> elements (with and without namespace)
    for tag in [f"{SVG_NS}text", "text"]:
        for text_el in root.iter(tag):
            _collect_text_from_element(text_el, elements)

    # Extract <title> and <desc> elements (metadata from diagramming tools)
    for tag in [f"{SVG_NS}title", "title", f"{SVG_NS}desc", "desc"]:
        for el in root.iter(tag):
            text = (el.text or "").strip()
            if text:
                elements.append(SvgTextElement(text=text))

    return elements


def _collect_text_from_element(element: ET.Element, result: list[SvgTextElement]) -> None:
    """Collect text from a <text> element and its <tspan> children."""
    x = float(element.get("x", "0") or "0")
    y = float(element.get("y", "0") or "0")

    # Direct text content
    direct_text = (element.text or "").strip()
    if direct_text:
        result.append(SvgTextElement(text=direct_text, x=x, y=y))

    # <tspan> children
    for tspan_tag in [f"{SVG_NS}tspan", "tspan"]:
        for tspan in element.iter(tspan_tag):
            if tspan is element:
                continue
            tspan_text = (tspan.text or "").strip()
            if tspan_text:
                tx = float(tspan.get("x", str(x)) or str(x))
                ty = float(tspan.get("y", str(y)) or str(y))
                result.append(SvgTextElement(text=tspan_text, x=tx, y=ty))


def svg_texts_to_summary(result: SvgParseResult) -> str:
    """Produce a text summary of labels found in the SVG diagram."""
    if not result.raw_text_labels:
        return "SVG diagram provided (no text labels extracted)."

    lines = [f"SVG diagram with {len(result.raw_text_labels)} labels:"]
    for label in result.raw_text_labels:
        lines.append(f"- {label}")
    return "\n".join(lines)
