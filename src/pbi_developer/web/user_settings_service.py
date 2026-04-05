"""User settings CRUD service for Supabase.

Manages per-user configuration stored in the user_settings table.
Sensitive fields (API keys, passwords) are encrypted at rest using
pgp_sym_encrypt with a server-side encryption key.
"""

from __future__ import annotations

from typing import Any


def _client():
    from pbi_developer.web.supabase_client import get_service_client

    client = get_service_client()
    if not client:
        raise RuntimeError("Supabase service client not configured")
    return client


def _encryption_key() -> str:
    from pbi_developer.web.supabase_client import get_encryption_key

    return get_encryption_key()


def _encrypt(value: str) -> str | None:
    """Encrypt a value using the Supabase RPC function."""
    if not value:
        return None
    resp = _client().rpc("encrypt_value", {"plain_text": value, "encryption_key": _encryption_key()}).execute()
    return resp.data


def _decrypt(cipher_text: str | None) -> str:
    """Decrypt a value using the Supabase RPC function."""
    if not cipher_text:
        return ""
    resp = _client().rpc("decrypt_value", {"cipher_text": cipher_text, "encryption_key": _encryption_key()}).execute()
    return resp.data or ""


def get_user_settings(user_id: str) -> dict[str, Any] | None:
    """Fetch user settings, decrypting sensitive fields."""
    resp = _client().table("user_settings").select("*").eq("user_id", user_id).execute()
    if not resp.data:
        return None

    row = resp.data[0]
    # Decrypt sensitive fields
    decrypted = dict(row)
    for field in [
        "claude_api_key_encrypted",
        "pbi_tenant_id_encrypted",
        "pbi_client_id_encrypted",
        "pbi_client_secret_encrypted",
        "sf_account_encrypted",
        "sf_user_encrypted",
        "sf_password_encrypted",
    ]:
        if row.get(field):
            plain_key = field.replace("_encrypted", "")
            decrypted[plain_key] = _decrypt(row[field])
        else:
            plain_key = field.replace("_encrypted", "")
            decrypted[plain_key] = ""
    return decrypted


def save_onboarding_step(user_id: str, step: int, data: dict[str, Any]) -> None:
    """Save data for a specific onboarding step.

    Step 1: Claude/AI settings
    Step 2: Power BI credentials
    Step 3: Snowflake credentials
    Step 4: Report style preferences
    """
    # Ensure a row exists
    existing = _client().table("user_settings").select("id").eq("user_id", user_id).execute()
    if not existing.data:
        _client().table("user_settings").insert({"user_id": user_id}).execute()

    updates: dict[str, Any] = {}

    if step == 1:
        if data.get("claude_api_key"):
            updates["claude_api_key_encrypted"] = _encrypt(data["claude_api_key"])
        updates["claude_base_url"] = data.get("claude_base_url", "")
        updates["claude_model"] = data.get("claude_model", "claude-sonnet-4-20250514")
        updates["claude_max_tokens"] = data.get("claude_max_tokens", 8192)
        updates["claude_temperature"] = data.get("claude_temperature", 0.2)

    elif step == 2:
        if data.get("pbi_tenant_id"):
            updates["pbi_tenant_id_encrypted"] = _encrypt(data["pbi_tenant_id"])
        if data.get("pbi_client_id"):
            updates["pbi_client_id_encrypted"] = _encrypt(data["pbi_client_id"])
        if data.get("pbi_client_secret"):
            updates["pbi_client_secret_encrypted"] = _encrypt(data["pbi_client_secret"])
        updates["pbi_workspace_id"] = data.get("pbi_workspace_id", "")

    elif step == 3:
        if data.get("sf_account"):
            updates["sf_account_encrypted"] = _encrypt(data["sf_account"])
        if data.get("sf_user"):
            updates["sf_user_encrypted"] = _encrypt(data["sf_user"])
        if data.get("sf_password"):
            updates["sf_password_encrypted"] = _encrypt(data["sf_password"])
        updates["sf_warehouse"] = data.get("sf_warehouse", "")
        updates["sf_database"] = data.get("sf_database", "")
        updates["sf_schema"] = data.get("sf_schema", "")

    elif step == 4:
        updates["color_palette"] = data.get("color_palette")
        updates["preferred_visuals"] = data.get("preferred_visuals")
        updates["page_width"] = data.get("page_width", 1280)
        updates["page_height"] = data.get("page_height", 720)
        updates["max_visuals_per_page"] = data.get("max_visuals_per_page", 8)

    if updates:
        _client().table("user_settings").update(updates).eq("user_id", user_id).execute()


