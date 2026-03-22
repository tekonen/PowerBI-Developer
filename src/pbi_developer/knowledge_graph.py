"""Persistent knowledge graph for business and physical data models.

Stores entities (tables, business objects, columns, measures) and their
relationships as a directed graph. Persists to JSON and accumulates
knowledge across pipeline runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_GRAPH_PATH = Path.home() / ".pbi-dev" / "knowledge_graph.json"


class KnowledgeGraphStore:
    """NetworkX-backed knowledge graph with JSON persistence.

    Stores entities as nodes and relationships as edges. The graph is
    shared across pipeline runs and accumulates knowledge over time.
    """

    def __init__(self, path: Path | None = None):
        self.path = path or _DEFAULT_GRAPH_PATH
        self.graph: nx.DiGraph = nx.DiGraph()
        self._load()

    # --- Persistence ---

    def _load(self) -> None:
        """Load graph from JSON file if it exists."""
        if not self.path.exists():
            return
        try:
            with open(self.path) as f:
                data = json.load(f)
            self.graph = nx.node_link_graph(data, directed=True)
            n, e = self.graph.number_of_nodes(), self.graph.number_of_edges()
            logger.info(f"Loaded knowledge graph: {n} nodes, {e} edges")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to load knowledge graph from {self.path}: {e}")
            self.graph = nx.DiGraph()

    def save(self) -> None:
        """Save graph to JSON file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self.graph)
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)
        n, e = self.graph.number_of_nodes(), self.graph.number_of_edges()
        logger.info(f"Saved knowledge graph: {n} nodes, {e} edges")

    # --- Mutation ---

    def add_entity(self, name: str, entity_type: str, **attrs: Any) -> None:
        """Add or update an entity node.

        Args:
            name: Entity name (table name, business entity name, etc.)
            entity_type: One of "table", "business_entity", "column", "measure"
            **attrs: Additional attributes (data_type, description, schema, expression, etc.)
        """
        self.graph.add_node(name, entity_type=entity_type, **attrs)

    def add_relationship(self, from_entity: str, to_entity: str, **attrs: Any) -> None:
        """Add or update a relationship edge.

        Args:
            from_entity: Source entity name.
            to_entity: Target entity name.
            **attrs: Relationship attributes (relationship_type, cardinality, cross_filter,
                     from_column, to_column, label, etc.)
        """
        self.graph.add_edge(from_entity, to_entity, **attrs)

    def merge_from_svg_interpretation(self, interpretation: dict[str, Any]) -> None:
        """Merge structured output from DiagramInterpreterAgent into the graph.

        Expected interpretation format:
        {
            "diagram_type": "physical_model" | "business_model",
            "entities": [{"name": str, "entity_type": str, "columns": [...], ...}],
            "relationships": [{"from_entity": str, "to_entity": str, "cardinality": str, ...}]
        }
        """
        for entity in interpretation.get("entities", []):
            name = entity.get("name", "")
            if not name:
                continue
            entity_type = entity.get("entity_type", "table")
            attrs = {k: v for k, v in entity.items() if k not in ("name", "entity_type", "columns")}
            self.add_entity(name, entity_type, **attrs)

            # Add columns as separate nodes linked to the table
            for col in entity.get("columns", []):
                col_name = col.get("name", "")
                if col_name:
                    full_col_name = f"{name}.{col_name}"
                    col_attrs = {k: v for k, v in col.items() if k != "name"}
                    self.add_entity(full_col_name, "column", table=name, **col_attrs)
                    self.add_relationship(name, full_col_name, relationship_type="has_column")

        for rel in interpretation.get("relationships", []):
            from_e = rel.get("from_entity", "")
            to_e = rel.get("to_entity", "")
            if from_e and to_e:
                attrs = {k: v for k, v in rel.items() if k not in ("from_entity", "to_entity")}
                self.add_relationship(from_e, to_e, **attrs)

        logger.info(
            f"Merged SVG interpretation: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges"
        )

    def merge_from_metadata(self, metadata: Any) -> None:
        """Import from a SemanticModelMetadata instance (accumulative).

        Args:
            metadata: A SemanticModelMetadata dataclass instance.
        """
        for table in metadata.tables:
            self.add_entity(table, "table")

        for col in metadata.columns:
            full_name = f"{col.table}.{col.name}"
            self.add_entity(full_name, "column", table=col.table, data_type=col.data_type)
            self.add_relationship(col.table, full_name, relationship_type="has_column")

        for measure in metadata.measures:
            full_name = f"{measure.table}.{measure.name}"
            self.add_entity(full_name, "measure", table=measure.table, expression=measure.expression)
            self.add_relationship(measure.table, full_name, relationship_type="has_measure")

        for rel in metadata.relationships:
            self.add_relationship(
                rel.from_table,
                rel.to_table,
                relationship_type="foreign_key",
                from_column=rel.from_column,
                to_column=rel.to_column,
                cardinality=rel.cardinality,
                cross_filter=rel.cross_filter,
            )

    # --- Query ---

    def get_tables(self) -> list[dict[str, Any]]:
        """Return all table-type entities."""
        return [{"name": n, **d} for n, d in self.graph.nodes(data=True) if d.get("entity_type") == "table"]

    def get_relationships(self) -> list[dict[str, Any]]:
        """Return all relationship edges (excluding has_column/has_measure structural edges)."""
        return [
            {"from_entity": u, "to_entity": v, **d}
            for u, v, d in self.graph.edges(data=True)
            if d.get("relationship_type") not in ("has_column", "has_measure")
        ]

    def get_entity(self, name: str) -> dict[str, Any] | None:
        """Return entity data by name, or None if not found."""
        if name in self.graph:
            return {"name": name, **dict(self.graph.nodes[name])}
        return None

    def find_path(self, from_entity: str, to_entity: str) -> list[str]:
        """Find shortest path between two entities.

        Returns list of entity names forming the path, or empty list if no path exists.
        """
        try:
            return list(nx.shortest_path(self.graph, from_entity, to_entity))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def clear(self) -> None:
        """Remove all nodes and edges from the graph."""
        self.graph.clear()

    # --- Export ---

    def to_metadata_markdown(self) -> str:
        """Export graph as markdown in SemanticModelMetadata.to_markdown() format.

        Produces table headings with columns, and a relationships table.
        Returns empty string if the graph has no table entities.
        """
        tables = self.get_tables()
        if not tables:
            return ""

        lines = ["# Knowledge Graph Model\n"]

        for table in tables:
            table_name = table["name"]
            lines.append(f"\n## Table: {table_name}")

            # Find columns for this table
            columns = [
                (n, d)
                for n, d in self.graph.nodes(data=True)
                if d.get("entity_type") == "column" and d.get("table") == table_name
            ]
            if columns:
                lines.append("| Column | Type | Description |")
                lines.append("|--------|------|-------------|")
                for full_name, col_data in columns:
                    col_name = full_name.split(".", 1)[-1] if "." in full_name else full_name
                    data_type = col_data.get("data_type", "")
                    desc = col_data.get("description", "")
                    lines.append(f"| {col_name} | {data_type} | {desc} |")

            # Find measures for this table
            measures = [
                (n, d)
                for n, d in self.graph.nodes(data=True)
                if d.get("entity_type") == "measure" and d.get("table") == table_name
            ]
            if measures:
                lines.append(f"\n### Measures in {table_name}")
                for full_name, m_data in measures:
                    m_name = full_name.split(".", 1)[-1] if "." in full_name else full_name
                    expr = m_data.get("expression", "")
                    lines.append(f"- **{m_name}**: `{expr}`")

        # Relationships
        rels = self.get_relationships()
        if rels:
            lines.append("\n## Relationships")
            lines.append("| From | To | Type | Cardinality |")
            lines.append("|------|-----|------|-------------|")
            for rel in rels:
                from_col = rel.get("from_column", "")
                to_col = rel.get("to_column", "")
                from_str = f"{rel['from_entity']}[{from_col}]" if from_col else rel["from_entity"]
                to_str = f"{rel['to_entity']}[{to_col}]" if to_col else rel["to_entity"]
                rel_type = rel.get("relationship_type", "")
                cardinality = rel.get("cardinality", "")
                lines.append(f"| {from_str} | {to_str} | {rel_type} | {cardinality} |")

        return "\n".join(lines)

    def to_brief_context(self) -> str:
        """Export a concise summary for planner brief context."""
        tables = self.get_tables()
        rels = self.get_relationships()
        if not tables:
            return ""

        table_names = [t["name"] for t in tables]
        lines = [
            f"The knowledge graph contains {len(tables)} tables and {len(rels)} relationships.",
            f"Tables: {', '.join(table_names[:20])}{'...' if len(table_names) > 20 else ''}",
        ]
        if rels:
            lines.append("Key relationships:")
            for rel in rels[:10]:
                card = rel.get("cardinality", "")
                card_str = f" ({card})" if card else ""
                lines.append(f"- {rel['from_entity']} → {rel['to_entity']}{card_str}")
            if len(rels) > 10:
                lines.append(f"- ... and {len(rels) - 10} more")
        return "\n".join(lines)
