"""Tests for XMLA connector metadata fetching."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestFetchMetadataViaRest:
    """Test the REST API-based metadata fetch."""

    def test_fetches_tables(self):
        from pbi_developer.connectors.xmla import fetch_metadata_via_rest

        mock_client = MagicMock()
        mock_client.execute_dax_query.side_effect = [
            {"results": [{"tables": [{"rows": [{"[Name]": "Employee"}, {"[Name]": "Date"}]}]}]},
            {"results": [{"tables": [{"rows": []}]}]},
            {"results": [{"tables": [{"rows": []}]}]},
            {"results": [{"tables": [{"rows": []}]}]},
        ]

        with patch("pbi_developer.connectors.powerbi_rest.PowerBIClient", return_value=mock_client):
            result = fetch_metadata_via_rest("dataset-123")

        assert result.model_name == "dataset-123"
        assert result.tables == ["Employee", "Date"]

    def test_handles_query_failure_gracefully(self):
        from pbi_developer.connectors.xmla import fetch_metadata_via_rest

        mock_client = MagicMock()
        mock_client.execute_dax_query.side_effect = Exception("Connection refused")

        with patch("pbi_developer.connectors.powerbi_rest.PowerBIClient", return_value=mock_client):
            result = fetch_metadata_via_rest("dataset-123")

        assert result.model_name == "dataset-123"
        assert result.tables == []
        assert result.measures == []


class TestExtractRows:
    def test_extracts_rows_from_valid_response(self):
        from pbi_developer.connectors.xmla import _extract_rows

        response = {"results": [{"tables": [{"rows": [{"col": "val"}]}]}]}
        assert _extract_rows(response) == [{"col": "val"}]

    def test_returns_empty_for_empty_response(self):
        from pbi_developer.connectors.xmla import _extract_rows

        assert _extract_rows({}) == []
        assert _extract_rows({"results": []}) == []


class TestFetchMetadataLegacy:
    def test_returns_empty_metadata(self):
        from pbi_developer.connectors.xmla import fetch_metadata

        result = fetch_metadata("powerbi://endpoint", "MyDataset")
        assert result.model_name == "MyDataset"
        assert result.tables == []
