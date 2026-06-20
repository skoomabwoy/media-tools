"""Tiny JSON-backed local config (device choice, cached device list, …)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "media-tools" / "config.json"


def load() -> dict[str, Any]:
    try:
        data = json.loads(config_path().read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(data: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def update(**changes: Any) -> dict[str, Any]:
    """Merge `changes` into the stored config and persist. Returns the new config."""
    data = load()
    data.update(changes)
    save(data)
    return data
