"""Authentication helpers for Power BI and Snowflake.

Uses MSAL for Azure AD / Entra ID service principal authentication.
"""

from __future__ import annotations

from typing import Any

from pbi_developer.config import settings
from pbi_developer.exceptions import ConnectionError as PBIConnectionError
from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


def get_powerbi_token() -> str:
    """Get an access token for Power BI REST API using service principal."""
    import msal

    cfg = settings.powerbi
    if not all([cfg.tenant_id, cfg.client_id, cfg.client_secret]):
        raise PBIConnectionError(
            "Missing Azure credentials. Set AZURE_TENANT_ID, AZURE_CLIENT_ID, "
            "and AZURE_CLIENT_SECRET environment variables."
        )

    authority = f"https://login.microsoftonline.com/{cfg.tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id=cfg.client_id,
        client_credential=cfg.client_secret,
        authority=authority,
    )

    result = app.acquire_token_for_client(scopes=[cfg.scope])
    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "Unknown error"))
        raise PBIConnectionError(f"Failed to acquire Power BI token: {error}")

    logger.info("Power BI access token acquired")
    return result["access_token"]


def get_snowflake_connection() -> Any:
    """Get a Snowflake connection using configured credentials."""
    import snowflake.connector

    cfg = settings.snowflake
    if not all([cfg.account, cfg.user, cfg.password]):
        raise PBIConnectionError(
            "Missing Snowflake credentials. Set SNOWFLAKE_ACCOUNT, "
            "SNOWFLAKE_USER, and SNOWFLAKE_PASSWORD environment variables."
        )

    conn = snowflake.connector.connect(
        account=cfg.account,
        user=cfg.user,
        password=cfg.password,
        warehouse=cfg.warehouse,
        database=cfg.database,
        schema=cfg.schema_name,
    )
    logger.info(f"Connected to Snowflake: {cfg.account}/{cfg.database}")
    return conn


def test_connection(target: str) -> tuple[bool, str]:
    """Test connectivity to a target system.

    Args:
        target: "powerbi", "snowflake", or "xmla"

    Returns:
        (success, message) tuple.
    """
    if target == "powerbi":
        try:
            get_powerbi_token()
            return True, "Power BI authentication successful"
        except Exception as e:
            return False, f"Power BI auth failed: {e}"

    elif target == "snowflake":
        try:
            conn = get_snowflake_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT CURRENT_VERSION()")
            version = cursor.fetchone()[0]
            conn.close()
            return True, f"Snowflake connected (version {version})"
        except Exception as e:
            return False, f"Snowflake connection failed: {e}"

    elif target == "xmla":
        return False, "XMLA endpoint testing not yet implemented (requires adomdclient or ssas_api)"

    else:
        return False, f"Unknown target: {target}. Use: powerbi, snowflake, or xmla"
