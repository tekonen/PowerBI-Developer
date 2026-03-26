"""QA agent — Step 5 of the pipeline.

Reviews the field-mapped wireframe before PBIR conversion. Checks for:
- Missing required fields in any visual
- Logical inconsistencies (e.g. ratio measure as additive bar chart)
- Layout issues (overlapping visuals, too many per page)
- Compliance with report standards
- All referenced fields exist in the model metadata

Outputs structured pass/fail with specific issues to enable automated retry loops.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pbi_developer.agents.base import BaseAgent
from pbi_developer.config import settings
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)

QA_SYSTEM_PROMPT = """\
You are a Power BI report quality assurance specialist. Your job is to
review a field-mapped wireframe and identify issues before it is converted
to PBIR format.

Check for:
1. **Missing fields**: Every visual must have at least one field mapped to
   its required data roles. A card needs a measure. A bar chart needs a
   category and a value.
2. **Invalid field references**: All table and column/measure names must
   exist in the semantic model metadata provided.
3. **Logical issues**: A percentage/ratio measure should not be summed in a
   stacked bar chart. Date columns should be on the X-axis of line charts.
4. **Layout issues**: Visuals should not overlap. No more than {max_visuals}
   visuals per page. Visuals should be within page bounds ({page_width}x{page_height}).
5. **Standards compliance**: Check against naming conventions and preferred
   visual types.
6. **Data role completeness**: Each visual type has required roles:
   - card: Fields (1 measure)
   - clusteredBarChart: Category + Y
   - lineChart: Category + Y
   - tableEx: Values (at least 1)
   - pivotTable: Rows + Values
   - slicer: Values (1 column)

