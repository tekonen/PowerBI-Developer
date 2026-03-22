"""Field mapping agent — Step 4 of the pipeline.

Takes the wireframe and maps actual semantic model fields (tables, columns,
measures) into each visual slot defined by the architect.

Separating architecture from field mapping keeps each agent's task bounded
and reduces errors — a single agent trying to do both tends to hallucinate
field names.
"""

from __future__ import annotations

from typing import Any

from pbi_developer.agents.base import BaseAgent
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)

FIELD_MAPPER_SYSTEM_PROMPT = """\
You are a Power BI field mapping specialist. Given a wireframe specification
and semantic model metadata, you map the correct data fields to each visual.

Rules:
1. ONLY use fields that exist in the semantic model metadata. Never invent field names.
2. For each visual, map the appropriate fields to the correct data roles:
   - card: Fields (one measure)
   - clusteredBarChart / clusteredColumnChart: Category (column), Y (measure), optionally Series (column)
   - lineChart / areaChart: Category (date/time column), Y (measure), optionally Series (column)
   - tableEx: Values (list of columns and measures)
   - pivotTable: Rows (column), Columns (optional column), Values (measure)
   - slicer: Values (column to filter on)
   - donutChart: Category (column), Y (measure)
3. Match fields semantically: if the data_intent says "attrition by department",
   look for an attrition measure and a department column.
4. Prefer certified measures over raw columns when available.
5. Use table names exactly as they appear in the metadata.
6. If you cannot find an appropriate field, mark it as "UNMAPPED" with a reason.

Output the same wireframe structure but with field mappings added to each visual.
"""

FIELD_MAPPED_WIREFRAME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page_name": {"type": "string"},
                    "visuals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "visual_type": {"type": "string"},
                                "title": {"type": "string"},
                                "data_intent": {"type": "string"},
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "width": {"type": "integer"},
                                "height": {"type": "integer"},
                                "field_mappings": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "role": {"type": "string"},
                                            "table": {"type": "string"},
                                            "field": {"type": "string"},
                                            "field_type": {
                                                "type": "string",
                                                "enum": ["column", "measure"],
                                            },
                                            "unmapped_reason": {"type": "string"},
                                        },
                                        "required": ["role", "table", "field", "field_type"],
                                    },
                                },
                            },
                            "required": ["visual_type", "field_mappings", "x", "y", "width", "height"],
                        },
                    },
                },
                "required": ["page_name", "visuals"],
            },
        },
        "unmapped_fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "visual_title": {"type": "string"},
                    "role": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
    },
    "required": ["pages"],
}


class FieldMapperAgent(BaseAgent):
    """Maps semantic model fields to wireframe visuals."""

    system_prompt = FIELD_MAPPER_SYSTEM_PROMPT
    agent_name = "field_mapper"

    def map_fields(
        self,
        wireframe: dict[str, Any],
        model_metadata: str,
        *,
        corrections: str | None = None,
        previous_output: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Map semantic model fields to each visual in the wireframe.

        Args:
            wireframe: Wireframe spec from WireframeAgent.
            model_metadata: Semantic model metadata as markdown text.
            corrections: Natural language corrections to apply to previous output.
            previous_output: Previous field-mapped wireframe to refine.

        Returns:
            Field-mapped wireframe matching FIELD_MAPPED_WIREFRAME_SCHEMA.
        """
        import json

        prompt = (
            "Map semantic model fields to each visual in this wireframe.\n\n"
            f"## Wireframe\n```json\n{json.dumps(wireframe, indent=2)}\n```\n\n"
            f"## Semantic Model Metadata\n{model_metadata}\n\n"
            "For each visual, add field_mappings with the correct table, field name, "
            "and whether it's a column or measure. "
            "If you cannot find an appropriate field, set field_type to 'column' "
            "and add an unmapped_reason."
        )

        if corrections and previous_output:
            prompt += (
                f"\n\n## Previous Field Mappings\n```json\n{json.dumps(previous_output, indent=2)}\n```\n"
                f"\n## Corrections Requested\n{corrections}\n\n"
                "Revise the field mappings based on the corrections. "
                "Keep mappings not mentioned in the corrections unchanged."
            )

        logger.info("Mapping fields to wireframe visuals...")
        result = self.call_structured(prompt, output_schema=FIELD_MAPPED_WIREFRAME_SCHEMA)

        # Count mappings
        total_mapped = 0
        total_unmapped = 0
        for page in result.get("pages", []):
            for visual in page.get("visuals", []):
                for fm in visual.get("field_mappings", []):
                    if fm.get("unmapped_reason"):
                        total_unmapped += 1
                    else:
                        total_mapped += 1

        logger.info(f"Field mapping: {total_mapped} mapped, {total_unmapped} unmapped")
        if total_unmapped > 0:
            logger.warning(f"  {total_unmapped} fields could not be mapped")

        return result
