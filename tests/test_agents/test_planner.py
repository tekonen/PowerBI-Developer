"""Tests for the PlannerAgent."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pbi_developer.agents.planner import (
    PLANNER_SYSTEM_PROMPT,
    STRUCTURED_BRIEF_SCHEMA,
    PlannerAgent,
)


@pytest.fixture
def planner(monkeypatch):
    """Create a PlannerAgent with mocked LangChain LLM."""
    monkeypatch.setattr("pbi_developer.agents.base.settings.claude.api_key", "fake-key")
    monkeypatch.setattr("pbi_developer.agents.base.settings.claude.model", "claude-sonnet-4-20250514")
    monkeypatch.setattr("pbi_developer.agents.base.settings.claude.max_tokens", 4096)
    monkeypatch.setattr("pbi_developer.agents.base.settings.claude.temperature", 0.2)
    monkeypatch.setattr("pbi_developer.agents.base.settings.claude.base_url", "")
    with patch("pbi_developer.agents.base.ChatAnthropic"):
        agent = PlannerAgent()
        yield agent


SAMPLE_PLAN = {
    "report_title": "Sales Dashboard",
    "audience": "Regional Managers",
    "pages": [
        {
            "page_name": "Overview",
            "purpose": "High-level KPIs",
            "questions_answered": ["What is total revenue?"],
            "suggested_visuals": [
                {
                    "visual_type": "card",
                    "description": "Total Revenue",
                    "data_intent": "Sum of revenue",
                    "position_hint": "top-left",
                }
            ],
            "suggested_filters": ["Date"],
        }
    ],
    "kpis": [{"name": "Total Revenue", "description": "Sum of all revenue"}],
    "analytical_questions": ["How does revenue trend over time?"],
    "constraints": [],
}


class TestPlannerPlan:
    """Test PlannerAgent.plan() method."""

    def test_plan_returns_structured_output(self, planner):
        """plan() should return the dict from call_structured."""
        with patch.object(planner, "call_structured", return_value=SAMPLE_PLAN):
            result = planner.plan("Build a sales dashboard with KPIs.")

        assert result["report_title"] == "Sales Dashboard"
        assert len(result["pages"]) == 1
        assert len(result["kpis"]) == 1

    def test_plan_passes_correct_schema(self, planner):
        """plan() should pass STRUCTURED_BRIEF_SCHEMA to call_structured."""
        with patch.object(planner, "call_structured", return_value=SAMPLE_PLAN) as mock_call:
            planner.plan("Build a dashboard")

        _, kwargs = mock_call.call_args
        assert kwargs["output_schema"] is STRUCTURED_BRIEF_SCHEMA

    def test_plan_prompt_contains_requirements(self, planner):
        """The prompt should include the brief text."""
        with patch.object(planner, "call_structured", return_value=SAMPLE_PLAN) as mock_call:
            planner.plan("Revenue by region quarterly")

        prompt = mock_call.call_args[0][0]
        assert "Revenue by region quarterly" in prompt
        assert "Requirements" in prompt

    def test_plan_with_model_metadata(self, planner):
        """When model_metadata is provided, it should appear in the prompt."""
        with patch.object(planner, "call_structured", return_value=SAMPLE_PLAN) as mock_call:
            planner.plan(
                "Build dashboard",
                model_metadata="Tables: Sales, Products\nMeasures: Revenue, Quantity",
            )

        prompt = mock_call.call_args[0][0]
        assert "Semantic Model" in prompt
        assert "Sales, Products" in prompt

    def test_plan_with_mockup_images(self, planner, tmp_path):
        """When images are provided, they should be passed through and prompt updated."""
        img_path = tmp_path / "mockup.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\nfake-image")

        with patch.object(planner, "call_structured", return_value=SAMPLE_PLAN) as mock_call:
            planner.plan("Build dashboard", mockup_images=[img_path])

        prompt = mock_call.call_args[0][0]
        assert "mockup/screenshot images" in prompt
        assert mock_call.call_args.kwargs["images"] == [img_path]

    def test_plan_with_bytes_images(self, planner):
        """Images as raw bytes should also work."""
        img_bytes = b"\x89PNG\r\n\x1a\nfake"

        with patch.object(planner, "call_structured", return_value=SAMPLE_PLAN) as mock_call:
            planner.plan("Build dashboard", mockup_images=[img_bytes])

        assert mock_call.call_args.kwargs["images"] == [img_bytes]

    def test_plan_without_images_no_image_text(self, planner):
        """When no images, the prompt should not mention screenshots."""
        with patch.object(planner, "call_structured", return_value=SAMPLE_PLAN) as mock_call:
            planner.plan("Simple dashboard")

        prompt = mock_call.call_args[0][0]
        assert "mockup/screenshot" not in prompt

    def test_plan_without_model_metadata(self, planner):
        """When no model_metadata, the prompt should not include model section."""
        with patch.object(planner, "call_structured", return_value=SAMPLE_PLAN) as mock_call:
            planner.plan("Simple dashboard")

        prompt = mock_call.call_args[0][0]
        assert "Semantic Model" not in prompt


class TestPlannerAgentAttributes:
    """Test PlannerAgent class attributes."""

    def test_system_prompt(self, planner):
        assert planner.system_prompt == PLANNER_SYSTEM_PROMPT
        assert "Power BI report planning" in planner.system_prompt

    def test_agent_name(self, planner):
        assert planner.agent_name == "planner"


class TestPlannerErrorHandling:
    """Test error paths in the planner."""

    def test_call_structured_raises_propagates(self, planner):
        """If call_structured raises, plan() should propagate it."""
        with (
            patch.object(planner, "call_structured", side_effect=RuntimeError("API failed")),
            pytest.raises(RuntimeError, match="API failed"),
        ):
            planner.plan("Build a dashboard")

    def test_call_structured_returns_raw_text(self, planner):
        """If call_structured returns a raw_text fallback, plan() still returns it."""
        fallback = {"raw_text": "Could not parse structured output"}
        with patch.object(planner, "call_structured", return_value=fallback):
            result = planner.plan("Build a dashboard")
        assert result == fallback
