"""Planner agent — Step 1 of the pipeline.

Parses dashboard requirements (text briefs, user questions, interview transcripts,
visual interpretations of mockups/recordings) into a structured brief JSON.

Output schema:
{
    "report_title": str,
    "audience": str,
    "pages": [
        {
            "page_name": str,
            "purpose": str,
            "questions_answered": [str],
            "suggested_visuals": [
                {
                    "visual_type": str,
                    "description": str,
                    "data_intent": str,
                    "position_hint": str  # "top-left", "center", "full-width", etc.
                }
            ],
            "suggested_filters": [str]
        }
    ],
    "kpis": [{"name": str, "description": str}],
    "analytical_questions": [str],
    "constraints": [str]
}
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pbi_developer.agents.base import BaseAgent
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """\
You are a Power BI report planning specialist. Your job is to analyze dashboard
requirements and produce a structured report specification.

You will receive one or more of:
- A text brief describing what the dashboard should show
- User questions the dashboard must answer
- Interview transcripts from stakeholders
- Visual descriptions of PowerPoint mockups or screen recordings

From these inputs, produce a structured plan that includes:
1. Report title and target audience
2. Pages with their purpose and the questions each page answers
3. For each page, the suggested visual types with their data intent
4. KPIs that should be prominently displayed
5. Analytical questions the report must answer
6. Any constraints mentioned in the requirements

Guidelines:
- Prefer simple, proven visual types: cards for KPIs, bar charts for comparisons,
  line charts for trends, tables for detail, slicers for filtering
- Limit to 6-8 visuals per page for readability
- Group related metrics on the same page
- Always include at least one slicer page or filter panel
- Flag any ambiguities in the requirements as constraints
"""

STRUCTURED_BRIEF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "report_title": {"type": "string"},
        "audience": {"type": "string"},
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page_name": {"type": "string"},
                    "purpose": {"type": "string"},
                    "questions_answered": {"type": "array", "items": {"type": "string"}},
                    "suggested_visuals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "visual_type": {"type": "string"},
                                "description": {"type": "string"},
                                "data_intent": {"type": "string"},
                                "position_hint": {"type": "string"},
                            },
                            "required": ["visual_type", "description", "data_intent"],
                        },
                    },
                    "suggested_filters": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["page_name", "purpose", "suggested_visuals"],
            },
        },
        "kpis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name", "description"],
            },
        },
        "analytical_questions": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["report_title", "pages", "kpis", "analytical_questions"],
}


class PlannerAgent(BaseAgent):
    """Parses requirements into a structured dashboard brief."""

    agent_name = "planner"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from pbi_developer.prompts import registry

        if registry.has("planner"):
            entry = registry.get("planner")
            self.system_prompt = entry.system_prompt
        else:
            self.system_prompt = PLANNER_SYSTEM_PROMPT

    def plan(
        self,
        brief_text: str,
        *,
        mockup_images: list[Path | bytes] | None = None,
        model_metadata: str | None = None,
    ) -> dict[str, Any]:
        """Parse requirements into a structured brief.

        Args:
            brief_text: Combined text from briefs, questions, transcripts.
            mockup_images: Optional images from PowerPoint or screenshots.
            model_metadata: Optional semantic model metadata to inform visual choices.

        Returns:
            Structured brief matching STRUCTURED_BRIEF_SCHEMA.
        """
        prompt_parts = [
            "Analyze the following dashboard requirements and produce a structured report plan.\n",
            "## Requirements\n",
            brief_text,
        ]

        if model_metadata:
            prompt_parts.extend(
                [
                    "\n\n## Available Semantic Model\n",
                    model_metadata,
                ]
            )

        if mockup_images:
            prompt_parts.append(
                "\n\nI've also attached mockup/screenshot images. "
                "Analyze the visual layout, chart types, and KPIs shown."
            )

        prompt = "\n".join(prompt_parts)
        logger.info(f"Planning report from {len(prompt)} chars of requirements")

        result = self.call_structured(
            prompt,
            output_schema=STRUCTURED_BRIEF_SCHEMA,
            images=mockup_images,
        )

        logger.info(
            f"Plan: {result.get('report_title', 'Untitled')} — "
            f"{len(result.get('pages', []))} pages, "
            f"{len(result.get('kpis', []))} KPIs"
        )
        return result
