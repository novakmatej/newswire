"""github_discussions source: GraphQL parsing and seen-set diff via check()."""

from __future__ import annotations

import pytest

from newswire.config import ConfigError
from newswire.sources.base import SourceError
from newswire.sources.github_discussions import GithubDiscussionsSource, fetch_discussions
from tests.helpers import StubResponse


def _graphql_router(discussions_nodes: list[dict]):
    """Stub the three GraphQL calls (repo id, categories, discussions)."""

    def fake_post(url, headers=None, json=None, timeout=None):
        query = json["query"]
        if "repository(owner" in query:
            return StubResponse(json_data={"data": {"repository": {"id": "REPO_ID"}}})
        if "discussionCategories" in query:
            return StubResponse(
                json_data={
                    "data": {
                        "node": {
                            "discussionCategories": {
                                "nodes": [{"id": "CAT_ID", "slug": "announcements"}]
                            }
                        }
                    }
                }
            )
        return StubResponse(
            json_data={"data": {"node": {"discussions": {"nodes": discussions_nodes}}}}
        )

    return fake_post


NODES = [
    {
        "number": 42,
        "title": "Fusion 2.0 announced",
        "url": "https://github.com/o/r/discussions/42",
        "body": "big news",
        "createdAt": "2025-11-02T00:00:00Z",
        "author": {"login": "someone"},
    },
    {
        "number": 41,
        "title": "Older news",
        "url": "https://github.com/o/r/discussions/41",
        "body": None,
        "createdAt": "2025-11-01T00:00:00Z",
        "author": {"login": "someone"},
    },
]


def test_fetch_discussions_parses_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("newswire.sources.github_discussions.requests.post", _graphql_router(NODES))
    discussions = fetch_discussions("o/r", "announcements", token="tok")
    assert [d.tag for d in discussions] == ["42", "41"]
    assert discussions[0].title == "Fusion 2.0 announced"
    assert discussions[0].url == "https://github.com/o/r/discussions/42"


def test_unknown_category_lists_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("newswire.sources.github_discussions.requests.post", _graphql_router(NODES))
    with pytest.raises(SourceError, match="Available: announcements"):
        fetch_discussions("o/r", "nonexistent", token="tok")


def test_graphql_errors_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "newswire.sources.github_discussions.requests.post",
        lambda *a, **k: StubResponse(json_data={"errors": [{"message": "bad"}]}),
    )
    with pytest.raises(SourceError, match="GraphQL errors"):
        fetch_discussions("o/r", "announcements", token="tok")


def test_check_seen_set_with_legacy_numbers(monkeypatch: pytest.MonkeyPatch, source_cfg) -> None:
    monkeypatch.setattr("newswire.sources.github_discussions.requests.post", _graphql_router(NODES))
    source = GithubDiscussionsSource(
        source_cfg("disc", options={"repo": "o/r", "category": "announcements", "token": "tok"})
    )

    # Legacy 'numbers' entry (ints) still diffs correctly
    section, next_entry = source.check({"numbers": [41]})
    assert [item.tag for item in section.items] == ["42"]
    assert section.kind == "links"
    assert next_entry["seen"] == ["42", "41"]

    # Everything seen -> no section, state still refreshed
    section, next_entry = source.check({"seen": ["41", "42"]})
    assert section is None
    assert next_entry["seen"] == ["42", "41"]


def test_token_required(source_cfg) -> None:
    with pytest.raises(ConfigError, match="token"):
        GithubDiscussionsSource(
            source_cfg("disc", options={"repo": "o/r", "category": "announcements"})
        )
