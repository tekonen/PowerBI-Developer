"""Tests for the diagram interpreter agent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pbi_developer.agents.diagram_interpreter import DiagramInterpreterAgent

MOCK_INTERPRETATION = {
    "diagram_type": "physical_model",
    "entities": [
        {
            "name": "Customers",
            "entity_type": "table",
            "columns": [
                {"name": "CustomerID", "data_type": "INT", "is_key": True},
            ],
        },
        {
            "name": "Orders",
            "entity_type": "table",
            "columns": [
                {"name": "OrderID", "data_type": "INT", "is_key": True},
                {"name": "CustomerID", "data_type": "INT", "is_key": False},
            ],
        },
    ],
    "relationships": [
        {
            "from_entity": "Orders",
            "to_entity": "Customers",
            "relationship_type": "foreign_key",
            "cardinality": "ManyToOne",
            "from_column": "CustomerID",
            "to_column": "CustomerID",
        },
    ],
}


class TestDiagramInterpreterAgent:
    def test_interpret_calls_structured(self):
        agent = DiagramInterpreterAgent.__new__(DiagramInterpreterAgent)
        agent.client = MagicMock()
        agent.model = "test-model"
        agent.max_tokens = 4096
        agent._total_input_tokens = 0
        agent._total_output_tokens = 0

        with patch.object(agent, "call_structured", return_value=MOCK_INTERPRETATION) as mock_call:
            result = agent.interpret(
                raster_png=b"fake-png",
                text_labels=["Customers", "Orders", "CustomerID", "OrderID"],
            )

        mock_call.assert_called_once()
        call_args = mock_call.call_args
        assert "Customers" in call_args[0][0]  # prompt contains labels
        assert call_args[1]["images"] == [b"fake-png"]

        assert result["diagram_type"] == "physical_model"
        assert len(result["entities"]) == 2
        assert len(result["relationships"]) == 1

    def test_interpret_without_raster(self):
        agent = DiagramInterpreterAgent.__new__(DiagramInterpreterAgent)
        agent.client = MagicMock()
        agent.model = "test-model"
        agent.max_tokens = 4096
        agent._total_input_tokens = 0
        agent._total_output_tokens = 0

        with patch.object(agent, "call_structured", return_value=MOCK_INTERPRETATION) as mock_call:
            result = agent.interpret(raster_png=b"", text_labels=["Customers", "Orders"])

        # No images passed when raster is empty
        call_args = mock_call.call_args
        assert call_args[1]["images"] is None
        assert result["diagram_type"] == "physical_model"

    def test_interpret_without_labels(self):
        agent = DiagramInterpreterAgent.__new__(DiagramInterpreterAgent)
        agent.client = MagicMock()
        agent.model = "test-model"
        agent.max_tokens = 4096
        agent._total_input_tokens = 0
        agent._total_output_tokens = 0

        with patch.object(agent, "call_structured", return_value=MOCK_INTERPRETATION):
            result = agent.interpret(raster_png=b"fake-png", text_labels=[])

        assert result is not None

    def test_agent_class_attributes(self):
        assert DiagramInterpreterAgent.agent_name == "diagram_interpreter"
        assert "data model" in DiagramInterpreterAgent.system_prompt.lower()
