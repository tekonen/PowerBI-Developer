"""File I/O helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, data: Any, indent: int = 2) -> None:
    """Write data as formatted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def read_json(path: Path) -> Any:
    """Read JSON file."""
    with open(path) as f:
        return json.load(f)


def ensure_dir(path: Path) -> Path:
    """Create directory if it doesn't exist, return the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path
