"""Tests for agent correction/refinement support."""

from __future__ import annotations

from unittest.mock import patch


class TestWireframeAgentCorrections:
    """Test that WireframeAgent includes correction context in prompts."""

    @patch("pbi_developer.agents.base.BaseAgent.call_structured")
    def test_design_with_corrections(self, mock_call, sample_structured_brief):
        from pbi_developer.agents.wireframe import WireframeAgent

        previous = {"pages": [{"page_name": "Old", "visuals": []}]}
        mock_call.return_value = {"pages": [{"page_name": "New", "visuals": []}]}

        agent = WireframeAgent()
        agent.design(
            sample_structured_brief,
            corrections="Add a slicer for Location",
            previous_output=previous,
        )

        prompt = mock_call.call_args[0][0]
        assert "Previous Wireframe" in prompt
        assert "Corrections Requested" in prompt
        assert "Add a slicer for Location" in prompt

    @patch("pbi_developer.agents.base.BaseAgent.call_structured")
    def test_design_without_corrections(self, mock_call, sample_structured_brief):
        from pbi_developer.agents.wireframe import WireframeAgent

        mock_call.return_value = {"pages": []}

        agent = WireframeAgent()
        agent.design(sample_structured_brief)

        prompt = mock_call.call_args[0][0]
        assert "Previous Wireframe" not in prompt
        assert "Corrections Requested" not in prompt


class TestFieldMapperAgentCorrections:
    """Test that FieldMapperAgent includes correction context in prompts."""

    @patch("pbi_developer.agents.base.BaseAgent.call_structured")
    def test_map_fields_with_corrections(self, mock_call):
        from pbi_developer.agents.field_mapper import FieldMapperAgent

        wireframe = {"pages": [{"page_name": "P1", "visuals": []}]}
        previous = {"pages": [{"page_name": "P1", "visuals": [{"field_mappings": []}]}]}
        mock_call.return_value = {"pages": [{"page_name": "P1", "visuals": []}]}

        agent = FieldMapperAgent()
        agent.map_fields(
            wireframe,
            "# Model\nNo metadata",
            corrections="Use Avg Tenure (Years) instead of Avg Tenure",
            previous_output=previous,
        )

        prompt = mock_call.call_args[0][0]
        assert "Previous Field Mappings" in prompt
        assert "Corrections Requested" in prompt
        assert "Avg Tenure (Years)" in prompt

    @patch("pbi_developer.agents.base.BaseAgent.call_structured")
    def test_map_fields_without_corrections(self, mock_call):
        from pbi_developer.agents.field_mapper import FieldMapperAgent

        mock_call.return_value = {"pages": []}

        agent = FieldMapperAgent()
        agent.map_fields({"pages": []}, "# Model")

        prompt = mock_call.call_args[0][0]
        assert "Previous Field Mappings" not in prompt


class TestDaxGeneratorAgentCorrections:
    """Test that DaxGeneratorAgent includes correction context in prompts."""

    @patch("pbi_developer.agents.base.BaseAgent.call_structured")
    def test_generate_measures_with_corrections(self, mock_call):
        from pbi_developer.agents.dax_generator import DaxGeneratorAgent

        metrics = [{"name": "Attrition Rate", "description": "Rolling attrition"}]
        previous = {"measures": [{"name": "Attrition Rate", "expression": "OLD_DAX"}]}
        mock_call.return_value = {"measures": []}

        agent = DaxGeneratorAgent()
        agent.generate_measures(
            metrics,
            "# Model",
            corrections="Use DATESINPERIOD for 12-month rolling window",
            previous_output=previous,
        )

        prompt = mock_call.call_args[0][0]
        assert "Previous Measures" in prompt
        assert "Corrections Requested" in prompt
        assert "DATESINPERIOD" in prompt

    @patch("pbi_developer.agents.base.BaseAgent.call_structured")
    def test_generate_measures_without_corrections(self, mock_call):
        from pbi_developer.agents.dax_generator import DaxGeneratorAgent

        mock_call.return_value = {"measures": []}

        agent = DaxGeneratorAgent()
        agent.generate_measures([{"name": "X", "description": "Y"}], "# Model")

        prompt = mock_call.call_args[0][0]
        assert "Previous Measures" not in prompt


class TestRLSAgentCorrections:
    """Test that RLSAgent includes correction context in prompts."""

    @patch("pbi_developer.agents.base.BaseAgent.call_structured")
    def test_generate_rls_with_corrections(self, mock_call):
        from pbi_developer.agents.rls import RLSAgent

        examples = [{"user": "alice@co.com", "expected": "HR data"}]
        previous = {"roles": [{"role_name": "HRViewer"}], "validation_results": []}
        mock_call.return_value = {"roles": [], "validation_results": []}

        agent = RLSAgent()
        agent.generate_rls(
            "Managers see their department",
            examples,
            "# Model",
            corrections="Include sub-regions for regional managers",
            previous_output=previous,
        )

        prompt = mock_call.call_args[0][0]
        assert "Previous RLS Config" in prompt
        assert "Corrections Requested" in prompt
        assert "sub-regions" in prompt

    @patch("pbi_developer.agents.base.BaseAgent.call_structured")
    def test_generate_rls_without_corrections(self, mock_call):
        from pbi_developer.agents.rls import RLSAgent

        mock_call.return_value = {"roles": [], "validation_results": []}

        agent = RLSAgent()
        agent.generate_rls("Managers see dept", [{"user": "a@b.com", "expected": "all"}], "# Model")

        prompt = mock_call.call_args[0][0]
        assert "Previous RLS Config" not in prompt
