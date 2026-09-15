"""github_releases source: REST parsing and cursor diff via check()."""

from __future__ import annotations

import pytest
from requests import RequestException

from newswire.config import ConfigError
from newswire.sources.base import SourceError
from newswire.sources.github_releases import GithubReleasesSource, fetch_releases
from tests.helpers import StubResponse


def _payload(tags: list[str]) -> list[dict]:
    return [
        {
            "tag_name": tag,
            "name": f"release {tag}",
            "html_url": f"https://github.com/o/r/releases/tag/{tag}",
            "body": f"## Features\n- something in {tag}",
            "published_at": "2025-11-01T00:00:00Z",
        }
        for tag in tags
    ]


def test_fetch_releases_parses_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured.update(url=url, headers=headers, params=params)
        return StubResponse(json_data=_payload(["v2", "v1"]) + [{"name": "no tag"}])

    monkeypatch.setattr("newswire.sources.github_releases.requests.get", fake_get)

    releases = fetch_releases("o/r", token="tok", per_page=5)

    assert captured["url"] == "https://api.github.com/repos/o/r/releases"
    assert captured["params"] == {"per_page": 5, "page": 1}
    assert captured["headers"]["Authorization"] == "Bearer tok"
    assert [r.tag for r in releases] == ["v2", "v1"]  # invalid entry skipped
    assert releases[0].title == "release v2"
    assert releases[0].url == "https://github.com/o/r/releases/tag/v2"
    assert "Features" in releases[0].body


def test_fetch_releases_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "newswire.sources.github_releases.requests.get",
        lambda *a, **k: (_ for _ in ()).throw(RequestException("boom")),
    )
    with pytest.raises(SourceError, match="Failed to fetch releases"):
        fetch_releases("o/r")


def test_check_returns_new_releases_and_next_cursor(
    monkeypatch: pytest.MonkeyPatch, source_cfg
) -> None:
    monkeypatch.setattr(
        "newswire.sources.github_releases.requests.get",
        lambda *a, **k: StubResponse(json_data=_payload(["v3", "v2", "v1"])),
    )
    source = GithubReleasesSource(source_cfg("core", options={"repo": "o/r"}))

    # Legacy state entry with last_id still works
    section, next_entry = source.check({"last_id": "v2"})
    assert section is not None
    assert [item.tag for item in section.items] == ["v3"]
    assert section.kind == "cards"
    assert next_entry == {"cursor": "v3", "last_check": "2025-11-01T00:00:00Z"}

    # Nothing new -> no section, state untouched
    section, next_entry = source.check({"cursor": "v3"})
    assert section is None
    assert next_entry is None

    # First run -> only the newest counts
    section, _ = source.check(None)
    assert [item.tag for item in section.items] == ["v3"]

    # Stored tag gone -> everything is new
    section, _ = source.check({"cursor": "v0"})
    assert len(section.items) == 3


def test_missing_repo_option_fails(source_cfg) -> None:
    with pytest.raises(ConfigError, match="requires option 'repo'"):
        GithubReleasesSource(source_cfg("core", options={}))
