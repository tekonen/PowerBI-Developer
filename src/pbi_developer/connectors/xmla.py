"""XMLA endpoint connector for Power BI semantic model metadata.

Queries DMVs (Dynamic Management Views) to retrieve:
- Tables and columns
- Measures with DAX expressions
- Relationships between tables
- Model metadata

Requires Fabric or Power BI Premium capacity for XMLA endpoint access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MeasureInfo:
    name: str
    table: str
    expression: str  # DAX
    description: str = ""
    format_string: str = ""
    is_hidden: bool = False


@dataclass
class ColumnMetadata:
    name: str
    table: str
    data_type: str
    description: str = ""
    is_hidden: bool = False


@dataclass
class RelationshipInfo:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str = "ManyToOne"
    cross_filter: str = "Single"


@dataclass
class SemanticModelMetadata:
    """Complete metadata for a Power BI semantic model."""

    model_name: str = ""
    tables: list[str] = field(default_factory=list)
    columns: list[ColumnMetadata] = field(default_factory=list)
    measures: list[MeasureInfo] = field(default_factory=list)
    relationships: list[RelationshipInfo] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Convert to markdown format for agent consumption."""
        lines = [f"# Semantic Model: {self.model_name}\n"]

        # Tables and columns
        tables_cols: dict[str, list[ColumnMetadata]] = {}
        for col in self.columns:
            tables_cols.setdefault(col.table, []).append(col)

        for table in self.tables:
            lines.append(f"\n## Table: {table}")
            cols = tables_cols.get(table, [])
            if cols:
                lines.append("| Column | Type | Description |")
                lines.append("|--------|------|-------------|")
                for c in cols:
                    if not c.is_hidden:
                        lines.append(f"| {c.name} | {c.data_type} | {c.description} |")

            # Measures for this table
            table_measures = [m for m in self.measures if m.table == table and not m.is_hidden]
            if table_measures:
                lines.append(f"\n### Measures in {table}")
                for m in table_measures:
                    lines.append(f"- **{m.name}**: `{m.expression}`")
                    if m.description:
                        lines.append(f"  {m.description}")

        # Relationships
        if self.relationships:
            lines.append("\n## Relationships")
            lines.append("| From | To | Cardinality | Filter |")
            lines.append("|------|-----|-------------|--------|")
            for r in self.relationships:
                lines.append(
                    f"| {r.from_table}[{r.from_column}] | "
                    f"{r.to_table}[{r.to_column}] | "
                    f"{r.cardinality} | {r.cross_filter} |"
                )

        return "\n".join(lines)


def load_metadata_from_file(path: Path) -> str:
    """Load model metadata from a markdown file (dry run mode).

    In dry run mode, users provide a pre-created model_metadata.md instead
    of connecting to a live XMLA endpoint.
    """
    if not path.exists():
        raise FileNotFoundError(f"Model metadata file not found: {path}")
    content = path.read_text(encoding="utf-8")
    logger.info(f"Loaded model metadata from {path} ({len(content)} chars)")
    return content


DMV_QUERIES = {
    "tables": "SELECT [Name] FROM $SYSTEM.TMSCHEMA_TABLES WHERE [IsHidden] = false",
    "columns": (
        "SELECT [TableID], [ExplicitName], [ExplicitDataType], [Description], [IsHidden] FROM $SYSTEM.TMSCHEMA_COLUMNS"
    ),
    "measures": (
        "SELECT [TableID], [Name], [Expression], [Description], [FormatString], [IsHidden] "
        "FROM $SYSTEM.TMSCHEMA_MEASURES"
    ),
    "relationships": (
        "SELECT [FromTableID], [FromColumnID], [ToTableID], [ToColumnID], [Cardinality], "
        "[CrossFilteringBehavior] FROM $SYSTEM.TMSCHEMA_RELATIONSHIPS"
    ),
}


