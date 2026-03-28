"""File-based prompt registry with content-hash versioning.

Loads system prompts and output schemas from YAML files, one per agent.
Tracks prompt versions by SHA-256 content hash for audit and debugging.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_PROMPTS_DIR = Path(__file__).parent


@dataclass
class PromptEntry:
    """A loaded prompt with metadata."""

    agent_name: str
    system_prompt: str
    output_schema: dict[str, Any] | None = None
    template_vars: list[str] = field(default_factory=list)
    content_hash: str = ""
    version_label: str = "1.0"
    source_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = _compute_hash(self.system_prompt, self.output_schema)


def _compute_hash(prompt: str, schema: dict[str, Any] | None) -> str:
    """Compute SHA-256 hash of prompt + canonical JSON of schema."""
    content = prompt
    if schema:
        content += json.dumps(schema, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class PromptRegistry:
    """File-based prompt registry with content-hash versioning.

    Scans a directory for *.yaml files, each containing an agent's
    system prompt, output schema, and metadata.
    """

    def __init__(self, prompts_dir: Path | None = None):
        self._prompts_dir = prompts_dir or _DEFAULT_PROMPTS_DIR
        self._entries: dict[str, PromptEntry] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Scan prompts directory and load all YAML files."""
        if not self._prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {self._prompts_dir}")
            return

        for yaml_path in sorted(self._prompts_dir.glob("*.yaml")):
            try:
                self._load_file(yaml_path)
            except Exception as e:
                logger.warning(f"Failed to load prompt file {yaml_path.name}: {e}")

        if self._entries:
            logger.info(f"Loaded {len(self._entries)} prompt(s) from {self._prompts_dir}")

    def _load_file(self, path: Path) -> None:
        """Load a single YAML prompt file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        if not data or not isinstance(data, dict):
            return

        agent_name = data.get("agent", path.stem)
        entry = PromptEntry(
            agent_name=agent_name,
            system_prompt=data.get("system_prompt", ""),
            output_schema=data.get("output_schema"),
            template_vars=data.get("template_vars", []),
            version_label=data.get("version_label", "1.0"),
            source_path=path,
        )
        self._entries[agent_name] = entry

    def get(self, agent_name: str) -> PromptEntry:
        """Get a prompt entry by agent name.

        Raises KeyError if agent not found.
        """
        if agent_name not in self._entries:
            raise KeyError(
                f"No prompt registered for agent '{agent_name}'. Available: {', '.join(sorted(self._entries.keys()))}"
            )
        return self._entries[agent_name]

    def get_rendered(self, agent_name: str, **template_kwargs: Any) -> str:
        """Get system prompt with template variables filled in.

        Uses Python str.format() for variable substitution.
        """
        entry = self.get(agent_name)
        if template_kwargs:
            return entry.system_prompt.format(**template_kwargs)
        return entry.system_prompt

    def get_schema(self, agent_name: str) -> dict[str, Any] | None:
        """Get the output schema for an agent, or None if not defined."""
        entry = self.get(agent_name)
        return entry.output_schema

    def versions(self) -> dict[str, str]:
        """Return a mapping of agent_name -> content_hash for all loaded prompts."""
        return {name: entry.content_hash for name, entry in self._entries.items()}

    def has(self, agent_name: str) -> bool:
        """Check if a prompt is registered for the given agent."""
        return agent_name in self._entries

    @property
    def agents(self) -> list[str]:
        """List all registered agent names."""
        return sorted(self._entries.keys())


# Module-level singleton
registry = PromptRegistry()
