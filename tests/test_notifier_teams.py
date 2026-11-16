"""Teams notifier: Adaptive Card envelope, markdown subset, chunking under 25 KB."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
import requests

from newswire.config import ConfigError
from newswire.models import CARDS, LINKS, NOTES, Item, Section
from newswire.notifiers.teams import (
    TeamsNotificationError,
    TeamsNotifier,
    build_adaptive_card,
    card_markdown,
    links_markdown,
    notes_markdown,
)

RELEASE_SECTION = Section(
    source_id="dbt-core-releases",
    title="dbt-core",
    kind=CARDS,
    emoji="🚀",
    items=(
        Item(
            title="dbt-core v1.8.0",
            tag="v1.8.0",
            url="https://github.com/dbt-labs/dbt-core/releases/tag/v1.8.0",
            body="## Features\n- Feature A\n- Feature B\n## Fixes\n- Fix [#123](https://gh/123)",
            date="2025-11-01T00:00:00Z",
        ),
    ),
)


def _card_content(payload: dict) -> dict:
    return payload["attachments"][0]["content"]


def _notifier(notifier_cfg, digest_cfg, **options) -> TeamsNotifier:
    return TeamsNotifier(
        notifier_cfg(
            "teams", "teams", options={"webhook_url": "https://example.com/webhook", **options}
        ),
        digest_cfg,
    )


def test_build_adaptive_card_envelope() -> None:
    payload = build_adaptive_card(["first", "second"])

    assert payload["type"] == "message"
    attachment = payload["attachments"][0]
    assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"

    content = _card_content(payload)
    assert content["type"] == "AdaptiveCard"
    assert [block["text"] for block in content["body"]] == ["first", "second"]
    # separators only between blocks
    assert [block["separator"] for block in content["body"]] == [False, True]
    assert all(block["wrap"] for block in content["body"])


def test_card_markdown_keeps_links_and_limits_items() -> None:
    markdown = card_markdown(RELEASE_SECTION, RELEASE_SECTION.items[0], item_limit=1)

    assert "**dbt-core v1.8.0**" in markdown
    assert "2025-11-01" in markdown
    assert "- Feature A" in markdown
    assert "Feature B" not in markdown
    assert "_...and 1 more_" in markdown
    assert "[View full release notes on GitHub](" in markdown


def test_card_markdown_without_body() -> None:
    section = Section(source_id="s", title="dbt-fusion", kind=CARDS, items=())
    markdown = card_markdown(section, Item(title="v2", tag="v2.0.0", url="https://x"))
    assert "_No release notes provided_" in markdown


def test_links_markdown() -> None:
    section = Section(
        source_id="blog",
        title="Blog",
        kind=LINKS,
        emoji="📰",
        items=(Item(title="Post 1", url="https://example.com/1"),),
    )
    markdown = links_markdown(section)
    assert "**📰 Blog**" in markdown
    assert "- [Post 1](https://example.com/1)" in markdown


def test_notes_markdown_bolds_leading_tag() -> None:
    section = Section(
        source_id="cloud",
        title="dbt Cloud Release Notes",
        kind=NOTES,
        emoji="☁️",
        subtitle="November 2025",
        link="https://example.com/notes",
        items=(Item(title="New: Feature X"), Item(title="Something else")),
    )
    markdown = notes_markdown(section)
    assert "**November 2025**" in markdown
    assert "- **New:** Feature X" in markdown
    assert "- Something else" in markdown
    assert "[View all release notes](https://example.com/notes)" in markdown


def test_send_digest_posts_adaptive_card_with_intro(notifier_cfg, digest_cfg) -> None:
    notifier = _notifier(notifier_cfg, digest_cfg)

    with patch("newswire.notifiers.teams.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        notifier.send_digest([RELEASE_SECTION])

    assert mock_post.call_count == 1
    content = _card_content(mock_post.call_args.kwargs["json"])
    assert content["type"] == "AdaptiveCard"
    dumped = json.dumps(content)
    assert "dbt-core v1.8.0" in dumped
    assert "dbt News Update" in content["body"][0]["text"]
    assert "Hey dbt builders!" in content["body"][0]["text"]


def test_send_digest_splits_oversized_payload(notifier_cfg, digest_cfg) -> None:
    big_section = Section(
        source_id="blog",
        title="Blog",
        kind=LINKS,
        items=tuple(
            Item(title=f"Post {i} " + "x" * 400, url=f"https://example.com/{i}") for i in range(60)
        ),
    )
    notifier = _notifier(notifier_cfg, digest_cfg)

    with patch("newswire.notifiers.teams.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        notifier.send_digest([RELEASE_SECTION, big_section])

    assert mock_post.call_count > 1
    for call in mock_post.call_args_list:
        assert len(json.dumps(call.kwargs["json"]).encode("utf-8")) <= 25_000


def test_send_no_news(notifier_cfg, digest_cfg) -> None:
    notifier = _notifier(notifier_cfg, digest_cfg)
    with patch("newswire.notifiers.teams.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        notifier.send_no_news()

    content = _card_content(mock_post.call_args.kwargs["json"])
    assert "No new updates today" in content["body"][0]["text"]


def test_request_failure_raises_teams_error(notifier_cfg, digest_cfg) -> None:
    notifier = _notifier(notifier_cfg, digest_cfg)
    with patch(
        "newswire.notifiers.teams.requests.post",
        side_effect=requests.RequestException("boom"),
    ):
        with pytest.raises(TeamsNotificationError, match="Failed to post Teams notification"):
            notifier.send_section(RELEASE_SECTION)


def test_build_adaptive_card_collapsible_block_toggles_hidden_body() -> None:
    body = _card_content(build_adaptive_card(["intro", ("**Title**", "- a\n- b")]))["body"]

    assert body[0]["text"] == "intro"
    header, content = body[1], body[2]
    assert header["separator"] is True
    assert header["items"][0]["text"] == "**Title** ▸"
    assert header["selectAction"] == {
        "type": "Action.ToggleVisibility",
        "targetElements": [content["id"]],
    }
    assert content["isVisible"] is False
    assert content["items"][0]["text"] == "- a\n- b"


def test_send_digest_collapsible_keeps_intro_visible_and_full_content(
    notifier_cfg, digest_cfg
) -> None:
    notifier = _notifier(notifier_cfg, digest_cfg, collapsible=True)

    with patch("newswire.notifiers.teams.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        notifier.send_digest([RELEASE_SECTION])

    body = _card_content(mock_post.call_args.kwargs["json"])["body"]
    assert body[0]["type"] == "TextBlock"
    assert "dbt News Update" in body[0]["text"]
    assert "dbt-core v1.8.0" in body[1]["items"][0]["text"]
    hidden = body[2]["items"][0]["text"]
    assert "- Feature A" in hidden
    assert "[View full release notes on GitHub](" in hidden


def test_send_digest_collapsible_splits_oversized_section_with_titles(
    notifier_cfg, digest_cfg
) -> None:
    big_section = Section(
        source_id="blog",
        title="Blog",
        kind=LINKS,
        items=tuple(
            Item(title=f"Post {i} " + "x" * 400, url=f"https://example.com/{i}") for i in range(60)
        ),
    )
    notifier = _notifier(notifier_cfg, digest_cfg, collapsible=True)

    with patch("newswire.notifiers.teams.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        notifier.send_digest([big_section])

    assert mock_post.call_count > 1
    titles = []
    for call in mock_post.call_args_list:
        assert len(json.dumps(call.kwargs["json"]).encode("utf-8")) <= 25_000
        for element in _card_content(call.kwargs["json"])["body"]:
            if "selectAction" in element:
                titles.append(element["items"][0]["text"])
    assert titles[0] == "**Blog** ▸"
    assert all(title == "**Blog** (cont.) ▸" for title in titles[1:])


def test_collapsible_must_be_bool(notifier_cfg, digest_cfg) -> None:
    with pytest.raises(ConfigError, match="collapsible"):
        _notifier(notifier_cfg, digest_cfg, collapsible="yes")
