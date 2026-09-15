"""Shared test helpers: stub HTTP responses and config factories."""

from __future__ import annotations

from typing import Any

import pytest
from requests import HTTPError

from newswire.config import DigestConfig, NotifierConfig, SourceConfig


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


@pytest.fixture
def source_cfg():
    def make(source_id: str = "src", type_: str = "test", **kwargs: Any) -> SourceConfig:
        options = kwargs.pop("options", {})
        return SourceConfig(id=source_id, type=type_, options=options, **kwargs)

    return make


@pytest.fixture
def notifier_cfg():
    def make(notifier_id: str = "chan", type_: str = "test", **kwargs: Any) -> NotifierConfig:
        options = kwargs.pop("options", {})
        return NotifierConfig(id=notifier_id, type=type_, options=options, **kwargs)

    return make


@pytest.fixture
def digest_cfg() -> DigestConfig:
    return DigestConfig(title="dbt News", intro="Hey dbt builders! 👋 Here's what's happening:")
