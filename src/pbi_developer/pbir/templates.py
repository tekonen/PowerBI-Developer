"""Built-in PBIR visual templates.

Provides parameterized visual templates for common Power BI visual types.
Claude fills in the parameters (data bindings, position, formatting) rather
than generating PBIR JSON from scratch — this reduces hallucination risk.
"""

from __future__ import annotations

from pbi_developer.pbir.models import (
    DataFieldBinding,
    PBIRVisual,
    VisualDataRole,
    VisualFormatting,
    VisualPosition,
)


def card_visual(
    *,
    measure_table: str,
    measure_name: str,
    title: str = "",
    x: int = 0,
    y: int = 0,
    width: int = 200,
    height: int = 120,
) -> PBIRVisual:
    """Create a KPI card visual."""
    return PBIRVisual(
        visual_type="card",
        position=VisualPosition(x=x, y=y, width=width, height=height),
        data_roles=[
            VisualDataRole(
                role="Fields",
                bindings=[DataFieldBinding(table=measure_table, measure=measure_name)],
            )
        ],
        formatting=VisualFormatting(title=title, show_title=bool(title)),
    )


def clustered_bar_chart(
    *,
    category_table: str,
    category_column: str,
    value_table: str,
    value_measure: str,
    title: str = "",
    legend_table: str | None = None,
    legend_column: str | None = None,
    x: int = 0,
    y: int = 0,
    width: int = 400,
    height: int = 300,
) -> PBIRVisual:
    """Create a clustered bar chart."""
    roles = [
        VisualDataRole(
            role="Category",
            bindings=[DataFieldBinding(table=category_table, column=category_column)],
        ),
        VisualDataRole(
            role="Y",
            bindings=[DataFieldBinding(table=value_table, measure=value_measure)],
        ),
    ]
    if legend_table and legend_column:
        roles.append(
            VisualDataRole(
                role="Series",
                bindings=[DataFieldBinding(table=legend_table, column=legend_column)],
            )
        )
    return PBIRVisual(
        visual_type="clusteredBarChart",
        position=VisualPosition(x=x, y=y, width=width, height=height),
        data_roles=roles,
        formatting=VisualFormatting(title=title, show_title=bool(title)),
    )


def line_chart(
    *,
    category_table: str,
    category_column: str,
    value_table: str,
    value_measure: str,
    title: str = "",
    legend_table: str | None = None,
    legend_column: str | None = None,
    x: int = 0,
    y: int = 0,
    width: int = 500,
    height: int = 300,
) -> PBIRVisual:
    """Create a line chart."""
    roles = [
        VisualDataRole(
            role="Category",
            bindings=[DataFieldBinding(table=category_table, column=category_column)],
        ),
        VisualDataRole(
            role="Y",
            bindings=[DataFieldBinding(table=value_table, measure=value_measure)],
        ),
    ]
    if legend_table and legend_column:
        roles.append(
            VisualDataRole(
                role="Series",
                bindings=[DataFieldBinding(table=legend_table, column=legend_column)],
            )
        )
    return PBIRVisual(
        visual_type="lineChart",
        position=VisualPosition(x=x, y=y, width=width, height=height),
        data_roles=roles,
        formatting=VisualFormatting(title=title, show_title=bool(title)),
    )


def table_visual(
    *,
    columns: list[tuple[str, str]],
    title: str = "",
    x: int = 0,
    y: int = 0,
    width: int = 600,
    height: int = 350,
) -> PBIRVisual:
    """Create a table visual.

    Args:
        columns: List of (table_name, column_name) tuples to display.
    """
    bindings = [DataFieldBinding(table=t, column=c) for t, c in columns]
    return PBIRVisual(
        visual_type="tableEx",
        position=VisualPosition(x=x, y=y, width=width, height=height),
        data_roles=[
            VisualDataRole(role="Values", bindings=bindings),
        ],
        formatting=VisualFormatting(title=title, show_title=bool(title)),
    )


def matrix_visual(
    *,
    row_table: str,
    row_column: str,
    value_table: str,
    value_measure: str,
    column_table: str | None = None,
    column_column: str | None = None,
    title: str = "",
    x: int = 0,
    y: int = 0,
    width: int = 600,
    height: int = 400,
) -> PBIRVisual:
    """Create a matrix visual."""
    roles = [
        VisualDataRole(
            role="Rows",
            bindings=[DataFieldBinding(table=row_table, column=row_column)],
        ),
        VisualDataRole(
            role="Values",
            bindings=[DataFieldBinding(table=value_table, measure=value_measure)],
        ),
    ]
    if column_table and column_column:
        roles.append(
            VisualDataRole(
                role="Columns",
                bindings=[DataFieldBinding(table=column_table, column=column_column)],
            )
        )
    return PBIRVisual(
        visual_type="pivotTable",
        position=VisualPosition(x=x, y=y, width=width, height=height),
        data_roles=roles,
        formatting=VisualFormatting(title=title, show_title=bool(title)),
    )


def slicer_visual(
    *,
    table: str,
    column: str,
    title: str = "",
    x: int = 0,
    y: int = 0,
    width: int = 200,
    height: int = 300,
) -> PBIRVisual:
    """Create a slicer (filter) visual."""
    return PBIRVisual(
        visual_type="slicer",
        position=VisualPosition(x=x, y=y, width=width, height=height),
        data_roles=[
            VisualDataRole(
                role="Values",
                bindings=[DataFieldBinding(table=table, column=column)],
            ),
        ],
        formatting=VisualFormatting(title=title, show_title=bool(title)),
    )


def donut_chart(
    *,
    category_table: str,
    category_column: str,
    value_table: str,
    value_measure: str,
    title: str = "",
    x: int = 0,
    y: int = 0,
    width: int = 300,
    height: int = 300,
) -> PBIRVisual:
    """Create a donut chart."""
    return PBIRVisual(
        visual_type="donutChart",
        position=VisualPosition(x=x, y=y, width=width, height=height),
        data_roles=[
            VisualDataRole(
                role="Category",
                bindings=[DataFieldBinding(table=category_table, column=category_column)],
            ),
            VisualDataRole(
                role="Y",
                bindings=[DataFieldBinding(table=value_table, measure=value_measure)],
            ),
        ],
        formatting=VisualFormatting(title=title, show_title=bool(title)),
    )


VISUAL_TYPE_MAP = {
    "card": card_visual,
    "clusteredBarChart": clustered_bar_chart,
    "lineChart": line_chart,
    "tableEx": table_visual,
    "table": table_visual,
    "pivotTable": matrix_visual,
    "matrix": matrix_visual,
    "slicer": slicer_visual,
    "donutChart": donut_chart,
}
