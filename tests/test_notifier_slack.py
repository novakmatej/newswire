"""Slack notifier: Block Kit shapes for all three section kinds and the digest."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from newswire.config import ConfigError
from newswire.models import CARDS, LINKS, NOTES, Item, Section
from newswire.notifiers.slack import SlackNotificationError, SlackNotifier, render_section

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

LINKS_SECTION = Section(
    source_id="dbt-blog",
    title="Developer Blog Posts",
    kind=LINKS,
    emoji="📰",
    items=(
        Item(title="Blog Post 1", url="https://docs.getdbt.com/blog/post1"),
        Item(title="Blog Post 2", url="https://docs.getdbt.com/blog/post2"),
    ),
)

NOTES_SECTION = Section(
    source_id="dbt-cloud-releases",
    title="dbt Cloud Release Notes",
    kind=NOTES,
    emoji="☁️",
    subtitle="November 2025",
    link="https://docs.getdbt.com/docs/dbt-versions/release-notes/cloud",
    items=(
        Item(title="New: Feature X with a [link](https://example.com)"),
        Item(title="Something else"),
    ),
)


def _notifier(notifier_cfg, digest_cfg) -> SlackNotifier:
    return SlackNotifier(
        notifier_cfg("slack", "slack", options={"webhook_url": "https://hooks.example.com/x"}),
        digest_cfg,
    )


def test_card_blocks(notifier_cfg, digest_cfg) -> None:
    blocks = render_section(RELEASE_SECTION)

    assert blocks[0]["type"] == "header"
    assert blocks[0]["text"]["text"] == "🚀 dbt-core v1.8.0 • 2025-11-01"
    body = blocks[1]["text"]["text"]
    assert "*✨ Features*" in body
    assert "Feature A" in body
    assert "<https://gh/123|#123>" in body  # markdown link converted to Slack format
    assert blocks[2]["type"] == "context"
    assert "View full release notes on GitHub" in blocks[2]["elements"][0]["text"]


def test_card_without_body(notifier_cfg, digest_cfg) -> None:
    section = Section(
        source_id="s",
        title="dbt-fusion",
        kind=CARDS,
        items=(Item(title="v2.0.0", tag="v2.0.0", url="https://x"),),
    )
    blocks = render_section(section)
    assert "_No release notes provided_" in blocks[1]["text"]["text"]


def test_links_blocks() -> None:
    blocks = render_section(LINKS_SECTION)
    assert blocks[0]["text"]["text"] == "📰 Developer Blog Posts"
    text = blocks[1]["text"]["text"]
    assert "• <https://docs.getdbt.com/blog/post1|Blog Post 1>" in text
    assert "Blog Post 2" in text


def test_notes_blocks_bold_tags_and_footer() -> None:
    blocks = render_section(NOTES_SECTION)
    assert blocks[0]["text"]["text"] == "☁️ dbt Cloud Release Notes"
    assert blocks[1]["text"]["text"] == "*November 2025*"
    bullets = blocks[2]["text"]["text"]
    assert "*New:* Feature X" in bullets
    assert "<https://example.com|link>" in bullets
    assert "• Something else" in bullets
    assert blocks[3]["type"] == "context"
    assert "View all release notes" in blocks[3]["elements"][0]["text"]


def test_digest_header_order_and_dividers(notifier_cfg, digest_cfg) -> None:
    notifier = _notifier(notifier_cfg, digest_cfg)

    with patch("newswire.notifiers.slack.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        notifier.send_digest([NOTES_SECTION, RELEASE_SECTION, LINKS_SECTION])

    blocks = mock_post.call_args.kwargs["json"]["blocks"]
    assert blocks[0]["type"] == "header"
    assert "dbt News" in blocks[0]["text"]["text"]
    assert blocks[1]["type"] == "divider"

    header_texts = [b["text"]["text"] for b in blocks if b["type"] == "header"]
    # config order preserved: cloud -> core -> blog
    assert header_texts[1].startswith("☁️")
    assert header_texts[2].startswith("🚀")
    assert header_texts[3].startswith("📰")

    divider_count = sum(1 for b in blocks if b["type"] == "divider")
    assert divider_count == 3  # after digest header + between the 3 sections


def test_no_news_blocks(notifier_cfg, digest_cfg) -> None:
    notifier = _notifier(notifier_cfg, digest_cfg)
    with patch("newswire.notifiers.slack.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        notifier.send_no_news()

    blocks = mock_post.call_args.kwargs["json"]["blocks"]
    assert "dbt News" in blocks[0]["text"]["text"]
    assert blocks[1]["type"] == "divider"
    assert "No new updates" in blocks[2]["text"]["text"]
    assert "nothing new to learn" in blocks[2]["text"]["text"]


def test_request_failure_raises(notifier_cfg, digest_cfg) -> None:
    notifier = _notifier(notifier_cfg, digest_cfg)
    with patch(
        "newswire.notifiers.slack.requests.post",
        side_effect=requests.RequestException("boom"),
    ):
        with pytest.raises(SlackNotificationError, match="Failed to post Slack notification"):
            notifier.send_section(LINKS_SECTION)


def test_webhook_url_required(notifier_cfg, digest_cfg) -> None:
    with pytest.raises(ConfigError, match="webhook_url"):
        SlackNotifier(notifier_cfg("slack", "slack", options={}), digest_cfg)


def test_long_notes_split_under_slack_text_limit(notifier_cfg, digest_cfg) -> None:
    """A first-run dbt Cloud section (many long bullets) must stay under 3000 chars per block."""
    big_section = Section(
        source_id="cloud",
        title="dbt Cloud Release Notes",
        kind=NOTES,
        subtitle="September 2026",
        link="https://example.com/notes",
        items=tuple(Item(title=f"New: bullet {i} " + "x" * 600) for i in range(13)),
    )
    blocks = render_section(big_section)

    texts = [b["text"]["text"] for b in blocks if b["type"] == "section"]
    assert all(len(text) <= 3000 for text in texts)
    assert len(texts) > 2  # subtitle + several split bullet blocks
    joined = "\n".join(texts)
    assert "bullet 0" in joined and "bullet 12" in joined  # nothing dropped


def test_send_blocks_chunks_at_fifty_blocks(notifier_cfg, digest_cfg) -> None:
    notifier = _notifier(notifier_cfg, digest_cfg)
    sections = [
        Section(
            source_id=f"s{i}",
            title=f"Section {i}",
            kind=LINKS,
            items=(Item(title="Post", url="https://example.com"),),
        )
        for i in range(40)  # 40 sections -> > 50 blocks with header/dividers
    ]

    with patch("newswire.notifiers.slack.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        notifier.send_digest(sections)

    assert mock_post.call_count > 1
    total = 0
    for call in mock_post.call_args_list:
        blocks = call.kwargs["json"]["blocks"]
        assert len(blocks) <= 50
        total += len(blocks)
    assert total == 40 * 2 + 2 + 39  # sections (header+list) + digest header/divider + dividers
