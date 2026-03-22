"""Configuration loader for environment variables and settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_SETTINGS_PATH = _PROJECT_ROOT / "config" / "settings.yaml"


class ClaudeConfig(BaseModel):
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192
    temperature: float = 0.2
    api_key: str = Field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))


class PowerBIConfig(BaseModel):
    api_base: str = "https://api.powerbi.com/v1.0/myorg"
    scope: str = "https://analysis.windows.net/powerbi/api/.default"
    workspace_id: str = Field(default_factory=lambda: os.environ.get("POWERBI_WORKSPACE_ID", ""))
    tenant_id: str = Field(default_factory=lambda: os.environ.get("AZURE_TENANT_ID", ""))
    client_id: str = Field(default_factory=lambda: os.environ.get("AZURE_CLIENT_ID", ""))
    client_secret: str = Field(default_factory=lambda: os.environ.get("AZURE_CLIENT_SECRET", ""))


class SnowflakeConfig(BaseModel):
    account: str = Field(default_factory=lambda: os.environ.get("SNOWFLAKE_ACCOUNT", ""))
    user: str = Field(default_factory=lambda: os.environ.get("SNOWFLAKE_USER", ""))
    password: str = Field(default_factory=lambda: os.environ.get("SNOWFLAKE_PASSWORD", ""))
    warehouse: str = Field(default_factory=lambda: os.environ.get("SNOWFLAKE_WAREHOUSE", ""))
    database: str = Field(default_factory=lambda: os.environ.get("SNOWFLAKE_DATABASE", ""))
    schema_name: str = Field(default_factory=lambda: os.environ.get("SNOWFLAKE_SCHEMA", ""))


class PBIRConfig(BaseModel):
    schema_version: str = "1.0"
    default_page_width: int = 1280
    default_page_height: int = 720


class PipelineConfig(BaseModel):
    max_qa_retries: int = 3
    require_human_review: bool = True


class ReportStandards(BaseModel):
    color_palette: list[str] = Field(
        default_factory=lambda: [
            "#118DFF",
            "#12239E",
            "#E66C37",
            "#6B007B",
            "#E044A7",
            "#744EC2",
            "#D9B300",
            "#D64550",
        ]
    )
    preferred_visuals: list[str] = Field(
        default_factory=lambda: [
            "card",
            "clusteredBarChart",
            "lineChart",
            "table",
            "slicer",
        ]
    )
    page_structure: dict[str, Any] = Field(
        default_factory=lambda: {
            "max_visuals_per_page": 8,
            "header_height": 60,
            "margin": 20,
        }
    )
    naming_rules: dict[str, str] = Field(
        default_factory=lambda: {
            "measures_prefix": "",
            "page_naming": "descriptive",
        }
    )


class Settings(BaseModel):
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    powerbi: PowerBIConfig = Field(default_factory=PowerBIConfig)
    snowflake: SnowflakeConfig = Field(default_factory=SnowflakeConfig)
    pbir: PBIRConfig = Field(default_factory=PBIRConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    report_standards: ReportStandards = Field(default_factory=ReportStandards)


def load_settings(settings_path: Path | None = None) -> Settings:
    """Load settings from YAML file merged with environment variables."""
    path = settings_path or _DEFAULT_SETTINGS_PATH
    data: dict[str, Any] = {}
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    return Settings(**data)


settings = load_settings()
