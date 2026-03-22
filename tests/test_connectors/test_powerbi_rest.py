"""Tests for the Power BI REST API client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from pbi_developer.connectors.powerbi_rest import PowerBIClient


@pytest.fixture
def client(monkeypatch):
    """Create a PowerBIClient with mocked settings and token."""
    monkeypatch.setattr(
        "pbi_developer.connectors.powerbi_rest.settings.powerbi.api_base",
        "https://api.powerbi.com/v1.0/myorg",
    )
    monkeypatch.setattr(
        "pbi_developer.connectors.powerbi_rest.settings.powerbi.workspace_id",
        "ws-123",
    )
    with patch("pbi_developer.connectors.powerbi_rest.get_powerbi_token", return_value="fake-token"):
        c = PowerBIClient(workspace_id="ws-123")
        # Pre-populate token to avoid repeated auth calls
        c._token = "fake-token"
        yield c


def _mock_response(json_data=None, status_code=200, raise_for_status=None):
    """Build a mock requests.Response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if raise_for_status:
        resp.raise_for_status.side_effect = raise_for_status
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------- list_workspaces ----------


class TestListWorkspaces:
    @patch("pbi_developer.connectors.powerbi_rest.requests.get")
    def test_success(self, mock_get, client):
        workspaces = [{"id": "ws-1", "name": "Dev"}, {"id": "ws-2", "name": "Prod"}]
        mock_get.return_value = _mock_response({"value": workspaces})

        result = client.list_workspaces()

        assert result == workspaces
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        assert call_url.endswith("/groups")

    @patch("pbi_developer.connectors.powerbi_rest.requests.get")
    def test_http_error(self, mock_get, client):
        mock_get.return_value = _mock_response(
            status_code=401,
            raise_for_status=requests.HTTPError("401 Unauthorized"),
        )
        with pytest.raises(requests.HTTPError):
            client.list_workspaces()

    @patch("pbi_developer.connectors.powerbi_rest.requests.get")
    def test_empty_value(self, mock_get, client):
        mock_get.return_value = _mock_response({"value": []})
        result = client.list_workspaces()
        assert result == []


# ---------- list_datasets ----------


class TestListDatasets:
    @patch("pbi_developer.connectors.powerbi_rest.requests.get")
    def test_success(self, mock_get, client):
        datasets = [{"id": "ds-1", "name": "Sales"}]
        mock_get.return_value = _mock_response({"value": datasets})

        result = client.list_datasets()

        assert result == datasets
        call_url = mock_get.call_args[0][0]
        assert "/groups/ws-123/datasets" in call_url

    @patch("pbi_developer.connectors.powerbi_rest.requests.get")
    def test_http_error(self, mock_get, client):
        mock_get.return_value = _mock_response(
            status_code=403,
            raise_for_status=requests.HTTPError("403 Forbidden"),
        )
        with pytest.raises(requests.HTTPError):
            client.list_datasets()


# ---------- execute_dax_query ----------


class TestExecuteDaxQuery:
    @patch("pbi_developer.connectors.powerbi_rest.requests.post")
    def test_success(self, mock_post, client):
        dax_result = {"results": [{"tables": [{"rows": [{"[Total]": 42}]}]}]}
        mock_post.return_value = _mock_response(dax_result)

        result = client.execute_dax_query("ds-1", "EVALUATE ROW('Total', 42)")

        assert result == dax_result
        call_kwargs = mock_post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["queries"][0]["query"] == "EVALUATE ROW('Total', 42)"
        assert body["serializerSettings"]["includeNulls"] is True

    @patch("pbi_developer.connectors.powerbi_rest.requests.post")
    def test_http_error(self, mock_post, client):
        mock_post.return_value = _mock_response(
            status_code=400,
            raise_for_status=requests.HTTPError("400 Bad Request"),
        )
        with pytest.raises(requests.HTTPError):
            client.execute_dax_query("ds-1", "INVALID DAX")


# ---------- import_pbix ----------


class TestImportPbix:
    @patch("pbi_developer.connectors.powerbi_rest.requests.post")
    def test_success(self, mock_post, client, tmp_path):
        pbix_file = tmp_path / "report.pbix"
        pbix_file.write_bytes(b"PK\x03\x04fake-pbix-content")

        import_result = {"id": "import-1", "name": "My Report"}
        mock_post.return_value = _mock_response(import_result)

        result = client.import_pbix(pbix_file, "My Report")

        assert result == import_result
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        assert "imports" in call_url
        assert "datasetDisplayName=My Report" in call_url

    @patch("pbi_developer.connectors.powerbi_rest.requests.post")
    def test_http_error(self, mock_post, client, tmp_path):
        pbix_file = tmp_path / "report.pbix"
        pbix_file.write_bytes(b"PK\x03\x04fake")

        mock_post.return_value = _mock_response(
            status_code=409,
            raise_for_status=requests.HTTPError("409 Conflict"),
        )
        with pytest.raises(requests.HTTPError):
            client.import_pbix(pbix_file, "Duplicate")