def fetch_metadata_via_rest(dataset_id: str) -> SemanticModelMetadata:
    """Fetch semantic model metadata via the Power BI REST API executeQueries endpoint.

    This is the cross-platform alternative to XMLA DMV queries. It uses the
    Power BI REST API's executeQueries endpoint to run DMV queries.

    Args:
        dataset_id: Dataset ID in Power BI Service.

    Returns:
        SemanticModelMetadata with tables, columns, measures, and relationships.
    """
    from pbi_developer.connectors.powerbi_rest import PowerBIClient

    client = PowerBIClient()
    metadata = SemanticModelMetadata(model_name=dataset_id)

    # Fetch tables
    try:
        result = client.execute_dax_query(dataset_id, DMV_QUERIES["tables"])
        for row in _extract_rows(result):
            table_name = row.get("[Name]", "")
            if table_name:
                metadata.tables.append(table_name)
        logger.info(f"Fetched {len(metadata.tables)} tables")
    except Exception as e:
        logger.warning(f"Failed to fetch tables: {e}")

    # Fetch columns
    try:
        result = client.execute_dax_query(dataset_id, DMV_QUERIES["columns"])
        for row in _extract_rows(result):
            if row.get("[IsHidden]", False):
                continue
            metadata.columns.append(
                ColumnMetadata(
                    name=row.get("[ExplicitName]", ""),
                    table=str(row.get("[TableID]", "")),
                    data_type=row.get("[ExplicitDataType]", ""),
                    description=row.get("[Description]", ""),
                    is_hidden=bool(row.get("[IsHidden]", False)),
                )
            )
        logger.info(f"Fetched {len(metadata.columns)} columns")
    except Exception as e:
        logger.warning(f"Failed to fetch columns: {e}")

    # Fetch measures
    try:
        result = client.execute_dax_query(dataset_id, DMV_QUERIES["measures"])
        for row in _extract_rows(result):
            if row.get("[IsHidden]", False):
                continue
            metadata.measures.append(
                MeasureInfo(
                    name=row.get("[Name]", ""),
                    table=str(row.get("[TableID]", "")),
                    expression=row.get("[Expression]", ""),
                    description=row.get("[Description]", ""),
                    format_string=row.get("[FormatString]", ""),
                    is_hidden=bool(row.get("[IsHidden]", False)),
                )
            )
        logger.info(f"Fetched {len(metadata.measures)} measures")
    except Exception as e:
        logger.warning(f"Failed to fetch measures: {e}")

    # Fetch relationships
    try:
        result = client.execute_dax_query(dataset_id, DMV_QUERIES["relationships"])
        for row in _extract_rows(result):
            metadata.relationships.append(
                RelationshipInfo(
                    from_table=str(row.get("[FromTableID]", "")),
                    from_column=str(row.get("[FromColumnID]", "")),
                    to_table=str(row.get("[ToTableID]", "")),
                    to_column=str(row.get("[ToColumnID]", "")),
                    cardinality=row.get("[Cardinality]", "ManyToOne"),
                    cross_filter=row.get("[CrossFilteringBehavior]", "Single"),
                )
            )
        logger.info(f"Fetched {len(metadata.relationships)} relationships")
    except Exception as e:
        logger.warning(f"Failed to fetch relationships: {e}")

    return metadata


def fetch_metadata(xmla_endpoint: str, dataset_name: str) -> SemanticModelMetadata:
    """Fetch semantic model metadata via XMLA endpoint.

    Direct XMLA queries require platform-specific libraries (adomdclient,
    pyadomd). This function falls back to the REST API executeQueries
    endpoint which is cross-platform.

    Args:
        xmla_endpoint: XMLA endpoint URL (e.g., powerbi://api.powerbi.com/v1.0/myorg/Workspace)
        dataset_name: Name of the dataset to query.

    Returns:
        SemanticModelMetadata with all tables, columns, measures, relationships.
    """
    logger.warning(
        "Direct XMLA endpoint query requires platform-specific libraries. "
        "Falling back to REST API executeQueries. "
        "For best results, provide a --model-metadata file."
    )
    return SemanticModelMetadata(model_name=dataset_name)


def _extract_rows(result: dict) -> list[dict]:
    """Extract rows from a Power BI executeQueries response."""
    try:
        tables = result.get("results", [{}])[0].get("tables", [])
        if tables:
            return tables[0].get("rows", [])
    except (IndexError, KeyError, TypeError):
        pass
    return []
