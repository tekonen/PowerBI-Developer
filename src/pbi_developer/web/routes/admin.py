"""Admin API routes for managing users, runs, prompts, and configuration."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/admin")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SECRET_FIELDS = frozenset({
    "api_key", "client_secret", "password",
})


def _mask(value: str) -> str:
    """Mask a secret, showing only the last 4 characters."""
    if not value or len(value) <= 4:
        return "***"
    return f"***{value[-4:]}"


def _require_admin(request: Request) -> JSONResponse | None:
    """Return a 403 JSONResponse if the caller is not an admin, else ``None``.

    In local mode (no Supabase / no auth middleware), access is allowed.
    """
    from pbi_developer.web.auth import get_current_user_id, is_user_admin

    user_id = get_current_user_id(request)
    if user_id is None:
        # Local mode -- no auth middleware attached; allow access.
        from pbi_developer.web.supabase_client import is_supabase_configured

        if not is_supabase_configured():
            return None
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    if not is_user_admin(user_id):
        return JSONResponse({"error": "Admin access required"}, status_code=403)
    return None


def _settings_to_dict_masked() -> dict[str, Any]:
    """Serialize current settings with secrets masked."""
    from pbi_developer.config import settings

    data = settings.model_dump()
    for section in data.values():
        if not isinstance(section, dict):
            continue
        for key, value in section.items():
            if key in _SECRET_FIELDS and isinstance(value, str) and value:
                section[key] = _mask(value)
    return data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/users")
async def list_users(request: Request):
    """List all users with stats."""
    denied = _require_admin(request)
    if denied:
        return denied

    try:
        from pbi_developer.web.admin_service import list_users as _list_users

        users = _list_users()
    except ImportError:
        # admin_service not yet available -- return empty list
        users = []
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return {"users": users}


@router.get("/users/stats")
async def get_user_stats(request: Request):
    """Aggregate user / run statistics."""
    denied = _require_admin(request)
    if denied:
        return denied

    try:
        from pbi_developer.web.admin_service import get_user_stats as _get_user_stats

        stats = _get_user_stats()
    except ImportError:
        stats = {"total_users": 0, "total_runs": 0}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return stats


@router.get("/runs")
async def list_all_runs(request: Request, limit: int = 50, offset: int = 0):
    """List all runs (paginated)."""
    denied = _require_admin(request)
    if denied:
        return denied

    try:
        from pbi_developer.web.admin_service import list_all_runs as _list_all_runs

        runs = _list_all_runs(limit=limit, offset=offset)
    except ImportError:
        # Fallback: use local RunStore
        try:
            from pbi_developer.web.run_store import RunStore

            store = RunStore()
            all_runs = store.list_runs()
            page = all_runs[offset : offset + limit]
            runs = [r.model_dump(mode="json") for r in page]
        except Exception:
            runs = []
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return {"runs": runs, "limit": limit, "offset": offset}


@router.get("/prompts")
async def get_system_prompts(request: Request):
    """List all system prompts with metadata."""
    denied = _require_admin(request)
    if denied:
        return denied

    try:
        from pbi_developer.web.admin_service import (
            get_system_prompts as _get_system_prompts,
        )

        prompts = _get_system_prompts()
    except ImportError:
        # Fallback: read from PromptRegistry if available
        try:
            from pbi_developer.prompts.registry import PromptRegistry

            reg = PromptRegistry()
            prompts = []
            for name in reg.agents:
                entry = reg.get(name)
                prompts.append({
                    "agent_name": entry.agent_name,
                    "version_label": entry.version_label,
                    "content_hash": entry.content_hash,
                    "template_vars": entry.template_vars,
                    "preview": entry.system_prompt[:200],
                    "full_prompt": entry.system_prompt,
                })
        except ImportError:
            prompts = []
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return {"prompts": prompts}


@router.put("/prompts/{agent_name}")
async def update_system_prompt(agent_name: str, request: Request):
    """Update a system prompt's text."""
    denied = _require_admin(request)
    if denied:
        return denied

    try:
        body = await request.json()
        new_prompt: str = body.get("system_prompt", "")
        if not new_prompt:
            return JSONResponse(
                {"error": "system_prompt is required"}, status_code=400
            )
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    try:
        from pbi_developer.web.admin_service import (
            update_system_prompt as _update_system_prompt,
        )

        _update_system_prompt(agent_name, new_prompt)
    except ImportError:
        # Fallback: write via PromptRegistry + YAML
        try:
            import yaml

            from pbi_developer.prompts.registry import PromptRegistry

            reg = PromptRegistry()
            entry = reg.get(agent_name)
            if entry is None:
                return JSONResponse(
                    {"error": f"Agent '{agent_name}' not found"}, status_code=404
                )
            path = entry.source_path
            data = yaml.safe_load(path.read_text())
            data["system_prompt"] = new_prompt
            path.write_text(
                yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
            )
        except ImportError:
            return JSONResponse(
                {"error": "Prompt management not available"}, status_code=501
            )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return {"success": True, "agent_name": agent_name}


@router.get("/config")
async def get_global_config(request: Request):
    """Get global configuration (secrets masked)."""
    denied = _require_admin(request)
    if denied:
        return denied

    try:
        config = _settings_to_dict_masked()
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return {"config": config}


@router.put("/config")
async def update_global_config(request: Request):
    """Update global configuration."""
    denied = _require_admin(request)
    if denied:
        return denied

    try:
        updates: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    try:
        from pbi_developer.web.admin_service import (
            update_global_config as _update_global_config,
        )

        _update_global_config(updates)
    except ImportError:
        # Fallback: merge into settings.yaml
        try:
            import yaml

            from pbi_developer.config import _DEFAULT_SETTINGS_PATH

            path = _DEFAULT_SETTINGS_PATH
            existing: dict[str, Any] = {}
            if path.exists():
                existing = yaml.safe_load(path.read_text()) or {}

            # Shallow-merge each section
            for section, values in updates.items():
                if isinstance(values, dict):
                    existing.setdefault(section, {}).update(values)
                else:
                    existing[section] = values

            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                yaml.dump(existing, default_flow_style=False, allow_unicode=True, sort_keys=False)
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return {"success": True}
