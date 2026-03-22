"""Tests for PBIR builder."""

import json
import tempfile
from pathlib import Path

from pbi_developer.pbir.builder import build_pbir_folder
from pbi_developer.pbir.models import (
    DataFieldBinding,
    PBIRPage,
    PBIRReport,
    PBIRVisual,
    VisualDataRole,
    VisualPosition,
)


def _sample_report() -> PBIRReport:
    return PBIRReport(
        name="TestReport",
        pages=[
            PBIRPage(
                display_name="Page 1",
                visuals=[
                    PBIRVisual(
                        visual_type="card",
                        position=VisualPosition(x=20, y=20, width=200, height=120),
                        data_roles=[
                            VisualDataRole(
                                role="Fields",
                                bindings=[DataFieldBinding(table="T", measure="M")],
                            )
                        ],
                    ),
                ],
            ),
        ],
    )


def test_build_pbir_folder():
    report = _sample_report()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        report_dir = build_pbir_folder(report, output_dir)

        # Check folder exists
        assert report_dir.exists()
        assert report_dir.name == "TestReport.Report"

        # Check definition.pbir
        defn = report_dir / "definition.pbir"
        assert defn.exists()
        data = json.loads(defn.read_text())
        assert data["version"] == "1.0"

        # Check report.json
        report_json = report_dir / "report.json"
        assert report_json.exists()

        # Check pages
        pages_dir = report_dir / "definition" / "pages"
        assert pages_dir.exists()
        page_dirs = list(pages_dir.iterdir())
        assert len(page_dirs) == 1

        # Check page.json
        page_dir = page_dirs[0]
        page_json = page_dir / "page.json"
        assert page_json.exists()
        page_data = json.loads(page_json.read_text())
        assert page_data["displayName"] == "Page 1"

        # Check visuals
        visuals_dir = page_dir / "visuals"
        assert visuals_dir.exists()
        visual_dirs = list(visuals_dir.iterdir())
        assert len(visual_dirs) == 1

        visual_json = visual_dirs[0] / "visual.json"
        assert visual_json.exists()
        visual_data = json.loads(visual_json.read_text())
        assert visual_data["visual"]["visualType"] == "card"

        # Check .pbip file
        pbip = output_dir / "TestReport.pbip"
        assert pbip.exists()


def test_build_multi_page_report():
    report = PBIRReport(
        name="MultiPage",
        pages=[
            PBIRPage(display_name="Overview"),
            PBIRPage(display_name="Details"),
            PBIRPage(display_name="Trends"),
        ],
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        report_dir = build_pbir_folder(report, Path(tmpdir))
        pages_dir = report_dir / "definition" / "pages"
        assert len(list(pages_dir.iterdir())) == 3
