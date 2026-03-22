"""Tests for the SVG diagram parser."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pbi_developer.exceptions import PBIDevError
from pbi_developer.inputs.svg_parser import (
    SvgParseResult,
    _extract_text_elements,
    parse_svg,
    svg_texts_to_summary,
)

# Minimal valid SVG with text elements
SAMPLE_SVG = b"""\
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">
  <rect x="10" y="10" width="120" height="50" fill="#ccc" />
  <text x="30" y="40" font-size="14">Customers</text>
  <rect x="200" y="10" width="120" height="50" fill="#ccc" />
  <text x="220" y="40" font-size="14">Orders</text>
  <line x1="130" y1="35" x2="200" y2="35" stroke="black" />
  <text x="150" y="30" font-size="10">1:N</text>
  <title>Customer-Order ERD</title>
</svg>
"""

SAMPLE_SVG_WITH_TSPAN = b"""\
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">
  <text x="10" y="20">
    <tspan x="10" y="20">TableName</tspan>
    <tspan x="10" y="35">Column1</tspan>
    <tspan x="10" y="50">Column2</tspan>
  </text>
</svg>
"""

EMPTY_SVG = b"""\
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <rect x="10" y="10" width="80" height="80" fill="blue" />
</svg>
"""


class TestExtractTextElements:
    def test_extracts_text_elements(self):
        elements = _extract_text_elements(SAMPLE_SVG)
        texts = [el.text for el in elements]
        assert "Customers" in texts
        assert "Orders" in texts
        assert "1:N" in texts

    def test_extracts_title_element(self):
        elements = _extract_text_elements(SAMPLE_SVG)
        texts = [el.text for el in elements]
        assert "Customer-Order ERD" in texts

    def test_extracts_tspan_elements(self):
        elements = _extract_text_elements(SAMPLE_SVG_WITH_TSPAN)
        texts = [el.text for el in elements]
        assert "TableName" in texts
        assert "Column1" in texts
        assert "Column2" in texts

    def test_empty_svg_returns_empty(self):
        elements = _extract_text_elements(EMPTY_SVG)
        assert elements == []

    def test_invalid_xml_raises(self):
        with pytest.raises(PBIDevError, match="not valid XML"):
            _extract_text_elements(b"<not valid xml><<<")

    def test_preserves_coordinates(self):
        elements = _extract_text_elements(SAMPLE_SVG)
        customers = next(el for el in elements if el.text == "Customers")
        assert customers.x == 30.0
        assert customers.y == 40.0


class TestParseSvg:
    def test_file_not_found_raises(self, tmp_path: Path):
        with pytest.raises(PBIDevError, match="not found"):
            parse_svg(tmp_path / "nonexistent.svg")

    def test_parse_returns_text_labels(self, tmp_path: Path):
        svg_path = tmp_path / "test.svg"
        svg_path.write_bytes(SAMPLE_SVG)

        with patch("pbi_developer.inputs.svg_parser._rasterize_svg", return_value=b"PNG"):
            result = parse_svg(svg_path)

        assert "Customers" in result.raw_text_labels
        assert "Orders" in result.raw_text_labels
        assert result.raster_png == b"PNG"

    def test_deduplicates_labels(self, tmp_path: Path):
        svg_with_dups = b"""\
        <svg xmlns="http://www.w3.org/2000/svg">
          <text x="10" y="20">Sales</text>
          <text x="50" y="20">Sales</text>
          <text x="90" y="20">Revenue</text>
        </svg>"""
        svg_path = tmp_path / "dups.svg"
        svg_path.write_bytes(svg_with_dups)

        with patch("pbi_developer.inputs.svg_parser._rasterize_svg", return_value=b"PNG"):
            result = parse_svg(svg_path)

        assert result.raw_text_labels.count("Sales") == 1

    def test_graceful_degradation_no_raster(self, tmp_path: Path):
        """If rasterization fails, should still succeed with text only."""
        svg_path = tmp_path / "test.svg"
        svg_path.write_bytes(SAMPLE_SVG)

        with patch("pbi_developer.inputs.svg_parser._rasterize_svg", return_value=b""):
            result = parse_svg(svg_path)

        assert result.raster_png == b""
        assert len(result.text_elements) > 0

    def test_fails_when_no_raster_and_no_text(self, tmp_path: Path):
        svg_path = tmp_path / "empty.svg"
        svg_path.write_bytes(EMPTY_SVG)

        with (
            patch("pbi_developer.inputs.svg_parser._rasterize_svg", return_value=b""),
            pytest.raises(PBIDevError, match="Cannot parse SVG"),
        ):
            parse_svg(svg_path)


class TestSvgTextsToSummary:
    def test_with_labels(self):
        result = SvgParseResult(raw_text_labels=["Customers", "Orders", "Products"])
        summary = svg_texts_to_summary(result)
        assert "3 labels" in summary
        assert "- Customers" in summary
        assert "- Orders" in summary

    def test_without_labels(self):
        result = SvgParseResult(raw_text_labels=[])
        summary = svg_texts_to_summary(result)
        assert "no text labels" in summary
