"""Factory for choosing between file-based and Supabase-backed run stores."""

from __future__ import annotations

from pbi_developer.web.run_store import RunStore


def get_store(user_id: str | None = None) -> RunStore:
    """Return the appropriate store backend.

    When Supabase is configured and a user_id is provided, returns a
    SupabaseRunStore scoped to that user. Otherwise returns the
    file-based RunStore for local/CLI mode.
    """
    from pbi_developer.web.supabase_client import is_supabase_configured

    if is_supabase_configured() and user_id:
        from pbi_developer.web.supabase_run_store import SupabaseRunStore

        return SupabaseRunStore(user_id)  # type: ignore[return-value]

    return RunStore()