# ---------- add_rls_member ----------


class TestAddRlsMember:
    @patch("pbi_developer.connectors.powerbi_rest.requests.post")
    def test_success(self, mock_post, client):
        mock_post.return_value = _mock_response(status_code=200)

        client.add_rls_member("ds-1", "SalesRole", "user@example.com")

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["identifier"] == "user@example.com"
        assert body["principalType"] == "User"
        assert body["datasetUserAccessRight"] == "Read"
        call_url = call_kwargs[0][0]
        assert "/datasets/ds-1/users" in call_url

    @patch("pbi_developer.connectors.powerbi_rest.requests.post")
    def test_http_error(self, mock_post, client):
        mock_post.return_value = _mock_response(
            status_code=404,
            raise_for_status=requests.HTTPError("404 Not Found"),
        )
        with pytest.raises(requests.HTTPError):
            client.add_rls_member("ds-bad", "Role", "user@example.com")


# ---------- deploy_pipeline_stage ----------


class TestDeployPipelineStage:
    @patch("pbi_developer.connectors.powerbi_rest.requests.post")
    def test_success_no_items(self, mock_post, client):
        deploy_result = {"operationId": "op-1"}
        mock_post.return_value = _mock_response(deploy_result)

        result = client.deploy_pipeline_stage("pipe-1", 0)

        assert result == deploy_result
        call_kwargs = mock_post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["sourceStageOrder"] == 0
        call_url = call_kwargs[0][0]
        assert "/pipelines/pipe-1/deploy" in call_url

    @patch("pbi_developer.connectors.powerbi_rest.requests.post")
    def test_success_with_items(self, mock_post, client):
        deploy_result = {"operationId": "op-2"}
        mock_post.return_value = _mock_response(deploy_result)

        items = [
            {"type": "dataset", "sourceId": "ds-1"},
            {"type": "report", "sourceId": "rpt-1"},
        ]
        result = client.deploy_pipeline_stage("pipe-1", 1, items=items)

        assert result == deploy_result
        call_kwargs = mock_post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["sourceStageOrder"] == 1
        assert len(body["datasets"]) == 1
        assert len(body["reports"]) == 1

    @patch("pbi_developer.connectors.powerbi_rest.requests.post")
    def test_http_error(self, mock_post, client):
        mock_post.return_value = _mock_response(
            status_code=500,
            raise_for_status=requests.HTTPError("500 Internal Server Error"),
        )
        with pytest.raises(requests.HTTPError):
            client.deploy_pipeline_stage("pipe-1", 0)


# ---------- Token & Headers ----------


class TestTokenAndHeaders:
    def test_token_calls_get_powerbi_token(self, monkeypatch):
        monkeypatch.setattr(
            "pbi_developer.connectors.powerbi_rest.settings.powerbi.api_base",
            "https://api.powerbi.com/v1.0/myorg",
        )
        monkeypatch.setattr(
            "pbi_developer.connectors.powerbi_rest.settings.powerbi.workspace_id",
            "ws-123",
        )
        with patch(
            "pbi_developer.connectors.powerbi_rest.get_powerbi_token",
            return_value="my-token",
        ) as mock_token:
            c = PowerBIClient()
            assert c.token == "my-token"
            mock_token.assert_called_once()

    def test_headers_include_bearer(self, client):
        headers = client.headers
        assert headers["Authorization"] == "Bearer fake-token"
        assert headers["Content-Type"] == "application/json"

    def test_url_with_workspace(self, client):
        url = client._url("datasets")
        assert "/groups/ws-123/datasets" in url

    def test_url_without_workspace(self, monkeypatch):
        monkeypatch.setattr(
            "pbi_developer.connectors.powerbi_rest.settings.powerbi.api_base",
            "https://api.powerbi.com/v1.0/myorg",
        )
        monkeypatch.setattr(
            "pbi_developer.connectors.powerbi_rest.settings.powerbi.workspace_id",
            "",
        )
        with patch("pbi_developer.connectors.powerbi_rest.get_powerbi_token", return_value="t"):
            c = PowerBIClient(workspace_id=None)
            c.workspace_id = None
            url = c._url("datasets")
            assert url == "https://api.powerbi.com/v1.0/myorg/datasets"
