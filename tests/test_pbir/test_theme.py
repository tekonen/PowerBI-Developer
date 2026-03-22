"""Tests for src/pbi_developer/pbir/theme.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pbi_developer.pbir.theme import (
    ExtractedStyle,
    apply_style_to_visual,
    extract_style_from_json,
    extract_style_from_pbir,
    extract_style_from_theme,
)

# ---------------------------------------------------------------------------
# ExtractedStyle model
# ---------------------------------------------------------------------------


class TestExtractedStyle:
    def test_defaults(self) -> None:
        s = ExtractedStyle()
        assert s.color_palette == []
        assert s.font_family == "Segoe UI"
        assert s.font_size == 10
        assert s.title_font_size == 14
        assert s.background_color is None
        assert s.border_enabled is False
        assert s.theme_name == "default"

    def test_custom_values(self) -> None:
        s = ExtractedStyle(
            color_palette=["#FF0000"],
            font_family="Arial",
            font_size=12,
            theme_name="custom",
        )
        assert s.color_palette == ["#FF0000"]
        assert s.font_family == "Arial"


# ---------------------------------------------------------------------------
# extract_style_from_json
# ---------------------------------------------------------------------------


class TestExtractStyleFromJson:
    def test_loads_template(self, tmp_path: Path) -> None:
        data = {
            "color_palette": ["#111111", "#222222"],
            "font_family": "Calibri",
            "font_size": 11,
            "theme_name": "corporate",
        }
        f = tmp_path / "style.json"
        f.write_text(json.dumps(data))

        style = extract_style_from_json(f)
        assert style.color_palette == ["#111111", "#222222"]
        assert style.font_family == "Calibri"
        assert style.font_size == 11
        assert style.theme_name == "corporate"

    def test_minimal_template(self, tmp_path: Path) -> None:
        f = tmp_path / "min.json"
        f.write_text(json.dumps({}))
        style = extract_style_from_json(f)
        # Should use defaults
        assert style.font_family == "Segoe UI"
        assert style.theme_name == "default"

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("not json {{{")
        with pytest.raises(json.JSONDecodeError):
            extract_style_from_json(f)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            extract_style_from_json(tmp_path / "missing.json")


# ---------------------------------------------------------------------------
# extract_style_from_theme
# ---------------------------------------------------------------------------


class TestExtractStyleFromTheme:
    def test_extracts_data_colors(self, tmp_path: Path) -> None:
        theme = {
            "name": "MyTheme",
            "dataColors": ["#AA0000", "#00BB00", "#0000CC"],
        }
        f = tmp_path / "theme.json"
        f.write_text(json.dumps(theme))

        style = extract_style_from_theme(f)
        assert style.theme_name == "MyTheme"
        assert style.color_palette == ["#AA0000", "#00BB00", "#0000CC"]

    def test_extracts_text_classes(self, tmp_path: Path) -> None:
        theme = {
            "name": "FontTheme",
            "textClasses": {
                "label": {
                    "fontFace": "Verdana",
                    "fontSize": 14,
                }
            },
        }
        f = tmp_path / "theme.json"
        f.write_text(json.dumps(theme))

        style = extract_style_from_theme(f)
        assert style.font_family == "Verdana"
        assert style.font_size == 14

    def test_empty_theme(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.json"
        f.write_text(json.dumps({}))
        style = extract_style_from_theme(f)
        assert style.theme_name == "custom"
        assert style.color_palette == []
        assert style.font_family == "Segoe UI"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            extract_style_from_theme(tmp_path / "nope.json")


# ---------------------------------------------------------------------------
# extract_style_from_pbir
# ---------------------------------------------------------------------------


class TestExtractStyleFromPbir:
    @pytest.fixture()
    def pbir_dir(self, tmp_path: Path) -> Path:
        """Create a minimal PBIR folder structure."""
        report_dir = tmp_path / "MyReport.Report"
        report_dir.mkdir()

        # report.json with theme info
        (report_dir / "report.json").write_text(
            json.dumps({"themeCollection": {"baseTheme": {"name": "CorporateTheme"}}})
        )

        # Page with a visual
        page_dir = report_dir / "definition" / "pages" / "page1"
        page_dir.mkdir(parents=True)
        (page_dir / "page.json").write_text(
            json.dumps({"name": "Page1", "displayName": "Overview", "width": 1920, "height": 1080})
        )

        visual_dir = page_dir / "visuals" / "v1"
        visual_dir.mkdir(parents=True)
        (visual_dir / "visual.json").write_text(
            json.dumps(
                {
                    "visual": {
                        "visualType": "barChart",
                        "objects": {
                            "dataPoint": [{"properties": {"fill": {"solid": {"color": "#3366CC"}}}}],
                            "labels": [{"properties": {"fontFamily": {"expr": {"Literal": {"Value": "'Roboto'"}}}}}],
                        },
                    },
                    "filters": [{"type": "basic", "column": "Region"}],
                }
            )
        )
        return report_dir

    def test_extracts_theme_name(self, pbir_dir: Path) -> None:
        style = extract_style_from_pbir(pbir_dir)
        assert style.theme_name == "CorporateTheme"

    def test_extracts_colors(self, pbir_dir: Path) -> None:
        style = extract_style_from_pbir(pbir_dir)
        assert "#3366CC" in style.color_palette

    def test_extracts_fonts(self, pbir_dir: Path) -> None:
        style = extract_style_from_pbir(pbir_dir)
        assert style.font_family == "Roboto"

    def test_extracts_page_layout(self, pbir_dir: Path) -> None:
        style = extract_style_from_pbir(pbir_dir)
        assert style.page_layout["width"] == 1920
        assert style.page_layout["height"] == 1080

    def test_extracts_filters(self, pbir_dir: Path) -> None:
        style = extract_style_from_pbir(pbir_dir)
        assert len(style.filter_configs) == 1
        assert style.filter_configs[0]["type"] == "basic"

    def test_extracts_visual_defaults(self, pbir_dir: Path) -> None:
        style = extract_style_from_pbir(pbir_dir)
        assert "barChart" in style.visual_defaults

    def test_missing_report_json(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "Empty.Report"
        report_dir.mkdir()
        style = extract_style_from_pbir(report_dir)
        assert style.theme_name == "default"

    def test_no_pages_dir(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "NoPagesReport.Report"
        report_dir.mkdir()
        (report_dir / "report.json").write_text(json.dumps({}))
        style = extract_style_from_pbir(report_dir)
        assert style.color_palette == []


# ---------------------------------------------------------------------------
# apply_style_to_visual
# ---------------------------------------------------------------------------


class TestApplyStyleToVisual:
    def test_applies_custom_font(self) -> None:
        visual_data: dict[str, Any] = {"visual": {"objects": {}}}
        style = ExtractedStyle(font_family="Roboto")
        result = apply_style_to_visual(visual_data, style)
        labels = result["visual"]["objects"]["labels"]
        assert labels[0]["properties"]["fontFamily"]["expr"]["Literal"]["Value"] == "'Roboto'"

    def test_skips_default_font(self) -> None:
        visual_data: dict[str, Any] = {"visual": {"objects": {}}}
        style = ExtractedStyle(font_family="Segoe UI")
        result = apply_style_to_visual(visual_data, style)
        assert "labels" not in result["visual"]["objects"]

    def test_applies_background_color(self) -> None:
        visual_data: dict[str, Any] = {"visual": {"objects": {}}}
        style = ExtractedStyle(background_color="#FAFAFA")
        result = apply_style_to_visual(visual_data, style)
        bg = result["visual"]["objects"]["background"]
        assert bg[0]["properties"]["color"]["solid"]["color"] == "#FAFAFA"

    def test_no_background_when_none(self) -> None:
        visual_data: dict[str, Any] = {"visual": {"objects": {}}}
        style = ExtractedStyle()
        result = apply_style_to_visual(visual_data, style)
        assert "background" not in result["visual"]["objects"]

    def test_preserves_existing_objects(self) -> None:
        visual_data: dict[str, Any] = {
            "visual": {"objects": {"existing": "data"}},
            "extra_key": 42,
        }
        style = ExtractedStyle(font_family="Arial")
        result = apply_style_to_visual(visual_data, style)
        assert result["visual"]["objects"]["existing"] == "data"
        assert result["extra_key"] == 42
