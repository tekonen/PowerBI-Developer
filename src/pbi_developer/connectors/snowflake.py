"""Snowflake schema discovery connector.

Connects to Snowflake, crawls schemas, and auto-documents table relationships,
data types, and row counts. Outputs a semantic layer map for downstream agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pbi_developer.connectors.auth import get_snowflake_connection
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool = True
    comment: str = ""


@dataclass
class TableInfo:
    schema_name: str
    table_name: str
    table_type: str  # TABLE, VIEW
    columns: list[ColumnInfo] = field(default_factory=list)
    row_count: int = 0
    comment: str = ""


@dataclass
class SnowflakeSchema:
    database: str
    tables: list[TableInfo] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Convert schema to markdown for agent consumption."""
        lines = [f"# Snowflake Schema: {self.database}\n"]
        for tbl in self.tables:
            lines.append(f"\n## {tbl.schema_name}.{tbl.table_name}")
            lines.append(f"Type: {tbl.table_type} | Rows: ~{tbl.row_count:,}")
            if tbl.comment:
                lines.append(f"Description: {tbl.comment}")
            lines.append("\n| Column | Type | Nullable | Description |")
            lines.append("|--------|------|----------|-------------|")
            for col in tbl.columns:
                lines.append(
                    f"| {col.name} | {col.data_type} | {col.nullable} | {col.comment} |"
                )
        return "\n".join(lines)


def discover_schema(
    *,
    database: str | None = None,
    schema: str | None = None,
    include_row_counts: bool = True,
) -> SnowflakeSchema:
    """Discover Snowflake schema: tables, columns, types, row counts.

    Args:
        database: Database to scan (defaults to configured database).
        schema: Schema to scan (defaults to all schemas or configured schema).
        include_row_counts: Whether to query row counts (slower but useful).

    Returns:
        SnowflakeSchema with all discovered tables and columns.
    """
    conn = get_snowflake_connection()
    cursor = conn.cursor()

    db = database or conn.database
    result = SnowflakeSchema(database=db)

    # Get tables
    schema_filter = f"AND TABLE_SCHEMA = '{schema}'" if schema else "AND TABLE_SCHEMA != 'INFORMATION_SCHEMA'"
    cursor.execute(f"""
        SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE, COMMENT
        FROM {db}.INFORMATION_SCHEMA.TABLES
        WHERE TABLE_CATALOG = '{db}' {schema_filter}
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """)

    tables = cursor.fetchall()
    logger.info(f"Found {len(tables)} tables in {db}")

    for schema_name, table_name, table_type, comment in tables:
        table_info = TableInfo(
            schema_name=schema_name,
            table_name=table_name,
            table_type=table_type,
            comment=comment or "",
        )

        # Get columns
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COMMENT
            FROM {db}.INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_CATALOG = '{db}'
              AND TABLE_SCHEMA = '{schema_name}'
              AND TABLE_NAME = '{table_name}'
            ORDER BY ORDINAL_POSITION
        """)

        for col_name, data_type, nullable, col_comment in cursor.fetchall():
            table_info.columns.append(ColumnInfo(
                name=col_name,
                data_type=data_type,
                nullable=(nullable == "YES"),
                comment=col_comment or "",
            ))

        # Get row count
        if include_row_counts:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{db}"."{schema_name}"."{table_name}"')
                table_info.row_count = cursor.fetchone()[0]
            except Exception:
                table_info.row_count = -1

        result.tables.append(table_info)
        logger.info(f"  {schema_name}.{table_name}: {len(table_info.columns)} columns, ~{table_info.row_count:,} rows")

    conn.close()
    return result
