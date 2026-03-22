"""Tests for the CLI entry point."""

from __future__ import annotations

from typer.testing import CliRunner

from pbi_developer.cli import app

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})


class TestCLIBasics:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "AI-powered" in result.stdout

    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "pbi-dev" in result.stdout
        assert "0.1.0" in result.stdout

    def test_generate_no_inputs(self):
        result = runner.invoke(app, ["generate"])
        assert result.exit_code == 1
        assert "At least one input" in result.stdout

    def test_validate_missing_dir(self):
        result = runner.invoke(app, ["validate", "/nonexistent/path"])
        # Should fail because the directory doesn't exist
        assert result.exit_code != 0

    def test_validate_with_report(self, tmp_path):
        """Test validate against a minimal valid PBIR structure."""
        import json

        report_dir = tmp_path / "Test.Report"
        report_dir.mkdir()
        (report_dir / "definition.pbir").write_text(json.dumps({"$schema": "...", "version": "1.0"}))
        (report_dir / "report.json").write_text(json.dumps({"$schema": "...", "themeCollection": {}}))
        pages_dir = report_dir / "definition" / "pages"
        pages_dir.mkdir(parents=True)
        page_dir = pages_dir / "a1b2c3d4e5f6g7h8i9j0"
        page_dir.mkdir()
        (page_dir / "page.json").write_text(json.dumps({"$schema": "...", "name": "test", "displayName": "Test Page"}))

        result = runner.invoke(app, ["validate", str(report_dir)])
        assert result.exit_code == 0
        assert "Validation Results" in result.stdout

    def test_connect_unknown_target(self):
        result = runner.invoke(app, ["connect", "unknown"])
        assert result.exit_code == 1
        assert "Unknown target" in result.stdout

    def test_generate_command_exists(self):
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--brief" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--verbose" in result.stdout

    def test_wireframe_command_exists(self):
        result = runner.invoke(app, ["wireframe", "--help"])
        assert result.exit_code == 0
        assert "--brief" in result.stdout

    def test_deploy_command_exists(self):
        result = runner.invoke(app, ["deploy", "--help"])
        assert result.exit_code == 0
        assert "--stage" in result.stdout

    def test_rls_command_exists(self):
        result = runner.invoke(app, ["rls", "--help"])
        assert result.exit_code == 0
        assert "--requirements" in result.stdout

    def test_refine_command_exists(self):
        result = runner.invoke(app, ["refine", "--help"])
        assert result.exit_code == 0
        assert "--step" in result.stdout
        assert "--corrections" in result.stdout

    def test_refine_invalid_step(self, tmp_path):
        # Create artifacts dir so it passes the existence check
        (tmp_path / "artifacts").mkdir()
        result = runner.invoke(
            app, ["refine", "--step", "ingestion", "--corrections", "fix", "--output-dir", str(tmp_path)]
        )
        assert result.exit_code == 1
        assert "Invalid step" in result.stdout

    def test_refine_no_artifacts(self, tmp_path):
        result = runner.invoke(
            app, ["refine", "--step", "wireframe", "--corrections", "fix", "--output-dir", str(tmp_path)]
        )
        assert result.exit_code == 1
        assert "No artifacts found" in result.stdout
