"""Tests for the pipeline promotion manager."""

from __future__ import annotations


class TestPromotionApprovalGate:
    """Test that production promotion is blocked when approval is required."""

    def test_prod_promotion_blocked(self):
        from pbi_developer.deployment.pipeline_manager import promote

        result = promote("pipeline-123", "test", require_approval=True)
        assert not result.success
        assert "approval required" in result.error
        assert result.source_stage == "test"
        assert result.target_stage == "prod"

    def test_dev_to_test_not_blocked(self):
        from pbi_developer.deployment.pipeline_manager import promote

        # Will fail at PowerBIClient init (no credentials), but shouldn't be blocked by gate
        result = promote("pipeline-123", "dev", require_approval=True)
        # Either succeeds or fails for a reason other than approval
        assert "approval required" not in (result.error or "")

    def test_invalid_stage(self):
        from pbi_developer.deployment.pipeline_manager import promote

        result = promote("pipeline-123", "invalid")
        assert not result.success
        assert "Invalid stage" in result.error

    def test_cannot_promote_from_prod(self):
        from pbi_developer.deployment.pipeline_manager import promote

        result = promote("pipeline-123", "prod")
        assert not result.success
        assert "already at final stage" in result.error
