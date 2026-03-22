"""Shared pytest fixtures for pbi-developer tests."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_brief_text() -> str:
    return (FIXTURES_DIR / "sample_brief.md").read_text(encoding="utf-8")


@pytest.fixture
def sample_model_metadata() -> str:
    return (FIXTURES_DIR / "sample_model_metadata.md").read_text(encoding="utf-8")


@pytest.fixture
def sample_structured_brief() -> dict:
    """A structured brief matching the PlannerAgent output schema."""
    return {
        "report_title": "HR Dashboard",
        "audience": "HR Leadership Team",
        "pages": [
            {
                "page_name": "Executive Summary",
                "purpose": "High-level KPIs and trends",
                "questions_answered": [
                    "What is our current headcount?",
                    "How has headcount trended?",
                ],
                "suggested_visuals": [
                    {
                        "visual_type": "card",
                        "description": "Total Headcount",
                        "data_intent": "Show current headcount",
                        "position_hint": "top-left",
                    },
                    {
                        "visual_type": "lineChart",
                        "description": "Headcount Trend",
                        "data_intent": "Headcount over 12 months",
                        "position_hint": "center",
                    },
                ],
                "suggested_filters": ["Department"],
            },
        ],
        "kpis": [
            {"name": "Headcount", "description": "Active employees"},
            {"name": "Attrition Rate", "description": "Rolling attrition"},
        ],
        "analytical_questions": [
            "What is our current headcount?",
            "What is the attrition rate by department?",
        ],
        "constraints": [],
    }


@pytest.fixture
def sample_field_mapped_wireframe() -> dict:
    """A field-mapped wireframe ready for QA validation."""
    return {
        "pages": [
            {
                "page_name": "Executive Summary",
                "visuals": [
                    {
                        "visual_type": "card",
                        "title": "Total Headcount",
                        "x": 20,
                        "y": 80,
                        "width": 200,
                        "height": 120,
                        "field_mappings": [
                            {
                                "role": "Fields",
                                "table": "HR Measures",
                                "field": "Headcount",
                                "field_type": "measure",
                            }
                        ],
                    },
                    {
                        "visual_type": "lineChart",
                        "title": "Headcount Trend",
                        "x": 20,
                        "y": 220,
                        "width": 600,
                        "height": 300,
                        "field_mappings": [
                            {
                                "role": "Category",
                                "table": "Date",
                                "field": "MonthYear",
                                "field_type": "column",
                            },
                            {
                                "role": "Y",
                                "table": "HR Measures",
                                "field": "Headcount",
                                "field_type": "measure",
                            },
                        ],
                    },
                    {
                        "visual_type": "slicer",
                        "title": "Department Filter",
                        "x": 20,
                        "y": 540,
                        "width": 200,
                        "height": 40,
                        "field_mappings": [
                            {
                                "role": "Values",
                                "table": "Employee",
                                "field": "Department",
                                "field_type": "column",
                            }
                        ],
                    },
                ],
            },
        ],
    }
