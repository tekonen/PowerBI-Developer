"""Tests for src/pbi_developer/deployment/tester.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pbi_developer.deployment.tester import (
    TestResult,
    TestSuiteResult,
    _extract_field_refs,
    _test_bpa_rules,
    _test_file_structure,
    run_tests,
)

# ---------------------------------------------------------------------------
# TestResult / TestSuiteResult dataclasses
# ---------------------------------------------------------------------------


class TestTestResult:
    def test_basic_creation(self) -> None:
        r = TestResult(name="check", passed=True, message="ok")
        assert r.name == "check"
        assert r.passed is True
        assert r.message == "ok"

    def test_default_message(self) -> None:
        r = TestResult(name="check", passed=False)
        assert r.message == ""


class TestTestSuiteResult:
    def test_all_passed_true(self) -> None:
        suite = TestSuiteResult(
            results=[
                TestResult("a", True),
                TestResult("b", True),
            ]
        )
        assert suite.all_passed is True
        assert suite.passed_count == 2
        assert suite.failed_count == 0

    def test_all_passed_false(self) -> None:
        suite = TestSuiteResult(
            results=[
                TestResult("a", True),
                TestResult("b", False, "error"),
            ]
        )
        assert suite.all_passed is False
        assert suite.passed_count == 1
        assert suite.failed_count == 1

    def test_empty_suite(self) -> None:
        suite = TestSuiteResult()
        assert suite.all_passed is True
        assert suite.passed_count == 0
        assert suite.failed_count == 0


# ---------------------------------------------------------------------------
# Fixtures: PBIR folder structures
# ---------------------------------------------------------------------------


@pytest.fixture()
def valid_pbir_dir(tmp_path: Path) -> Path:
    """Create a valid PBIR folder structure with all required files."""
    report_dir = tmp_path / "TestReport.Report"
    report_dir.mkdir()

    # definition.pbir
    (report_dir / "definition.pbir").write_text(json.dumps({"version": "4.0"}))

    # report.json
    (report_dir / "report.json").write_text(json.dumps({"themeCollection": {"baseTheme": {"name": "Default"}}}))

    # Page with visuals
    page_dir = report_dir / "definition" / "pages" / "page1"
    page_dir.mkdir(parents=True)
    (page_dir / "page.json").write_text(
        json.dumps({"name": "Page1", "displayName": "Overview", "width": 1280, "height": 720})
    )

    visual_dir = page_dir / "visuals" / "v1"
    visual_dir.mkdir(parents=True)
    (visual_dir / "visual.json").write_text(
        json.dumps(
            {
                "name": "visual_v1",
                "position": {"x": 10, "y": 10, "width": 300, "height": 200},
                "visual": {
                    "visualType": "barChart",
                    "objects": {
                        "title": [{"properties": {"text": "Revenue"}}],
                    },
                    "query": {"queryState": {"Values": {"projections": [{"queryRef": "Sales.Revenue"}]}}},
                },
            }
        )
    )

    return report_dir


@pytest.fixture()
def minimal_pbir_dir(tmp_path: Path) -> Path:
    """PBIR dir with structure but no visuals."""
    report_dir = tmp_path / "MinReport.Report"
    report_dir.mkdir()
    (report_dir / "definition.pbir").write_text(json.dumps({"version": "4.0"}))
    (report_dir / "report.json").write_text(json.dumps({}))
    page_dir = report_dir / "definition" / "pages" / "p1"
    page_dir.mkdir(parents=True)
    (page_dir / "page.json").write_text(json.dumps({"name": "p1", "displayName": "Page 1"}))
    return report_dir


# ---------------------------------------------------------------------------
# _test_file_structure
# ---------------------------------------------------------------------------


class TestFileStructure:
    def test_valid_structure_passes(self, valid_pbir_dir: Path) -> None:
        result = _test_file_structure(valid_pbir_dir)
        assert result.passed is True
        assert "All required files present" in result.message

    def test_missing_definition_pbir(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "Bad.Report"
        report_dir.mkdir()
        (report_dir / "report.json").write_text("{}")
        (report_dir / "definition" / "pages").mkdir(parents=True)

        result = _test_file_structure(report_dir)
        assert result.passed is False
        assert "definition.pbir" in result.message

    def test_missing_report_json(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "Bad.Report"
        report_dir.mkdir()
        (report_dir / "definition.pbir").write_text("{}")
        (report_dir / "definition" / "pages").mkdir(parents=True)

        result = _test_file_structure(report_dir)
        assert result.passed is False
        assert "report.json" in result.message

    def test_missing_pages_dir(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "Bad.Report"
        report_dir.mkdir()
        (report_dir / "definition.pbir").write_text("{}")
        (report_dir / "report.json").write_text("{}")

        result = _test_file_structure(report_dir)
        assert result.passed is False
        assert "pages" in result.message

    def test_all_missing(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "Empty.Report"
        report_dir.mkdir()
        result = _test_file_structure(report_dir)
        assert result.passed is False


# ---------------------------------------------------------------------------
# _test_bpa_rules
# ---------------------------------------------------------------------------


class TestBpaRules:
    def test_valid_report_has_page_and_visual_counts(self, valid_pbir_dir: Path) -> None:
        results = _test_bpa_rules(valid_pbir_dir)
        names = [r.name for r in results]
        assert "Page Count" in names
        assert "Visual Count" in names

        page_result = next(r for r in results if r.name == "Page Count")
        assert page_result.passed is True
        assert "1 page(s)" in page_result.message

        visual_result = next(r for r in results if r.name == "Visual Count")
        assert visual_result.passed is True
        assert "1 visual(s)" in visual_result.message

    def test_no_pages_dir_returns_empty(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "NoPagesReport.Report"
        report_dir.mkdir()
        results = _test_bpa_rules(report_dir)
        assert results == []

    def test_visual_without_title_warning(self, tmp_path: Path) -> None:
        """A visual with no title objects triggers a warning result."""
        report_dir = tmp_path / "NoTitle.Report"
        page_dir = report_dir / "definition" / "pages" / "p1" / "visuals" / "v1"
        page_dir.mkdir(parents=True)

        # page.json for the page
        (report_dir / "definition" / "pages" / "p1" / "page.json").write_text(
            json.dumps({"name": "p1", "displayName": "P1"})
        )

        # visual without title in objects
        (page_dir / "visual.json").write_text(json.dumps({"visual": {"visualType": "card", "objects": {}}}))

        results = _test_bpa_rules(report_dir)
        title_results = [r for r in results if r.name == "Visual Titles"]
        assert len(title_results) == 1
        assert "without titles" in title_results[0].message

    def test_minimal_report_no_visuals(self, minimal_pbir_dir: Path) -> None:
        results = _test_bpa_rules(minimal_pbir_dir)
        visual_result = next(r for r in results if r.name == "Visual Count")
        assert visual_result.passed is False
        assert "0 visual(s)" in visual_result.message


# ---------------------------------------------------------------------------
# _extract_field_refs
# ---------------------------------------------------------------------------


class TestExtractFieldRefs:
    def test_extracts_query_refs(self) -> None:
        visual_data = {
            "visual": {
                "query": {
                    "queryState": {
                        "Values": {
                            "projections": [
                                {"queryRef": "Sales.Revenue"},
                                {"queryRef": "Sales.Quantity"},
                            ]
                        },
                        "Category": {
                            "projections": [
                                {"queryRef": "Product.Name"},
                            ]
                        },
                    }
                }
            }
        }
        refs = _extract_field_refs(visual_data)
        assert "Sales.Revenue" in refs
        assert "Sales.Quantity" in refs
        assert "Product.Name" in refs

    def test_no_query_state(self) -> None:
        refs = _extract_field_refs({"visual": {}})
        assert refs == []

    def test_empty_data(self) -> None:
        refs = _extract_field_refs({})
        assert refs == []

    def test_ignores_refs_without_dot(self) -> None:
        visual_data = {
            "visual": {
                "query": {
                    "queryState": {
                        "Values": {
                            "projections": [
                                {"queryRef": "NoDotRef"},
                            ]
                        }
                    }
                }
            }
        }
        refs = _extract_field_refs(visual_data)
        assert refs == []


# ---------------------------------------------------------------------------
# run_tests (integration with mocked validator)
# ---------------------------------------------------------------------------


class TestRunTests:
    @patch("pbi_developer.deployment.tester.validate_pbir_folder")
    def test_basic_run_with_valid_report(self, mock_validate: MagicMock, valid_pbir_dir: Path) -> None:
        """run_tests should include schema validation, file structure, and BPA results."""
        from pbi_developer.pbir.validator import ValidationResult

        mock_validate.return_value = ValidationResult(valid=True, files_checked=5)

        suite = run_tests(valid_pbir_dir)

        assert mock_validate.called
        # Should have: schema validation + file structure + BPA rules
        assert len(suite.results) >= 3
        names = [r.name for r in suite.results]
        assert "PBIR Schema Validation" in names
        assert "File Structure" in names
        assert "Page Count" in names

    @patch("pbi_developer.deployment.tester.validate_pbir_folder")
    def test_schema_validation_failure(self, mock_validate: MagicMock, valid_pbir_dir: Path) -> None:
        from pbi_developer.pbir.validator import ValidationResult

        vr = ValidationResult(valid=False, files_checked=3)
        vr.errors = ["Missing required property 'name'", "Invalid JSON"]
        mock_validate.return_value = vr

        suite = run_tests(valid_pbir_dir)
        schema_result = next(r for r in suite.results if r.name == "PBIR Schema Validation")
        assert schema_result.passed is False
        assert "2 error(s)" in schema_result.message

    @patch("pbi_developer.deployment.tester.validate_pbir_folder")
    def test_field_reference_check_with_valid_metadata(
        self, mock_validate: MagicMock, valid_pbir_dir: Path, tmp_path: Path
    ) -> None:
        from pbi_developer.pbir.validator import ValidationResult

        mock_validate.return_value = ValidationResult(valid=True, files_checked=3)

        # Create metadata file that contains the referenced field "Sales.Revenue"
        metadata_path = tmp_path / "model.json"
        metadata_path.write_text('{"tables": [{"name": "Sales.Revenue", "columns": ["Revenue"]}]}')

        suite = run_tests(valid_pbir_dir, model_metadata_path=metadata_path)
        names = [r.name for r in suite.results]
        assert "Field References" in names

        field_result = next(r for r in suite.results if r.name == "Field References")
        assert field_result.passed is True

    @patch("pbi_developer.deployment.tester.validate_pbir_folder")
    def test_field_reference_check_with_missing_fields(
        self, mock_validate: MagicMock, valid_pbir_dir: Path, tmp_path: Path
    ) -> None:
        from pbi_developer.pbir.validator import ValidationResult

        mock_validate.return_value = ValidationResult(valid=True, files_checked=3)

        # Metadata that does NOT contain "Sales.Revenue"
        metadata_path = tmp_path / "model.json"
        metadata_path.write_text('{"tables": [{"name": "Orders"}]}')

        suite = run_tests(valid_pbir_dir, model_metadata_path=metadata_path)
        field_result = next(r for r in suite.results if r.name == "Field References")
        assert field_result.passed is False
        assert "not found in model" in field_result.message

    @patch("pbi_developer.deployment.tester.validate_pbir_folder")
    def test_no_field_check_without_metadata(self, mock_validate: MagicMock, valid_pbir_dir: Path) -> None:
        from pbi_developer.pbir.validator import ValidationResult

        mock_validate.return_value = ValidationResult(valid=True, files_checked=3)

        suite = run_tests(valid_pbir_dir)
        names = [r.name for r in suite.results]
        assert "Field References" not in names

    @patch("pbi_developer.deployment.tester.validate_pbir_folder")
    def test_no_dax_check_without_dataset_id(self, mock_validate: MagicMock, valid_pbir_dir: Path) -> None:
        from pbi_developer.pbir.validator import ValidationResult

        mock_validate.return_value = ValidationResult(valid=True, files_checked=3)

        suite = run_tests(valid_pbir_dir)
        names = [r.name for r in suite.results]
        assert "DAX Connectivity" not in names
        assert "DAX Testing" not in names

    @patch("pbi_developer.deployment.tester.validate_pbir_folder")
    def test_suite_reports_overall_pass(self, mock_validate: MagicMock, valid_pbir_dir: Path) -> None:
        from pbi_developer.pbir.validator import ValidationResult

        mock_validate.return_value = ValidationResult(valid=True, files_checked=5)

        suite = run_tests(valid_pbir_dir)
        # All individual tests should pass for a valid report
        for r in suite.results:
            if r.name == "PBIR Schema Validation":
                assert r.passed is True
            if r.name == "File Structure":
                assert r.passed is True
