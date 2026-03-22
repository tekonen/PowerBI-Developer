"""PBIR schema validation.

Validates generated PBIR JSON files against Microsoft's published JSON schemas.
Falls back to structural validation when schemas are not locally cached.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)

_SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "config" / "pbir_schemas"

REQUIRED_PROPERTIES = {
    "visual.json": ["name", "position", "visual"],
    "page.json": ["name", "displayName"],
    "definition.pbir": ["version"],
    "report.json": [],
}


@dataclass
class ValidationResult:
    """Result of PBIR validation."""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    files_checked: int = 0

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_pbir_folder(report_dir: Path) -> ValidationResult:
    """Validate a complete PBIR folder structure.

    Checks:
    1. Required files exist (definition.pbir, report.json)
    2. All JSON files are valid JSON
    3. Required properties are present in each file type
    4. Visual positions are within page bounds
    5. Page/visual folder structure is correct
    """
    result = ValidationResult()

    if not report_dir.exists():
        result.add_error(f"Report directory does not exist: {report_dir}")
        return result

    # Check definition.pbir
    pbir_file = report_dir / "definition.pbir"
    if not pbir_file.exists():
        result.add_error("Missing definition.pbir")
    else:
        _validate_json_file(pbir_file, "definition.pbir", result)

    # Check report.json
    report_file = report_dir / "report.json"
    if not report_file.exists():
        result.add_error("Missing report.json")
    else:
        _validate_json_file(report_file, "report.json", result)

    # Check pages
    pages_dir = report_dir / "definition" / "pages"
    if not pages_dir.exists():
        result.add_error("Missing definition/pages/ directory")
        return result

    page_dirs = [d for d in pages_dir.iterdir() if d.is_dir()]
    if not page_dirs:
        result.add_warning("No pages found in report")

    for page_dir in page_dirs:
        page_json = page_dir / "page.json"
        if not page_json.exists():
            result.add_error(f"Missing page.json in {page_dir.name}")
            continue

        page_data = _validate_json_file(page_json, "page.json", result)
        if page_data is None:
            continue

        page_width = page_data.get("width", 1280)
        page_height = page_data.get("height", 720)

        # Check visuals
        visuals_dir = page_dir / "visuals"
        if visuals_dir.exists():
            for visual_dir in visuals_dir.iterdir():
                if not visual_dir.is_dir():
                    continue
                visual_json = visual_dir / "visual.json"
                if not visual_json.exists():
                    result.add_error(f"Missing visual.json in {visual_dir.name}")
                    continue

                visual_data = _validate_json_file(visual_json, "visual.json", result)
                if visual_data:
                    _validate_visual_position(visual_data, page_width, page_height, result)

    return result


def _validate_json_file(path: Path, file_type: str, result: ValidationResult) -> dict[str, Any] | None:
    """Validate a JSON file has valid syntax and required properties."""
    result.files_checked += 1
    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result.add_error(f"Invalid JSON in {path}: {e}")
        return None

    required = REQUIRED_PROPERTIES.get(file_type, [])
    for prop in required:
        if prop not in data:
            result.add_error(f"Missing required property '{prop}' in {path}")

    # Try jsonschema validation if schemas are cached
    schema_path = _SCHEMA_DIR / f"{file_type}.schema.json"
    if schema_path.exists():
        try:
            import jsonschema

            with open(schema_path) as f:
                schema = json.load(f)
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:
            result.add_error(f"Schema validation failed for {path}: {e.message}")
        except Exception:
            pass  # jsonschema not installed or schema issue — skip

    return data


def _validate_visual_position(
    visual_data: dict[str, Any],
    page_width: int,
    page_height: int,
    result: ValidationResult,
) -> None:
    """Check that visual position is within page bounds."""
    pos = visual_data.get("position", {})
    name = visual_data.get("name", "unknown")
    x = pos.get("x", 0)
    y = pos.get("y", 0)
    w = pos.get("width", 0)
    h = pos.get("height", 0)

    if x + w > page_width:
        result.add_warning(f"Visual {name}: extends beyond page width ({x}+{w} > {page_width})")
    if y + h > page_height:
        result.add_warning(f"Visual {name}: extends beyond page height ({y}+{h} > {page_height})")
    if w <= 0 or h <= 0:
        result.add_error(f"Visual {name}: invalid dimensions (width={w}, height={h})")