def complete_onboarding(user_id: str) -> None:
    """Mark onboarding as completed for a user."""
    _client().table("user_settings").update({"onboarding_completed": True}).eq("user_id", user_id).execute()


def has_completed_onboarding(user_id: str) -> bool:
    """Check if a user has completed onboarding."""
    resp = _client().table("user_settings").select("onboarding_completed").eq("user_id", user_id).execute()
    if not resp.data:
        return False
    return bool(resp.data[0].get("onboarding_completed"))


def build_settings_for_user(user_id: str):
    """Build a Settings object merging user-specific overrides with global defaults.

    Returns a new Settings instance with user credentials applied.
    """
    from pbi_developer.config import Settings, load_settings

    base = load_settings()
    user_cfg = get_user_settings(user_id)
    if not user_cfg:
        return base

    overrides: dict[str, Any] = {}

    # Claude overrides
    claude_overrides: dict[str, Any] = {}
    if user_cfg.get("claude_api_key"):
        claude_overrides["api_key"] = user_cfg["claude_api_key"]
    if user_cfg.get("claude_base_url"):
        claude_overrides["base_url"] = user_cfg["claude_base_url"]
    if user_cfg.get("claude_model"):
        claude_overrides["model"] = user_cfg["claude_model"]
    if user_cfg.get("claude_max_tokens"):
        claude_overrides["max_tokens"] = user_cfg["claude_max_tokens"]
    if user_cfg.get("claude_temperature") is not None:
        claude_overrides["temperature"] = float(user_cfg["claude_temperature"])
    if claude_overrides:
        overrides["claude"] = {**base.claude.model_dump(), **claude_overrides}

    # Power BI overrides
    pbi_overrides: dict[str, Any] = {}
    if user_cfg.get("pbi_tenant_id"):
        pbi_overrides["tenant_id"] = user_cfg["pbi_tenant_id"]
    if user_cfg.get("pbi_client_id"):
        pbi_overrides["client_id"] = user_cfg["pbi_client_id"]
    if user_cfg.get("pbi_client_secret"):
        pbi_overrides["client_secret"] = user_cfg["pbi_client_secret"]
    if user_cfg.get("pbi_workspace_id"):
        pbi_overrides["workspace_id"] = user_cfg["pbi_workspace_id"]
    if pbi_overrides:
        overrides["powerbi"] = {**base.powerbi.model_dump(), **pbi_overrides}

    # Snowflake overrides
    sf_overrides: dict[str, Any] = {}
    if user_cfg.get("sf_account"):
        sf_overrides["account"] = user_cfg["sf_account"]
    if user_cfg.get("sf_user"):
        sf_overrides["user"] = user_cfg["sf_user"]
    if user_cfg.get("sf_password"):
        sf_overrides["password"] = user_cfg["sf_password"]
    if user_cfg.get("sf_warehouse"):
        sf_overrides["warehouse"] = user_cfg["sf_warehouse"]
    if user_cfg.get("sf_database"):
        sf_overrides["database"] = user_cfg["sf_database"]
    if user_cfg.get("sf_schema"):
        sf_overrides["schema_name"] = user_cfg["sf_schema"]
    if sf_overrides:
        overrides["snowflake"] = {**base.snowflake.model_dump(), **sf_overrides}

    # Report standards overrides
    rs_overrides: dict[str, Any] = {}
    if user_cfg.get("color_palette"):
        rs_overrides["color_palette"] = user_cfg["color_palette"]
    if user_cfg.get("preferred_visuals"):
        rs_overrides["preferred_visuals"] = user_cfg["preferred_visuals"]
    page_structure = dict(base.report_standards.page_structure)
    if user_cfg.get("max_visuals_per_page"):
        page_structure["max_visuals_per_page"] = user_cfg["max_visuals_per_page"]
    rs_overrides["page_structure"] = page_structure
    if rs_overrides:
        overrides["report_standards"] = {**base.report_standards.model_dump(), **rs_overrides}

    # PBIR page dimensions
    pbir_overrides: dict[str, Any] = {}
    if user_cfg.get("page_width"):
        pbir_overrides["default_page_width"] = user_cfg["page_width"]
    if user_cfg.get("page_height"):
        pbir_overrides["default_page_height"] = user_cfg["page_height"]
    if pbir_overrides:
        overrides["pbir"] = {**base.pbir.model_dump(), **pbir_overrides}

    return Settings(**{**base.model_dump(), **overrides})
