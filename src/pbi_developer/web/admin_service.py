"""Admin service for managing users, runs, prompts, and global configuration.

Provides admin-only operations that bypass RLS via the Supabase service client.
All functions assume the caller has already verified admin status.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Lazy imports — avoid circular dependencies and hard failures when optional
# packages are missing.
# ---------------------------------------------------------------------------


_service_client: Any = None


def _get_service_client() -> Any:
    """Return the Supabase service-role client (bypasses RLS).

    The client is created once and cached for the lifetime of the process.
    """
    global _service_client
    if _service_client is not None:
        return _service_client

    import os

    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    _service_client = create_client(url, key)
    return _service_client


def _get_settings_path() -> Path:
    """Return the path to the global settings.yaml file."""
    return Path(__file__).resolve().parent.parent.parent.parent / "config" / "settings.yaml"


def _content_hash(text: str) -> str:
    """Return a short SHA-256 hex digest of *text*."""
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _mask(value: str) -> str:
    """Mask a secret, showing only the last 4 characters."""
    if not value or len(value) <= 4:
        return "***"
    return f"***{value[-4:]}"


# ---------------------------------------------------------------------------
# Secret field names — these are never returned or updated in plain text via
# the admin API.
# ---------------------------------------------------------------------------

_SECRET_FIELDS = frozenset(
    {
        "api_key",
        "client_secret",
        "password",
    }
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_admin(user_id: str) -> bool:
    """Check whether *user_id* has ``is_admin=True`` in ``user_settings``.

    Uses the Supabase service client so the check itself is not subject to
    RLS.
    """
    client = _get_service_client()
    result = client.table("user_settings").select("is_admin").eq("user_id", user_id).limit(1).execute()
    if result.data:
        return bool(result.data[0].get("is_admin", False))
    return False


def list_users() -> list[dict[str, Any]]:
    """List all users with their settings and run counts.

    Returns a list of dicts with keys: ``user_id``, ``email``,
    ``onboarding``, ``is_admin``, ``created_at``, ``run_count``.
    """
    client = _get_service_client()

    # Fetch all user settings
    settings_result = (
        client.table("user_settings")
        .select("user_id, email, onboarding, is_admin, created_at")
        .order("created_at", desc=True)
        .execute()
    )

    # Fetch run counts per user
    runs_result = client.table("runs").select("user_id").execute()

    run_counts: dict[str, int] = {}
    for row in runs_result.data or []:
        uid = row["user_id"]
        run_counts[uid] = run_counts.get(uid, 0) + 1

    users: list[dict[str, Any]] = []
    for row in settings_result.data or []:
        uid = row["user_id"]
        users.append(
            {
                "user_id": uid,
                "email": row.get("email"),
                "onboarding": row.get("onboarding", False),
                "is_admin": row.get("is_admin", False),
                "created_at": row.get("created_at"),
                "run_count": run_counts.get(uid, 0),
            }
        )
    return users


def get_user_stats() -> dict[str, Any]:
    """Return aggregate statistics across all users.

    Keys: ``total_users``, ``total_runs``, ``runs_by_status``,
    ``total_tokens_used``.
    """
    client = _get_service_client()

    users_result = client.table("user_settings").select("id", count="exact").execute()
    total_users: int = users_result.count or 0

    runs_result = client.table("runs").select("status, tokens").execute()
    rows = runs_result.data or []

    total_runs = len(rows)
    runs_by_status: dict[str, int] = {}
    total_input_tokens = 0
    total_output_tokens = 0

    for row in rows:
        status = row.get("status", "unknown")
        runs_by_status[status] = runs_by_status.get(status, 0) + 1
        tokens = row.get("tokens") or {}
        total_input_tokens += tokens.get("input_tokens", 0)
        total_output_tokens += tokens.get("output_tokens", 0)

    return {
        "total_users": total_users,
        "total_runs": total_runs,
        "runs_by_status": runs_by_status,
        "total_tokens_used": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
        },
    }


def list_all_runs(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """Return all runs across all users, ordered by creation time (newest first).

    Supports pagination via *limit* and *offset*.
    """
    client = _get_service_client()
    result = client.table("runs").select("*").order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return result.data or []


def get_system_prompts() -> list[dict[str, Any]]:
    """Load all agent system prompts and return metadata for each.

    Each entry contains: ``agent_name``, ``version_label``,
    ``content_hash``, ``template_vars``, ``system_prompt`` (first 200 chars).

    Falls back to inspecting ``BaseAgent`` subclasses when no
    ``PromptRegistry`` is available.
    """
    prompts: list[dict[str, Any]] = []

    try:
        from pbi_developer.prompts.registry import registry  # type: ignore[import-untyped]

        for entry in registry.all():
            prompt_text = entry.get("system_prompt", "")
            prompts.append(
                {
                    "agent_name": entry.get("agent_name", "unknown"),
                    "version_label": entry.get("version_label", "latest"),
                    "content_hash": _content_hash(prompt_text),
                    "template_vars": entry.get("template_vars", []),
                    "system_prompt": prompt_text[:200],
                }
            )
        return prompts
    except (ImportError, AttributeError):
        pass

    # Fallback: discover prompts from BaseAgent subclasses
    from pbi_developer.agents.base import BaseAgent

    for cls in BaseAgent.__subclasses__():
        prompt_text = cls.system_prompt
        prompts.append(
            {
                "agent_name": cls.agent_name,
                "version_label": "latest",
                "content_hash": _content_hash(prompt_text),
                "template_vars": [],
                "system_prompt": prompt_text[:200],
            }
        )
    return prompts


def update_system_prompt(agent_name: str, new_prompt: str) -> dict[str, Any]:
    """Write an updated system prompt for *agent_name*.

    Attempts to persist via ``PromptRegistry``; falls back to updating the
    agent class attribute directly (in-memory only).

    Returns a dict with ``agent_name``, ``content_hash``, and ``persisted``
    (bool indicating whether the change was written to disk).
    """
    new_hash = _content_hash(new_prompt)

    # Try PromptRegistry first
    try:
        from pbi_developer.prompts.registry import registry  # type: ignore[import-untyped]

        registry.update(agent_name, new_prompt)
        return {
            "agent_name": agent_name,
            "content_hash": new_hash,
            "persisted": True,
        }
    except (ImportError, AttributeError):
        pass

    # Fallback: update the class attribute in-memory
    from pbi_developer.agents.base import BaseAgent

    for cls in BaseAgent.__subclasses__():
        if cls.agent_name == agent_name:
            cls.system_prompt = new_prompt
            return {
                "agent_name": agent_name,
                "content_hash": new_hash,
                "persisted": False,
            }

    raise ValueError(f"Unknown agent: {agent_name}")


def get_global_config() -> dict[str, Any]:
    """Read the current global configuration with secrets masked.

    Returns a nested dict mirroring ``config/settings.yaml`` but with
    sensitive values replaced by ``***<last-4-chars>``.
    """
    import yaml

    path = _get_settings_path()
    data: dict[str, Any] = {}
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}

    return _mask_secrets(data)


def update_global_config(updates: dict[str, Any]) -> dict[str, Any]:
    """Merge *updates* into ``config/settings.yaml``.

    Secret fields are ignored — they cannot be changed through this
    endpoint. Returns the new (masked) config.
    """
    import yaml

    path = _get_settings_path()

    current: dict[str, Any] = {}
    if path.exists():
        with open(path) as f:
            current = yaml.safe_load(f) or {}

    _deep_merge(current, updates, skip_secrets=True)

    with open(path, "w") as f:
        yaml.safe_dump(current, f, default_flow_style=False, sort_keys=False)

    return _mask_secrets(current)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _mask_secrets(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively mask values whose keys match ``_SECRET_FIELDS``."""
    masked: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            masked[key] = _mask_secrets(value)
        elif key in _SECRET_FIELDS and isinstance(value, str):
            masked[key] = _mask(value)
        else:
            masked[key] = value
    return masked


def _deep_merge(
    base: dict[str, Any],
    overrides: dict[str, Any],
    *,
    skip_secrets: bool = False,
) -> None:
    """Recursively merge *overrides* into *base* in place."""
    for key, value in overrides.items():
        if skip_secrets and key in _SECRET_FIELDS:
            continue
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value, skip_secrets=skip_secrets)
        else:
            base[key] = value
