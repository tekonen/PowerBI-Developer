"""PBIR folder structure builder.

Assembles a valid PBIR directory from Pydantic models:

    <ReportName>.Report/
        definition.pbir
        report.json
        definition/
            pages/
                <page-folder>/
                    page.json
                    visuals/
                        <visual-folder>/
                            visual.json
"""

from __future__ import annotations

from pathlib import Path

from pbi_developer.pbir.models import PBIRReport
from pbi_developer.utils.files import ensure_dir, write_json
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


def build_pbir_folder(report: PBIRReport, output_dir: Path) -> Path:
    """Build the complete PBIR folder structure on disk.

    Args:
        report: The PBIRReport model containing all pages and visuals.
        output_dir: Parent directory where the .Report folder will be created.

    Returns:
        Path to the created .Report folder.
    """
    report_dir = ensure_dir(output_dir / f"{report.name}.Report")
    logger.info(f"Building PBIR folder: {report_dir}")

    # definition.pbir
    write_json(report_dir / "definition.pbir", report.definition.to_pbir_json())

    # report.json
    write_json(report_dir / "report.json", report.settings.to_pbir_json())

    # definition/pages/
    pages_dir = ensure_dir(report_dir / "definition" / "pages")

    for page in report.pages:
        page_dir = ensure_dir(pages_dir / page.id)

        # page.json
        write_json(page_dir / "page.json", page.to_pbir_json())

        # visuals/
        visuals_dir = ensure_dir(page_dir / "visuals")

        for visual in page.visuals:
            visual_dir = ensure_dir(visuals_dir / visual.id)
            write_json(visual_dir / "visual.json", visual.to_pbir_json())
            logger.info(f"  Visual: {visual.visual_type} ({visual.id})")

        logger.info(f"  Page: {page.display_name} ({len(page.visuals)} visuals)")

    # Create .pbip marker file alongside the .Report folder
    pbip_path = output_dir / f"{report.name}.pbip"
    write_json(pbip_path, {
        "version": "1.0",
        "artifacts": [
            {
                "report": {
                    "path": f"{report.name}.Report",
                }
            }
        ],
    })

    logger.info(f"PBIR build complete: {len(report.pages)} pages, "
                f"{sum(len(p.visuals) for p in report.pages)} visuals")
    return report_dir
