"""Tests for PBIR models."""

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


def test_visual_to_pbir_json():
    visual = PBIRVisual(
        visual_type="card",
        position=VisualPosition(x=10, y=20, width=200, height=120),
        data_roles=[
            VisualDataRole(
                role="Fields",
                bindings=[DataFieldBinding(table="Measures", measure="Total Headcount")],
            )
        ],
        formatting=VisualFormatting(title="Headcount", show_title=True),
    )
    result = visual.to_pbir_json()
    assert result["visual"]["visualType"] == "card"
    assert result["position"]["x"] == 10
    assert result["position"]["y"] == 20
    assert result["position"]["width"] == 200
    assert "$schema" in result


def test_page_to_pbir_json():
    page = PBIRPage(
        display_name="Executive Summary",
        width=1280,
        height=720,
    )
    result = page.to_pbir_json()
    assert result["displayName"] == "Executive Summary"
    assert result["width"] == 1280
    assert result["height"] == 720
    assert "$schema" in result


def test_definition_to_pbir_json():
    defn = PBIRDefinition()
    result = defn.to_pbir_json()
    assert result["version"] == "1.0"
    assert "$schema" in result


def test_report_settings_to_pbir_json():
    settings = ReportSettings(theme_name="corporate")
    result = settings.to_pbir_json()
    assert result["themeCollection"]["baseTheme"]["name"] == "corporate"
    assert "$schema" in result


def test_full_report_model():
    report = PBIRReport(
        name="HR Dashboard",
        pages=[
            PBIRPage(
                display_name="Overview",
                visuals=[
                    PBIRVisual(
                        visual_type="card",
                        position=VisualPosition(x=20, y=20, width=200, height=120),
                        data_roles=[
                            VisualDataRole(
                                role="Fields",
                                bindings=[DataFieldBinding(table="HR", measure="Headcount")],
                            )
                        ],
                    ),
                    PBIRVisual(
                        visual_type="clusteredBarChart",
                        position=VisualPosition(x=20, y=160, width=600, height=300),
                        data_roles=[
                            VisualDataRole(
                                role="Category",
                                bindings=[DataFieldBinding(table="Employee", column="Department")],
                            ),
                            VisualDataRole(
                                role="Y",
                                bindings=[DataFieldBinding(table="HR", measure="Attrition Rate")],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    assert report.name == "HR Dashboard"
    assert len(report.pages) == 1
    assert len(report.pages[0].visuals) == 2
    assert report.pages[0].visuals[0].visual_type == "card"
    assert report.pages[0].visuals[1].visual_type == "clusteredBarChart"


def test_data_field_binding_column_expression():
    binding = DataFieldBinding(table="Employee", column="Department")
    expr = binding.expression
    assert "Column" in expr
    assert expr["Column"]["Property"] == "Department"


def test_data_field_binding_measure_expression():
    binding = DataFieldBinding(table="HR", measure="Headcount")
    expr = binding.expression
    assert "Measure" in expr
    assert expr["Measure"]["Property"] == "Headcount"
