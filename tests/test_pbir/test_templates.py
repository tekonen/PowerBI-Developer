"""Tests for PBIR visual templates."""

from pbi_developer.pbir.templates import (
    card_visual,
    clustered_bar_chart,
    donut_chart,
    line_chart,
    matrix_visual,
    slicer_visual,
    table_visual,
)


def test_card_visual():
    v = card_visual(measure_table="HR", measure_name="Headcount", title="Total Headcount")
    assert v.visual_type == "card"
    assert len(v.data_roles) == 1
    assert v.data_roles[0].role == "Fields"
    j = v.to_pbir_json()
    assert j["visual"]["visualType"] == "card"


def test_clustered_bar_chart():
    v = clustered_bar_chart(
        category_table="Employee",
        category_column="Department",
        value_table="HR",
        value_measure="Attrition Rate",
        title="Attrition by Department",
    )
    assert v.visual_type == "clusteredBarChart"
    assert len(v.data_roles) == 2


def test_clustered_bar_chart_with_legend():
    v = clustered_bar_chart(
        category_table="Employee",
        category_column="Department",
        value_table="HR",
        value_measure="Headcount",
        legend_table="Employee",
        legend_column="Gender",
    )
    assert len(v.data_roles) == 3


def test_line_chart():
    v = line_chart(
        category_table="Date",
        category_column="MonthYear",
        value_table="HR",
        value_measure="Headcount",
    )
    assert v.visual_type == "lineChart"


def test_table_visual():
    v = table_visual(
        columns=[("Employee", "Name"), ("Employee", "Department"), ("Employee", "Start Date")],
        title="Employee List",
    )
    assert v.visual_type == "tableEx"
    assert len(v.data_roles[0].bindings) == 3


def test_matrix_visual():
    v = matrix_visual(
        row_table="Employee",
        row_column="Department",
        value_table="HR",
        value_measure="Headcount",
        column_table="Date",
        column_column="Year",
    )
    assert v.visual_type == "pivotTable"
    assert len(v.data_roles) == 3


def test_slicer_visual():
    v = slicer_visual(table="Employee", column="Department")
    assert v.visual_type == "slicer"


def test_donut_chart():
    v = donut_chart(
        category_table="Employee",
        category_column="Gender",
        value_table="HR",
        value_measure="Headcount",
    )
    assert v.visual_type == "donutChart"