For each issue found, provide:
- severity: "error" (blocks generation) or "warning" (proceed with caution)
- visual_id: which visual has the issue (page_name + visual title)
- description: what's wrong
- suggestion: how to fix it
"""

QA_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "passed": {"type": "boolean"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["error", "warning"]},
                    "visual_id": {"type": "string"},
                    "description": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["severity", "description"],
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["passed", "issues", "summary"],
}

# Required data roles per visual type
REQUIRED_ROLES: dict[str, list[str]] = {
    "card": ["Fields"],
    "clusteredBarChart": ["Category", "Y"],
    "clusteredColumnChart": ["Category", "Y"],
    "lineChart": ["Category", "Y"],
    "areaChart": ["Category", "Y"],
    "tableEx": ["Values"],
    "pivotTable": ["Rows", "Values"],
    "slicer": ["Values"],
    "donutChart": ["Category", "Y"],
    "treemap": ["Group", "Values"],
    "gauge": ["Value"],
}


@dataclass
class QAIssue:
    severity: str  # "error" or "warning"
    visual_id: str
    description: str
    suggestion: str = ""


@dataclass
class QAResult:
    passed: bool = True
    issues: list[QAIssue] = field(default_factory=list)
    summary: str = ""

    def add_error(self, visual_id: str, desc: str, suggestion: str = "") -> None:
        self.issues.append(QAIssue("error", visual_id, desc, suggestion))
        self.passed = False

    def add_warning(self, visual_id: str, desc: str, suggestion: str = "") -> None:
        self.issues.append(QAIssue("warning", visual_id, desc, suggestion))


class QAAgent(BaseAgent):
    """Validates field-mapped wireframes before PBIR generation."""

    agent_name = "qa"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        from pbi_developer.prompts import registry

        standards = settings.report_standards
        page = settings.pbir
        template_kwargs = {
            "max_visuals": standards.page_structure.get("max_visuals_per_page", 8),
            "page_width": page.default_page_width,
            "page_height": page.default_page_height,
        }
        if registry.has("qa"):
            self.system_prompt = registry.get_rendered("qa", **template_kwargs)
        else:
            self.system_prompt = QA_SYSTEM_PROMPT.format(**template_kwargs)

    def validate(
        self,
        field_mapped_wireframe: dict[str, Any],
        model_metadata: str,
    ) -> QAResult:
        """Run QA checks on a field-mapped wireframe.

        Combines programmatic checks with AI-powered review.

        Returns:
            QAResult with pass/fail and list of issues.
        """
        result = QAResult()

        # Run programmatic checks first (fast, deterministic)
        self._check_structure(field_mapped_wireframe, result)
        self._check_layout(field_mapped_wireframe, result)
        self._check_required_roles(field_mapped_wireframe, result)

        # Run AI-powered semantic checks
        ai_result = self._ai_review(field_mapped_wireframe, model_metadata)
        for issue in ai_result.get("issues", []):
            if issue.get("severity") == "error":
                result.add_error(
                    issue.get("visual_id", ""),
                    issue.get("description", ""),
                    issue.get("suggestion", ""),
                )
            else:
                result.add_warning(
                    issue.get("visual_id", ""),
                    issue.get("description", ""),
                    issue.get("suggestion", ""),
                )

        errors = sum(1 for i in result.issues if i.severity == "error")
        warnings = sum(1 for i in result.issues if i.severity == "warning")
        result.summary = f"{errors} error(s), {warnings} warning(s)"
        if errors > 0:
            result.passed = False

        logger.info(f"QA result: {'PASSED' if result.passed else 'FAILED'} — {result.summary}")
        return result

    def _check_structure(self, wireframe: dict[str, Any], result: QAResult) -> None:
        """Check basic wireframe structure."""
        pages = wireframe.get("pages", [])
        if not pages:
            result.add_error("report", "No pages defined in wireframe")

        for page in pages:
            visuals = page.get("visuals", [])
            if not visuals:
                result.add_warning(
                    page.get("page_name", "unknown"),
                    "Page has no visuals",
                )

    def _check_layout(self, wireframe: dict[str, Any], result: QAResult) -> None:
        """Check for layout issues (overlapping, bounds)."""
        page_w = settings.pbir.default_page_width
        page_h = settings.pbir.default_page_height
        max_vis = settings.report_standards.page_structure.get("max_visuals_per_page", 8)

        for page in wireframe.get("pages", []):
            page_name = page.get("page_name", "unknown")
            visuals = page.get("visuals", [])

            if len(visuals) > max_vis:
                result.add_warning(
                    page_name,
                    f"Page has {len(visuals)} visuals (max recommended: {max_vis})",
                    "Consider splitting into multiple pages",
                )

            for v in visuals:
                title = v.get("title", v.get("visual_type", "unknown"))
                x, y = v.get("x", 0), v.get("y", 0)
                w, h = v.get("width", 0), v.get("height", 0)
                if x + w > page_w or y + h > page_h:
                    result.add_warning(
                        f"{page_name}/{title}",
                        f"Visual extends beyond page bounds ({x}+{w}, {y}+{h})",
                    )

    def _check_required_roles(self, wireframe: dict[str, Any], result: QAResult) -> None:
        """Check that all visuals have their required data roles mapped."""
        for page in wireframe.get("pages", []):
            page_name = page.get("page_name", "unknown")
            for v in page.get("visuals", []):
                vtype = v.get("visual_type", "")
                title = v.get("title", vtype)
                mappings = v.get("field_mappings", [])
                mapped_roles = {m.get("role") for m in mappings if not m.get("unmapped_reason")}

                required = REQUIRED_ROLES.get(vtype, [])
                for role in required:
                    if role not in mapped_roles:
                        result.add_error(
                            f"{page_name}/{title}",
                            f"Missing required role '{role}' for {vtype}",
                            f"Map a {'measure' if role in ('Y', 'Values', 'Fields', 'Value') else 'column'} "
                            f"to the '{role}' role",
                        )

    def _ai_review(self, wireframe: dict[str, Any], model_metadata: str) -> dict[str, Any]:
        """Use Claude for semantic QA checks."""
        import json

        prompt = (
            "Review this field-mapped wireframe for logical and semantic issues.\n\n"
            f"## Wireframe\n```json\n{json.dumps(wireframe, indent=2)}\n```\n\n"
            f"## Model Metadata\n{model_metadata}\n\n"
            "Focus on:\n"
            "- Fields that don't exist in the model\n"
            "- Logical mismatches (ratio on stacked chart, text field as value, etc.)\n"
            "- Missing analytical context\n"
            "Only report real issues. If everything looks correct, return passed=true with empty issues."
        )
        return self.call_structured(prompt, output_schema=QA_OUTPUT_SCHEMA)
