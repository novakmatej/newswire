"""State backends: github_gist (mocked) and local_file (tmp dir)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from requests import RequestException

from newswire.config import ConfigError, StateConfig
from newswire.state.base import StateError
from newswire.state.github_gist import GistStateBackend
from newswire.state.local_file import LocalFileStateBackend
from tests.helpers import StubResponse


def _gist_cfg(**options) -> StateConfig:
    return StateConfig(
        backend="github_gist",
        options={"gist_id": "gid", "token": "tok", "filename": "dbt-news-state.json", **options},
    )


def test_gist_load_prefers_configured_filename(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "files": {
            "other.json": {"content": json.dumps({"wrong": True})},
            "dbt-news-state.json": {
                "content": json.dumps({"dbt-core-releases": {"last_id": "v1"}})
            },
        }
    }
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured.update(url=url, headers=headers)
        return StubResponse(json_data=payload)

    monkeypatch.setattr("newswire.state.github_gist.requests.get", fake_get)

    state = GistStateBackend(_gist_cfg()).load()
    assert state == {"dbt-core-releases": {"last_id": "v1"}}
    assert captured["url"] == "https://api.github.com/gists/gid"
    assert captured["headers"]["Authorization"] == "token tok"


def test_gist_load_empty_gist_returns_empty_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "newswire.state.github_gist.requests.get",
        lambda *a, **k: StubResponse(json_data={"files": {}}),
    )
    assert GistStateBackend(_gist_cfg()).load() == {}


def test_gist_save_patches_configured_filename(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_patch(url, headers=None, json=None, timeout=None):
        captured.update(url=url, payload=json)
        return StubResponse(json_data={})

    monkeypatch.setattr("newswire.state.github_gist.requests.patch", fake_patch)

    GistStateBackend(_gist_cfg()).save({"key": {"cursor": "v2"}})
    files = captured["payload"]["files"]
    assert list(files) == ["dbt-news-state.json"]
    assert "v2" in files["dbt-news-state.json"]["content"]


def test_gist_errors_wrap_as_state_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "newswire.state.github_gist.requests.get",
        lambda *a, **k: (_ for _ in ()).throw(RequestException("boom")),
    )
    with pytest.raises(StateError, match="Failed to fetch state"):
        GistStateBackend(_gist_cfg()).load()


def test_gist_requires_gist_id_and_token() -> None:
    with pytest.raises(ConfigError, match="gist_id"):
        GistStateBackend(StateConfig(backend="github_gist", options={"token": "t"}))
    with pytest.raises(ConfigError, match="token"):
        GistStateBackend(StateConfig(backend="github_gist", options={"gist_id": "g"}))


def test_local_file_roundtrip(tmp_path: Path) -> None:
    backend = LocalFileStateBackend(
        StateConfig(backend="local_file", options={"path": str(tmp_path / "sub" / "state.json")})
    )
    assert backend.load() == {}  # missing file -> empty state
    backend.save({"a": {"cursor": "v1"}})
    assert backend.load() == {"a": {"cursor": "v1"}}


def test_local_file_invalid_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{not json", encoding="utf-8")
    backend = LocalFileStateBackend(StateConfig(backend="local_file", options={"path": str(path)}))
    with pytest.raises(StateError):
        backend.load()
