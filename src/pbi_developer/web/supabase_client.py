"""Supabase client singleton.

When SUPABASE_URL is set, returns a configured Supabase client.
When not set, the app runs in local mode (JSON file storage, no auth).
"""

from __future__ import annotations

from functools import lru_cache


def _cfg():
    from pbi_developer.config import settings

    return settings.supabase


def is_supabase_configured() -> bool:
    """Return True if Supabase environment variables are set."""
    cfg = _cfg()
    return bool(cfg.url and cfg.anon_key)


@lru_cache(maxsize=1)
def get_supabase():
    """Return the Supabase client (anon key) or None if not configured."""
    if not is_supabase_configured():
        return None
    from supabase import create_client

    cfg = _cfg()
    return create_client(cfg.url, cfg.anon_key)


@lru_cache(maxsize=1)
def get_service_client():
    """Return a service-role Supabase client for server-side operations."""
    cfg = _cfg()
    if not (cfg.url and cfg.service_role_key):
        return None
    from supabase import create_client

    return create_client(cfg.url, cfg.service_role_key)


def get_encryption_key() -> str:
    """Return the encryption key for encrypting user credentials."""
    return _cfg().encryption_key
