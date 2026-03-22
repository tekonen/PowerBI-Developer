"""DAX generation agent.

Generates and validates DAX measures given metric definitions.
Useful for People Analytics where complex cohort logic is common
(rolling 12-month attrition, FTE calculations, gender pay gap ratios).
"""

from __future__ import annotations

from typing import Any

from pbi_developer.agents.base import BaseAgent
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)

DAX_GENERATOR_SYSTEM_PROMPT = """\
You are a DAX measure generation specialist for Power BI. Given a metric
definition and semantic model context, you generate correct, optimized DAX.

Guidelines:
1. Use CALCULATE, FILTER, ALL, ALLEXCEPT correctly
2. Handle time intelligence with DATEADD, SAMEPERIODLASTYEAR, TOTALYTD, etc.
3. Use variables (VAR/RETURN) for readability and performance
4. Include format strings appropriate to the measure type
5. Add measure descriptions explaining the calculation logic
6. Follow naming conventions: no prefix for base measures, suffix indicators
   like "%" for ratios, "YoY" for year-over-year
7. Validate that all table and column references exist in the model

For People Analytics / HR measures:
- Headcount: Use COUNTROWS with appropriate date filters
- Attrition: Rolling window with cohort-based denominators
- FTE: Sum or average depending on business definition
- Diversity metrics: Ratios with appropriate denominators
"""

DAX_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "measures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "table": {"type": "string"},
                    "expression": {"type": "string"},
                    "format_string": {"type": "string"},
                    "description": {"type": "string"},
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Other measures this measure depends on",
                    },
                },
                "required": ["name", "table", "expression"],
            },
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["measures"],
}


class DaxGeneratorAgent(BaseAgent):
    """Generates DAX measures from metric definitions."""

    system_prompt = DAX_GENERATOR_SYSTEM_PROMPT
    agent_name = "dax_generator"

    def generate_measures(
        self,
        metric_definitions: list[dict[str, str]],
        model_metadata: str,
    ) -> dict[str, Any]:
        """Generate DAX measures for the given metric definitions.

        Args:
            metric_definitions: List of dicts with "name" and "description" keys.
            model_metadata: Semantic model metadata as markdown.

        Returns:
            Dict with "measures" list and optional "warnings".
        """

        metrics_text = "\n".join(
            f"- **{m['name']}**: {m.get('description', 'No description')}" for m in metric_definitions
        )

        prompt = (
            "Generate DAX measures for the following metrics:\n\n"
            f"{metrics_text}\n\n"
            f"## Semantic Model\n{model_metadata}\n\n"
            "Generate valid DAX that references only tables and columns that exist "
            "in the model. Include format strings and descriptions."
        )

        logger.info(f"Generating {len(metric_definitions)} DAX measure(s)")
        result = self.call_structured(prompt, output_schema=DAX_OUTPUT_SCHEMA)
        logger.info(f"Generated {len(result.get('measures', []))} measures")
        return result
