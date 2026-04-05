"""FastAPI web application for the AI Power BI Developer tool.

This module assembles the app from focused route modules:
- routes/pages.py        — HTML page routes
- routes/api.py          — Core API routes (runs, deploy, validate, connect, etc.)
- routes/wizard.py       — Wizard step-by-step routes
- routes/versions.py     — Version control routes
- routes/auth_routes.py  — Login, register, OAuth callback, logout
- routes/onboarding.py   — New-user onboarding wizard
- routes/admin.py        — Admin API routes
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pbi_developer.web.auth import AuthMiddleware
from pbi_developer.web.routes import admin, api, auth_routes, onboarding, pages, versions, wizard
from pbi_developer.web.run_store import RunStore
from pbi_developer.web.version_control import VersionManager

# Store background task references to prevent garbage collection
_background_tasks: set[asyncio.Task] = set()

_WEB_DIR = Path(__file__).parent
_TEMPLATES_DIR = _WEB_DIR / "templates"
_STATIC_DIR = _WEB_DIR / "static"

app = FastAPI(title="AI Power BI Developer")
app.add_middleware(AuthMiddleware)

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

store = RunStore()
_versions_dir = store.base_dir / "dashboard-versions"
version_mgr = VersionManager(_versions_dir)

# Register route modules
app.include_router(auth_routes.router)
app.include_router(onboarding.router)
app.include_router(pages.router)
app.include_router(api.router)
app.include_router(wizard.router)
app.include_router(versions.router)
app.include_router(admin.router)


# ---------- Helpers ----------


def _auto_commit(message: str, run_id: str, output_path: Path | str) -> None:
    """Copy output to version-controlled dir and commit."""
    output = Path(output_path) if isinstance(output_path, str) else output_path
    if not output.exists():
        return

    # Copy output into the version-controlled directory
    dest = _versions_dir / output.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(output, dest)

    version_mgr.commit_version(message, run_id)
