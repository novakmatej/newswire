"""Shared stub HTTP response for mocked requests."""

from __future__ import annotations

from typing import Any

from requests import HTTPError


class StubResponse:
    def __init__(self, status_code: int = 200, content: bytes = b"", json_data: Any = None):
        self.status_code = status_code
        self.content = content
        self._json = json_data

    def json(self) -> Any:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPError(f"HTTP error {self.status_code}")
