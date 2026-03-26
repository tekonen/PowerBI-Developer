"""Diagram interpreter agent — analyzes SVG diagrams of data models.

Takes a rasterized PNG of the diagram and extracted text labels, then
produces structured entities and relationships for the knowledge graph.

Output schema:
{
    "diagram_type": "physical_model" | "business_model",
    "entities": [
        {
            "name": str,
            "entity_type": "table" | "business_entity",
            "description": str,
            "columns": [{"name": str, "data_type": str, "is_key": bool}]
        }
    ],
    "relationships": [
        {
            "from_entity": str,
            "to_entity": str,
            "relationship_type": "foreign_key" | "association" | "inheritance",
            "cardinality": "OneToOne" | "OneToMany" | "ManyToOne" | "ManyToMany",
            "from_column": str,
            "to_column": str,
            "label": str
        }
    ]
}
"""

from __future__ import annotations

from typing import Any

from pbi_developer.agents.base import BaseAgent
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)

INTERPRETER_SYSTEM_PROMPT = """\
You are a data model diagram analyst. You receive a rasterized image of an \
entity-relationship diagram or physical table diagram, along with a list of \
text labels extracted from the SVG source.

Your task is to identify:
1. All entities (tables, business objects) shown in the diagram
2. Their columns/attributes if visible
3. All relationships between entities (lines, arrows, connectors)
4. Cardinality of each relationship (1:1, 1:N, N:M) if indicated

Rules:
- Use the provided text labels as the EXACT names for entities and columns. \
Do not invent names that are not in the text labels.
- If the diagram shows physical tables with data types, classify as "physical_model".
- If the diagram shows conceptual/business entities without data types, classify \
as "business_model".
- For each relationship, identify the direction (from → to) based on arrows or \
foreign key indicators (FK, PK).
- If cardinality markers are visible (1, N, M, *, 0..1, etc.), use them. \
Otherwise default to "ManyToOne".
- Include a short description for each entity if context clues are available.
"""

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "diagram_type": {
            "type": "string",
            "enum": ["physical_model", "business_model"],
        },
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "entity_type": {"type": "string", "enum": ["table", "business_entity"]},
                    "description": {"type": "string"},
                    "columns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "data_type": {"type": "string"},
                                "is_key": {"type": "boolean"},
                            },
                            "required": ["name"],
                        },
                    },
                },
                "required": ["name", "entity_type"],
            },
        },
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from_entity": {"type": "string"},
                    "to_entity": {"type": "string"},
                    "relationship_type": {
                        "type": "string",
                        "enum": ["foreign_key", "association", "inheritance"],
                    },
                    "cardinality": {
                        "type": "string",
                        "enum": ["OneToOne", "OneToMany", "ManyToOne", "ManyToMany"],
                    },
                    "from_column": {"type": "string"},
                    "to_column": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["from_entity", "to_entity"],
            },
        },
    },
    "required": ["diagram_type", "entities", "relationships"],
}


class DiagramInterpreterAgent(BaseAgent):
    """Interprets SVG data model diagrams into structured entities and relationships."""

    agent_name = "diagram_interpreter"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from pbi_developer.prompts import registry

        if registry.has("diagram_interpreter"):
            self.system_prompt = registry.get("diagram_interpreter").system_prompt
        else:
            self.system_prompt = INTERPRETER_SYSTEM_PROMPT

    def interpret(
        self,
        raster_png: bytes,
        text_labels: list[str],
    ) -> dict[str, Any]:
        """Analyze a rasterized diagram image and extracted text labels.

        Args:
            raster_png: PNG bytes of the rasterized SVG diagram.
            text_labels: List of text strings extracted from the SVG XML.

        Returns:
            Structured dict with diagram_type, entities, and relationships.
        """
        labels_text = "\n".join(f"- {label}" for label in text_labels) if text_labels else "(no text labels extracted)"

        prompt = (
            "Analyze this data model diagram and extract all entities and relationships.\n\n"
            f"## Text labels extracted from the SVG source\n{labels_text}\n\n"
            "Use these exact label strings as entity and column names. "
            "Return the structured output describing all entities and their relationships."
        )

        images = [raster_png] if raster_png else None

        result = self.call_structured(
            prompt,
            OUTPUT_SCHEMA,
            images=images,
            temperature=0.1,
        )

        logger.info(
            f"Interpreted diagram: type={result.get('diagram_type')}, "
            f"entities={len(result.get('entities', []))}, "
            f"relationships={len(result.get('relationships', []))}"
        )
        return result
