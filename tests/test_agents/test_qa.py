"""Tests for QA agent — programmatic validation checks."""

from __future__ import annotations

from pbi_developer.agents.qa import REQUIRED_ROLES, QAAgent, QAResult


class TestQAResult:
    def test_new_result_passes(self):
        result = QAResult()
        assert result.passed is True
        assert result.issues == []

    def test_add_error_fails_result(self):
        result = QAResult()
        result.add_error("visual_1", "Missing field")
        assert result.passed is False
        assert len(result.issues) == 1
        assert result.issues[0].severity == "error"

    def test_add_warning_preserves_pass(self):
        result = QAResult()
        result.add_warning("visual_1", "Consider splitting page")
        assert result.passed is True
        assert len(result.issues) == 1
        assert result.issues[0].severity == "warning"

    def test_multiple_issues(self):
        result = QAResult()
        result.add_error("v1", "Missing field")
        result.add_warning("v2", "Page busy")
        result.add_error("v3", "Invalid type")
        assert result.passed is False
        assert len(result.issues) == 3


class TestQAChecks:
    def test_check_structure_empty_pages(self):
        agent = QAAgent.__new__(QAAgent)
        result = QAResult()
        agent._check_structure({"pages": []}, result)
        assert result.passed is False

    def test_check_structure_page_with_no_visuals(self):
        agent = QAAgent.__new__(QAAgent)
        result = QAResult()
        agent._check_structure({"pages": [{"page_name": "Empty", "visuals": []}]}, result)
        assert result.passed is True  # warning, not error
        assert len(result.issues) == 1
        assert result.issues[0].severity == "warning"

    def test_check_required_roles_card_with_fields(self, sample_field_mapped_wireframe):
        agent = QAAgent.__new__(QAAgent)
        result = QAResult()
        agent._check_required_roles(sample_field_mapped_wireframe, result)
        assert result.passed is True

    def test_check_required_roles_missing_role(self):
        agent = QAAgent.__new__(QAAgent)
        result = QAResult()
        wireframe = {
            "pages": [
                {
                    "page_name": "Test",
                    "visuals": [
                        {
                            "visual_type": "clusteredBarChart",
                            "title": "Bad Chart",
                            "field_mappings": [
                                {"role": "Category", "table": "T", "field": "Col", "field_type": "column"},
                                # Missing Y role
                            ],
                        }
                    ],
                }
            ]
        }
        agent._check_required_roles(wireframe, result)
        assert result.passed is False
        assert any("Y" in i.description for i in result.issues)

    def test_check_layout_visual_out_of_bounds(self):
        agent = QAAgent.__new__(QAAgent)
        result = QAResult()
        wireframe = {
            "pages": [
                {
                    "page_name": "Test",
                    "visuals": [
                        {
                            "visual_type": "card",
                            "title": "Overflow",
                            "x": 1200,
                            "y": 600,
                            "width": 200,
                            "height": 200,
                            "field_mappings": [{"role": "Fields", "table": "T", "field": "M", "field_type": "measure"}],
                        }
                    ],
                }
            ]
        }
        agent._check_layout(wireframe, result)
        assert any("bounds" in i.description for i in result.issues)

    def test_check_layout_too_many_visuals(self):
        agent = QAAgent.__new__(QAAgent)
        result = QAResult()
        wireframe = {
            "pages": [
                {
                    "page_name": "Busy Page",
                    "visuals": [
                        {
                            "visual_type": "card",
                            "title": f"Card {i}",
                            "x": 0,
                            "y": 0,
                            "width": 100,
                            "height": 100,
                            "field_mappings": [{"role": "Fields", "table": "T", "field": "M", "field_type": "measure"}],
                        }
                        for i in range(10)
                    ],
                }
            ]
        }
        agent._check_layout(wireframe, result)
        assert any("10 visuals" in i.description for i in result.issues)


class TestRequiredRoles:
    def test_card_requires_fields(self):
        assert "Fields" in REQUIRED_ROLES["card"]

    def test_bar_chart_requires_category_and_y(self):
        assert "Category" in REQUIRED_ROLES["clusteredBarChart"]
        assert "Y" in REQUIRED_ROLES["clusteredBarChart"]

    def test_slicer_requires_values(self):
        assert "Values" in REQUIRED_ROLES["slicer"]
