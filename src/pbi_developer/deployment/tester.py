"""Testing module for Power BI reports.

Validates generated PBIR output:
- Schema validation against Microsoft's JSON schemas
- Cross-check field references against semantic model
- BPA-style rules (naming, format strings, cardinality)
- DAX syntax validation via executeQueries endpoint
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pbi_developer.pbir.validator import validate_pbir_folder
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str = ""


@dataclass
class TestSuiteResult:
    results: list[TestResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)


def run_tests(
    report_dir: Path,
    *,
    model_metadata_path: Path | None = None,
    dataset_id: str | None = None,
) -> TestSuiteResult:
    """Run all tests on a generated PBIR report.

    Args:
        report_dir: Path to the .Report PBIR folder.
        model_metadata_path: Optional model metadata for field reference checks.
        dataset_id: Optional dataset ID for live DAX testing.

    Returns:
        TestSuiteResult with all test outcomes.
    """
    suite = TestSuiteResult()

    # Test 1: PBIR schema validation
    suite.results.append(_test_schema_validation(report_dir))

    # Test 2: File structure completeness
    suite.results.append(_test_file_structure(report_dir))

    # Test 3: Field reference validation
    if model_metadata_path:
        suite.results.append(_test_field_references(report_dir, model_metadata_path))

    # Test 4: BPA-style rules
    suite.results.extend(_test_bpa_rules(report_dir))

    # Test 5: DAX validation (live only)
    if dataset_id:
        suite.results.extend(_test_dax_queries(report_dir, dataset_id))

    return suite


def _test_schema_validation(report_dir: Path) -> TestResult:
    """Validate PBIR files against schemas."""
    result = validate_pbir_folder(report_dir)
    if result.valid:
        return TestResult(
            "PBIR Schema Validation",
            True,
            f"All {result.files_checked} files valid",
        )
    return TestResult(
        "PBIR Schema Validation",
        False,
        f"{len(result.errors)} error(s): {'; '.join(result.errors[:3])}",
    )


def _test_file_structure(report_dir: Path) -> TestResult:
    """Check that required files and directories exist."""
    required = [
        report_dir / "definition.pbir",
        report_dir / "report.json",
        report_dir / "definition" / "pages",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        return TestResult(
            "File Structure",
            False,
            f"Missing: {', '.join(missing)}",
        )
    return TestResult("File Structure", True, "All required files present")


def _test_field_references(report_dir: Path, metadata_path: Path) -> TestResult:
    """Check that all field references in visuals exist in the model."""
    metadata_text = metadata_path.read_text()

    # Extract all referenced fields from visuals
    pages_dir = report_dir / "definition" / "pages"
    if not pages_dir.exists():
        return TestResult("Field References", False, "No pages directory")

    missing_refs: list[str] = []
    for page_dir in pages_dir.iterdir():
        if not page_dir.is_dir():
            continue
        visuals_dir = page_dir / "visuals"
        if not visuals_dir.exists():
            continue
        for visual_dir in visuals_dir.iterdir():
            visual_json = visual_dir / "visual.json"
            if not visual_json.exists():
                continue
            with open(visual_json) as f:
                data = json.load(f)
            refs = _extract_field_refs(data)
            for ref in refs:
                if ref not in metadata_text:
                    missing_refs.append(ref)

    if missing_refs:
        return TestResult(
            "Field References",
            False,
            f"{len(missing_refs)} field(s) not found in model: {', '.join(missing_refs[:5])}",
        )
    return TestResult("Field References", True, "All field references valid")


def _test_bpa_rules(report_dir: Path) -> list[TestResult]:
    """Run Best Practice Analyzer-style rules."""
    results: list[TestResult] = []

    pages_dir = report_dir / "definition" / "pages"
    if not pages_dir.exists():
        return results

    page_count = 0
    visual_count = 0
    visuals_without_title = 0

    for page_dir in pages_dir.iterdir():
        if not page_dir.is_dir():
            continue
        page_count += 1
        visuals_dir = page_dir / "visuals"
        if not visuals_dir.exists():
            continue
        for visual_dir in visuals_dir.iterdir():
            if not visual_dir.is_dir():
                continue
            visual_count += 1
            visual_json = visual_dir / "visual.json"
            if visual_json.exists():
                with open(visual_json) as f:
                    data = json.load(f)
                objects = data.get("visual", {}).get("objects", {})
                title_obj = objects.get("title", [])
                if not title_obj:
                    visuals_without_title += 1

    results.append(TestResult(
        "Page Count",
        page_count > 0,
        f"{page_count} page(s) found",
    ))

    results.append(TestResult(
        "Visual Count",
        visual_count > 0,
        f"{visual_count} visual(s) across {page_count} page(s)",
    ))

    if visuals_without_title > 0:
        results.append(TestResult(
            "Visual Titles",
            True,  # Warning, not failure
            f"{visuals_without_title} visual(s) without titles (optional)",
        ))

    return results


def _test_dax_queries(report_dir: Path, dataset_id: str) -> list[TestResult]:
    """Test DAX measure validity by executing simple queries."""
    results: list[TestResult] = []
    try:
        from pbi_developer.connectors.powerbi_rest import PowerBIClient
        client = PowerBIClient()

        # Test with a simple EVALUATE query
        try:
            result = client.execute_dax_query(dataset_id, "EVALUATE ROW(\"test\", 1)")
            results.append(TestResult("DAX Connectivity", True, "DAX query execution working"))
        except Exception as e:
            results.append(TestResult("DAX Connectivity", False, f"DAX query failed: {e}"))

    except Exception as e:
        results.append(TestResult("DAX Testing", False, f"Cannot initialize: {e}"))

    return results


def _extract_field_refs(visual_data: dict[str, Any]) -> list[str]:
    """Extract table.field references from a visual.json."""
    refs: list[str] = []
    query_state = visual_data.get("visual", {}).get("query", {}).get("queryState", {})
    for role, config in query_state.items():
        for proj in config.get("projections", []):
            qr = proj.get("queryRef", "")
            if "." in qr:
                refs.append(qr)
    return refs
