"""Supabase client singleton.

When SUPABASE_URL is set, returns a configured Supabase client.
When not set, the app runs in local mode (JSON file storage, no auth).
"""

from __future__ import annotations

import os
from functools import lru_cache

_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
_SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ENCRYPTION_KEY = os.environ.get("SUPABASE_ENCRYPTION_KEY", "")


def is_supabase_configured() -> bool:
    """Return True if Supabase environment variables are set."""
    return bool(_SUPABASE_URL and _SUPABASE_ANON_KEY)


@lru_cache(maxsize=1)
def get_supabase():
    """Return the Supabase client (anon key) or None if not configured."""
    if not is_supabase_configured():
        return None
    from supabase import create_client

    return create_client(_SUPABASE_URL, _SUPABASE_ANON_KEY)


@lru_cache(maxsize=1)
def get_service_client():
    """Return a service-role Supabase client for server-side operations."""
    if not (_SUPABASE_URL and _SUPABASE_SERVICE_ROLE_KEY):
        return None
    from supabase import create_client

    return create_client(_SUPABASE_URL, _SUPABASE_SERVICE_ROLE_KEY)
