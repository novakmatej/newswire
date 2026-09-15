"""State in a local JSON file: option ``path``. Good for local runs and Docker volumes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from newswire.config import ConfigError, StateConfig
from newswire.registry import state_backend
from newswire.state.base import StateError


@state_backend("local_file")
class LocalFileStateBackend:
    def __init__(self, cfg: StateConfig):
        path = cfg.options.get("path")
        if not path:
            raise ConfigError("state: local_file requires option 'path'")
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            content = self.path.read_text(encoding="utf-8")
            return json.loads(content) if content.strip() else {}
        except (OSError, json.JSONDecodeError) as exc:
            raise StateError(f"Failed to read state from {self.path}: {exc}") from exc

    def save(self, state: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except OSError as exc:
            raise StateError(f"Failed to write state to {self.path}: {exc}") from exc
