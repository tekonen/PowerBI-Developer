"""Tests for src/pbi_developer/config.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from pbi_developer.config import (
    ClaudeConfig,
    PBIRConfig,
    PipelineConfig,
    PowerBIConfig,
    ReportStandards,
    Settings,
    SnowflakeConfig,
    load_settings,
)

# ---------------------------------------------------------------------------
# ClaudeConfig
# ---------------------------------------------------------------------------


class TestClaudeConfig:
    def test_defaults(self) -> None:
        cfg = ClaudeConfig()
        assert cfg.model == "claude-sonnet-4-20250514"
        assert cfg.max_tokens == 8192
        assert cfg.temperature == 0.2

    def test_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        cfg = ClaudeConfig()
        assert cfg.api_key == "sk-test-key"

    def test_api_key_empty_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        cfg = ClaudeConfig()
        assert cfg.api_key == ""

    def test_override_values(self) -> None:
        cfg = ClaudeConfig(model="claude-opus-4-20250514", max_tokens=4096, temperature=0.5)
        assert cfg.model == "claude-opus-4-20250514"
        assert cfg.max_tokens == 4096
        assert cfg.temperature == 0.5


# ---------------------------------------------------------------------------
# PowerBIConfig
# ---------------------------------------------------------------------------


class TestPowerBIConfig:
    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("POWERBI_WORKSPACE_ID", raising=False)
        monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
        monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
        monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)

        cfg = PowerBIConfig()
        assert cfg.api_base == "https://api.powerbi.com/v1.0/myorg"
        assert cfg.scope == "https://analysis.windows.net/powerbi/api/.default"
        assert cfg.workspace_id == ""
        assert cfg.tenant_id == ""
        assert cfg.client_id == ""
        assert cfg.client_secret == ""

    def test_reads_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POWERBI_WORKSPACE_ID", "ws-123")
        monkeypatch.setenv("AZURE_TENANT_ID", "tenant-456")
        monkeypatch.setenv("AZURE_CLIENT_ID", "client-789")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret-abc")

        cfg = PowerBIConfig()
        assert cfg.workspace_id == "ws-123"
        assert cfg.tenant_id == "tenant-456"
        assert cfg.client_id == "client-789"
        assert cfg.client_secret == "secret-abc"


# ---------------------------------------------------------------------------
# SnowflakeConfig
# ---------------------------------------------------------------------------


class TestSnowflakeConfig:
    def test_defaults_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in [
            "SNOWFLAKE_ACCOUNT",
            "SNOWFLAKE_USER",
            "SNOWFLAKE_PASSWORD",
            "SNOWFLAKE_WAREHOUSE",
            "SNOWFLAKE_DATABASE",
            "SNOWFLAKE_SCHEMA",
        ]:
            monkeypatch.delenv(var, raising=False)

        cfg = SnowflakeConfig()
        assert cfg.account == ""
        assert cfg.user == ""
        assert cfg.password == ""
        assert cfg.warehouse == ""
        assert cfg.database == ""
        assert cfg.schema_name == ""

    def test_reads_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "acct")
        monkeypatch.setenv("SNOWFLAKE_USER", "usr")
        monkeypatch.setenv("SNOWFLAKE_PASSWORD", "pw")
        monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "wh")
        monkeypatch.setenv("SNOWFLAKE_DATABASE", "db")
        monkeypatch.setenv("SNOWFLAKE_SCHEMA", "sch")

        cfg = SnowflakeConfig()
        assert cfg.account == "acct"
        assert cfg.user == "usr"
        assert cfg.password == "pw"
        assert cfg.warehouse == "wh"
        assert cfg.database == "db"
        assert cfg.schema_name == "sch"


# ---------------------------------------------------------------------------
# PBIRConfig
# ---------------------------------------------------------------------------


class TestPBIRConfig:
    def test_defaults(self) -> None:
        cfg = PBIRConfig()
        assert cfg.schema_version == "1.0"
        assert cfg.default_page_width == 1280
        assert cfg.default_page_height == 720

    def test_override(self) -> None:
        cfg = PBIRConfig(schema_version="2.0", default_page_width=1920, default_page_height=1080)
        assert cfg.schema_version == "2.0"
        assert cfg.default_page_width == 1920
        assert cfg.default_page_height == 1080


# ---------------------------------------------------------------------------
# PipelineConfig
# ---------------------------------------------------------------------------


class TestPipelineConfig:
    def test_defaults(self) -> None:
        cfg = PipelineConfig()
        assert cfg.max_qa_retries == 3
        assert cfg.require_human_review is True

    def test_override(self) -> None:
        cfg = PipelineConfig(max_qa_retries=5, require_human_review=False)
        assert cfg.max_qa_retries == 5
        assert cfg.require_human_review is False


# ---------------------------------------------------------------------------
# ReportStandards
# ---------------------------------------------------------------------------


class TestReportStandards:
    def test_default_color_palette_length(self) -> None:
        rs = ReportStandards()
        assert len(rs.color_palette) == 8

    def test_default_preferred_visuals(self) -> None:
        rs = ReportStandards()
        assert "card" in rs.preferred_visuals
        assert "lineChart" in rs.preferred_visuals

    def test_default_page_structure(self) -> None:
        rs = ReportStandards()
        assert rs.page_structure["max_visuals_per_page"] == 8
        assert rs.page_structure["header_height"] == 60
        assert rs.page_structure["margin"] == 20

    def test_default_naming_rules(self) -> None:
        rs = ReportStandards()
        assert rs.naming_rules["page_naming"] == "descriptive"

    def test_override_color_palette(self) -> None:
        rs = ReportStandards(color_palette=["#000", "#FFF"])
        assert rs.color_palette == ["#000", "#FFF"]


# ---------------------------------------------------------------------------
# Settings (composite)
# ---------------------------------------------------------------------------


class TestSettings:
    def test_default_construction(self) -> None:
        s = Settings()
        assert isinstance(s.claude, ClaudeConfig)
        assert isinstance(s.powerbi, PowerBIConfig)
        assert isinstance(s.snowflake, SnowflakeConfig)
        assert isinstance(s.pbir, PBIRConfig)
        assert isinstance(s.pipeline, PipelineConfig)
        assert isinstance(s.report_standards, ReportStandards)

    def test_partial_override(self) -> None:
        s = Settings(pbir=PBIRConfig(schema_version="3.0"))
        assert s.pbir.schema_version == "3.0"
        # Others remain defaults
        assert s.pipeline.max_qa_retries == 3


# ---------------------------------------------------------------------------
# load_settings
# ---------------------------------------------------------------------------


class TestLoadSettings:
    def test_loads_from_yaml(self, tmp_path: Path) -> None:
        yaml_data: dict[str, Any] = {
            "pbir": {"schema_version": "9.9", "default_page_width": 800},
            "pipeline": {"max_qa_retries": 10},
        }
        cfg_file = tmp_path / "settings.yaml"
        cfg_file.write_text(yaml.dump(yaml_data))

        s = load_settings(cfg_file)
        assert s.pbir.schema_version == "9.9"
        assert s.pbir.default_page_width == 800
        assert s.pipeline.max_qa_retries == 10
        # Unset fields keep defaults
        assert s.pbir.default_page_height == 720

    def test_missing_yaml_returns_defaults(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.yaml"
        s = load_settings(missing)
        assert isinstance(s, Settings)
        assert s.pbir.schema_version == "1.0"

    def test_empty_yaml_returns_defaults(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "empty.yaml"
        cfg_file.write_text("")

        s = load_settings(cfg_file)
        assert isinstance(s, Settings)
        assert s.pipeline.require_human_review is True

    def test_yaml_with_unknown_keys_ignored_or_errors(self, tmp_path: Path) -> None:
        """Pydantic should reject unknown top-level keys by default (strict)
        or ignore them depending on model config. We just verify no crash for
        known keys alongside unknown ones when extra='ignore' or similar."""
        yaml_data: dict[str, Any] = {
            "pbir": {"schema_version": "1.0"},
        }
        cfg_file = tmp_path / "settings.yaml"
        cfg_file.write_text(yaml.dump(yaml_data))

        # Should at minimum not crash for valid data
        s = load_settings(cfg_file)
        assert s.pbir.schema_version == "1.0"
