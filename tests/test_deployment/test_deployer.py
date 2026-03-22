"""Tests for the deployment module."""

from __future__ import annotations

from unittest.mock import patch


class TestDeployReviewGate:
    """Test that production deployment is blocked when review is required."""

    @patch("pbi_developer.deployment.deployer.settings")
    def test_prod_blocked_when_review_required(self, mock_settings, tmp_path):
        from pbi_developer.deployment.deployer import deploy_report

        mock_settings.pipeline.require_human_review = True
        mock_settings.powerbi.workspace_id = "ws-123"

        result = deploy_report(tmp_path, stage="prod")
        assert not result.success
        assert "human review is required" in result.error

    @patch("pbi_developer.deployment.deployer.settings")
    def test_dev_not_blocked(self, mock_settings, tmp_path):
        from pbi_developer.deployment.deployer import deploy_report

        mock_settings.pipeline.require_human_review = True
        mock_settings.powerbi.workspace_id = "ws-123"

        # Should proceed to deployment method (will fail at fabric-cicd import, that's fine)
        result = deploy_report(tmp_path, stage="dev")
        # It won't succeed (no fabric-cicd installed) but it shouldn't be blocked by review gate
        assert "human review" not in (result.error or "")


class TestDeployNoWorkspace:
    @patch("pbi_developer.deployment.deployer.settings")
    def test_missing_workspace(self, mock_settings, tmp_path):
        from pbi_developer.deployment.deployer import deploy_report

        mock_settings.powerbi.workspace_id = ""

        result = deploy_report(tmp_path)
        assert not result.success
        assert "No workspace ID" in result.error
