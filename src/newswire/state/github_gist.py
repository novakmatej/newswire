"""State in a GitHub Gist: one JSON file, options gist_id, token, filename."""

from __future__ import annotations

import json
from typing import Any

import requests

from newswire.config import ConfigError, StateConfig
from newswire.registry import state_backend
from newswire.state.base import StateError


@state_backend("github_gist")
class GistStateBackend:
    def __init__(self, cfg: StateConfig):
        options = cfg.options
        self.gist_id = options.get("gist_id")
        if not self.gist_id:
            raise ConfigError("state: github_gist requires option 'gist_id'")
        self.token = options.get("token")
        if not self.token:
            raise ConfigError("state: github_gist requires option 'token'")
        self.filename = options.get("filename", "state.json")
        self.timeout = float(options.get("timeout", 10))

    @property
    def _url(self) -> str:
        return f"https://api.github.com/gists/{self.gist_id}"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def load(self) -> dict[str, Any]:
        try:
            response = requests.get(self._url, headers=self._headers, timeout=self.timeout)
            response.raise_for_status()

            files = response.json().get("files", {})
            if not files:
                return {}

            # Prefer the configured filename; fall back to the first file so a
            # gist created under another name keeps working.
            first_file = files.get(self.filename) or next(iter(files.values()))
            content = first_file.get("content", "{}")
            return json.loads(content) if content else {}

        except requests.RequestException as exc:
            raise StateError(f"Failed to fetch state from Gist: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise StateError(f"Failed to parse state JSON: {exc}") from exc

    def save(self, state: dict[str, Any]) -> None:
        payload = {"files": {self.filename: {"content": json.dumps(state, indent=2)}}}
        try:
            response = requests.patch(
                self._url, headers=self._headers, json=payload, timeout=self.timeout
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise StateError(f"Failed to update state in Gist: {exc}") from exc
