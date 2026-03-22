"""Tests for the PBIR generator agent."""

from __future__ import annotations

from pbi_developer.agents.pbir_generator import generate_pbir_report
from pbi_developer.pbir.models import (
    PBIRPage,
    PBIRReport,
    PBIRVisual,
)

SAMPLE_WIREFRAME = {
    "pages": [
        {
            "page_name": "Overview",
            "width": 1280,
            "height": 720,
            "visuals": [
                {
                    "visual_type": "card",
                    "title": "Total Revenue",
                    "x": 10,
                    "y": 10,
                    "width": 200,
                    "height": 100,
                    "field_mappings": [
                        {
                            "role": "Values",
                            "table": "Sales",
                            "field": "Revenue",
                            "field_type": "measure",
                        }
                    ],
                },
                {
                    "visual_type": "clusteredBarChart",
                    "title": "Revenue by Region",
                    "x": 220,
                    "y": 10,
                    "width": 400,
                    "height": 300,
                    "field_mappings": [
                        {
                            "role": "Category",
                            "table": "Geography",
                            "field": "Region",
                            "field_type": "column",
                        },
                        {
                            "role": "Values",
                            "table": "Sales",
                            "field": "Revenue",
                            "field_type": "measure",
                        },
                    ],
                },
            ],
        },
        {
            "page_name": "Detail",
            "visuals": [
                {
                    "visual_type": "tableEx",
                    "title": "Sales Table",
                    "x": 0,
                    "y": 0,
                    "width": 600,
                    "height": 400,
                    "field_mappings": [
                        {
                            "role": "Values",
                            "table": "Sales",
                            "field": "OrderID",
                            "field_type": "column",
                        },
                        {
                            "role": "Values",
                            "table": "Sales",
                            "field": "Revenue",
                            "field_type": "measure",
                        },
                    ],
                }
            ],
        },
    ]
}


class TestGeneratePbirReport:
    """Test generate_pbir_report with real PBIRReport objects."""

    def test_returns_pbir_report(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME, report_name="Test Report")
        assert isinstance(report, PBIRReport)
        assert report.name == "Test Report"

    def test_page_count(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        assert len(report.pages) == 2

    def test_page_names(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        names = [p.display_name for p in report.pages]
        assert names == ["Overview", "Detail"]

    def test_page_dimensions(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        overview = report.pages[0]
        assert overview.width == 1280
        assert overview.height == 720

    def test_visual_count_per_page(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        assert len(report.pages[0].visuals) == 2
        assert len(report.pages[1].visuals) == 1

    def test_visual_types(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        types = [v.visual_type for v in report.pages[0].visuals]
        assert types == ["card", "clusteredBarChart"]

    def test_visual_position(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        card = report.pages[0].visuals[0]
        assert card.position.x == 10
        assert card.position.y == 10
        assert card.position.width == 200
        assert card.position.height == 100

    def test_visual_data_roles(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        bar_chart = report.pages[0].visuals[1]
        role_names = [r.role for r in bar_chart.data_roles]
        assert "Category" in role_names
        assert "Values" in role_names

    def test_field_bindings_measure(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        card = report.pages[0].visuals[0]
        values_role = next(r for r in card.data_roles if r.role == "Values")
        assert len(values_role.bindings) == 1
        binding = values_role.bindings[0]
        assert binding.table == "Sales"
        assert binding.measure == "Revenue"
        assert binding.column is None

    def test_field_bindings_column(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        bar_chart = report.pages[0].visuals[1]
        cat_role = next(r for r in bar_chart.data_roles if r.role == "Category")
        binding = cat_role.bindings[0]
        assert binding.table == "Geography"
        assert binding.column == "Region"
        assert binding.measure is None

    def test_visual_formatting_title(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        card = report.pages[0].visuals[0]
        assert card.formatting.title == "Total Revenue"
        assert card.formatting.show_title is True

    def test_unmapped_fields_skipped(self):
        wireframe = {
            "pages": [
                {
                    "page_name": "Test",
                    "visuals": [
                        {
                            "visual_type": "card",
                            "field_mappings": [
                                {
                                    "role": "Values",
                                    "table": "Sales",
                                    "field": "Revenue",
                                    "field_type": "measure",
                                },
                                {
                                    "role": "Category",
                                    "unmapped_reason": "No matching column",
                                },
                            ],
                        }
                    ],
                }
            ]
        }
        report = generate_pbir_report(wireframe)
        visual = report.pages[0].visuals[0]
        role_names = [r.role for r in visual.data_roles]
        assert "Category" not in role_names
        assert "Values" in role_names


class TestGeneratePbirReportStyle:
    """Test style application in generate_pbir_report."""

    def test_theme_name(self):
        style = {"theme_name": "CorporateBlue"}
        report = generate_pbir_report(SAMPLE_WIREFRAME, style=style)
        assert report.settings.theme_name == "CorporateBlue"

    def test_font_family_applied(self):
        style = {"font_family": "Arial"}
        report = generate_pbir_report(SAMPLE_WIREFRAME, style=style)
        for page in report.pages:
            for visual in page.visuals:
                assert visual.formatting.font_family == "Arial"

    def test_background_color_applied(self):
        style = {"background_color": "#F0F0F0"}
        report = generate_pbir_report(SAMPLE_WIREFRAME, style=style)
        for page in report.pages:
            for visual in page.visuals:
                assert visual.formatting.background_color == "#F0F0F0"

    def test_no_style(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        assert report.settings.theme_name == "default"
        card = report.pages[0].visuals[0]
        assert card.formatting.font_family == "Segoe UI"
        assert card.formatting.background_color is None


class TestGeneratePbirReportEdgeCases:
    """Test edge cases."""

    def test_empty_wireframe(self):
        report = generate_pbir_report({"pages": []})
        assert isinstance(report, PBIRReport)
        assert len(report.pages) == 0

    def test_no_pages_key(self):
        report = generate_pbir_report({})
        assert len(report.pages) == 0

    def test_page_with_no_visuals(self):
        wireframe = {"pages": [{"page_name": "Empty Page", "visuals": []}]}
        report = generate_pbir_report(wireframe)
        assert len(report.pages) == 1
        assert len(report.pages[0].visuals) == 0

    def test_visual_defaults(self):
        """Visuals with minimal spec should get default dimensions."""
        wireframe = {
            "pages": [
                {
                    "page_name": "Minimal",
                    "visuals": [
                        {"visual_type": "card", "field_mappings": []},
                    ],
                }
            ]
        }
        report = generate_pbir_report(wireframe)
        visual = report.pages[0].visuals[0]
        assert visual.position.x == 0
        assert visual.position.y == 0
        assert visual.position.width == 300
        assert visual.position.height == 200

    def test_default_report_name(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        assert report.name == "Report"

    def test_report_has_definition(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        assert report.definition is not None
        assert report.definition.version == "1.0"

    def test_pages_are_pbir_page_instances(self):
        report = generate_pbir_report(SAMPLE_WIREFRAME)
        for page in report.pages:
            assert isinstance(page, PBIRPage)
            for visual in page.visuals:
                assert isinstance(visual, PBIRVisual)
