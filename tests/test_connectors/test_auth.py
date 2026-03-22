"""Tests for authentication and connection testing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestConnectionTest:
    def test_unknown_target(self):
        from pbi_developer.connectors.auth import test_connection

        success, msg = test_connection("unknown")
        assert not success
        assert "Unknown target" in msg

    def test_xmla_connection_success(self):
        from pbi_developer.connectors.auth import test_connection

        mock_client = MagicMock()
        mock_client.list_datasets.return_value = [{"id": "ds1"}, {"id": "ds2"}]
        mock_cls = MagicMock(return_value=mock_client)

        with patch("pbi_developer.connectors.powerbi_rest.PowerBIClient", mock_cls):
            success, msg = test_connection("xmla")

        assert success
        assert "2 dataset(s)" in msg

    def test_xmla_connection_failure(self):
        from pbi_developer.connectors.auth import test_connection

        mock_cls = MagicMock(side_effect=Exception("No credentials"))

        with patch("pbi_developer.connectors.powerbi_rest.PowerBIClient", mock_cls):
            success, msg = test_connection("xmla")

        assert not success
        assert "failed" in msg
