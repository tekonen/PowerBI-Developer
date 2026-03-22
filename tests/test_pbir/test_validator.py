"""Tests for PBIR validator."""

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
from pbi_developer.pbir.validator import validate_pbir_folder


def test_valid_report():
    report = PBIRReport(
        name="Valid",
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
    with tempfile.TemporaryDirectory() as tmpdir:
        report_dir = build_pbir_folder(report, Path(tmpdir))
        result = validate_pbir_folder(report_dir)
        assert result.valid, f"Validation errors: {result.errors}"
        assert result.files_checked > 0


def test_missing_directory():
    result = validate_pbir_folder(Path("/nonexistent/path"))
    assert not result.valid
    assert any("does not exist" in e for e in result.errors)


def test_visual_out_of_bounds_warning():
    report = PBIRReport(
        name="OutOfBounds",
        pages=[
            PBIRPage(
                display_name="Page 1",
                width=1280,
                height=720,
                visuals=[
                    PBIRVisual(
                        visual_type="card",
                        position=VisualPosition(x=1200, y=600, width=200, height=200),
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
    with tempfile.TemporaryDirectory() as tmpdir:
        report_dir = build_pbir_folder(report, Path(tmpdir))
        result = validate_pbir_folder(report_dir)
        assert len(result.warnings) > 0
