"""Microsoft Teams notifier.

Targets a Teams *Workflow* webhook (Power Automate, "When a Teams webhook
request is received"). That trigger expects an Adaptive Card envelope, not the
retired Office 365 connector MessageCard format.

Adaptive Card TextBlocks render a markdown subset: **bold**, _italic_,
``- bullets`` and ``[text](url)``. Headings and tables are not supported, so
section titles are bold text. Cards are chunked under ~28 KB; an oversized
section is split by line.

Options: ``webhook_url`` (required), ``timeout``.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Sequence

import requests

from newswire.config import ConfigError, DigestConfig, NotifierConfig
from newswire.models import CARDS, LINKS, NOTES, Item, Section
from newswire.notifiers.base import (
    SECTION_EMOJI,
    NotificationError,
    bold_leading_tag,
    heading_text,
    parse_release_sections,
)
from newswire.registry import notifier_type

# Teams rejects adaptive card payloads at roughly 28 KB; stay clear of the edge.
_MAX_CARD_BYTES = 25_000


class TeamsNotificationError(NotificationError):
    """Raised when sending a Teams notification fails."""


def _paragraphs(*parts: str | list[str]) -> str:
    """Join paragraphs with a blank line; a list becomes one bullet block."""
    rendered = []
    for part in parts:
        text = "\n".join(part) if isinstance(part, list) else part
        if text:
            rendered.append(text)
    return "\n\n".join(rendered)


def card_markdown(section: Section, item: Item, item_limit: int = 3) -> str:
    """Format one release as Adaptive Card markdown."""
    title = f"{section.emoji} **{section.title}" if section.emoji else f"**{section.title}"
    if item.tag:
        title += f" {item.tag}"
    title += "**"
    if item.date:
        title += f" • {item.date[:10]}"

    parts: list[str | list[str]] = [title]

    sections = parse_release_sections(item.body) if item.body else {}
    if sections:
        for section_name, items in sections.items():
            emoji = SECTION_EMOJI.get(section_name, "•")
            bullets = [f"- {entry}" for entry in items[:item_limit]]
            if len(items) > item_limit:
                bullets.append(f"- _...and {len(items) - item_limit} more_")
            parts.append(f"{emoji} **{section_name}**")
            parts.append(bullets)
    else:
        parts.append("_No release notes provided_")

    if item.url:
        parts.append(f"[View full release notes on GitHub]({item.url})")
    return _paragraphs(*parts)


def links_markdown(section: Section) -> str:
    """Format a titled list of links as Adaptive Card markdown."""
    bullets = [f"- [{item.title}]({item.url})" for item in section.items]
    return _paragraphs(f"**{heading_text(section)}**", bullets)


def notes_markdown(section: Section) -> str:
    """Format release-notes bullets as Adaptive Card markdown."""
    bullets = [f"- {bold_leading_tag(item.title, '**')}" for item in section.items]
    parts: list[str | list[str]] = [f"**{heading_text(section)}**"]
    if section.subtitle:
        parts.append(f"**{section.subtitle}**")
    parts.append(bullets)
    if section.link:
        parts.append(f"[View all release notes]({section.link})")
    return _paragraphs(*parts)


def render_section(section: Section) -> list[str]:
    """One config section as one or more markdown card sections."""
    if section.kind == CARDS:
        return [card_markdown(section, item) for item in section.items]
    if section.kind == NOTES:
        return [notes_markdown(section)]
    if section.kind == LINKS:
        return [links_markdown(section)]
    raise NotificationError(f"Unknown section kind: {section.kind}")


@notifier_type("teams")
class TeamsNotifier:
    def __init__(self, cfg: NotifierConfig, digest: DigestConfig):
        self.id = cfg.id
        self.send_no_news_enabled = cfg.send_no_news
        self.digest = digest
        self.webhook_url = cfg.options.get("webhook_url")
        if not self.webhook_url:
            raise ConfigError(f"notifier '{cfg.id}': teams requires option 'webhook_url'")
        self.timeout = float(cfg.options.get("timeout", 10))

    def send_digest(self, sections: Sequence[Section]) -> None:
        rendered: list[str] = []
        for section in sections:
            rendered.extend(render_section(section))
        rendered = [text for text in rendered if text]
        if not rendered:
            return

        year, week = datetime.now().isocalendar()[:2]
        intro = _paragraphs(
            f"**📬 {self.digest.title} Update • Week {week}, {year}**",
            self.digest.intro,
        )
        self._send_sections([intro, *rendered])

    def send_section(self, section: Section) -> None:
        self._send_sections(render_section(section))

    def send_no_news(self) -> None:
        self._send_sections(
            [
                "**📭 No new updates today**",
                "There's currently nothing new to learn. Check back next time!",
            ]
        )

    def _send_sections(self, sections: Sequence[str]) -> None:
        """Post sections as one or more Adaptive Cards."""
        for chunk in _chunk_sections([s for s in sections if s]):
            self._post(build_adaptive_card(chunk))

    def _post(self, payload: dict[str, Any]) -> None:
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise TeamsNotificationError(f"Failed to post Teams notification: {exc}") from exc


def build_adaptive_card(sections: Sequence[str]) -> dict[str, Any]:
    """Wrap markdown sections in the Teams Workflow Adaptive Card envelope."""
    body = [
        {"type": "TextBlock", "text": section, "wrap": True, "separator": index > 0}
        for index, section in enumerate(sections)
    ]
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "version": "1.4",
                    "body": body,
                },
            }
        ],
    }


def _chunk_sections(sections: Sequence[str], max_bytes: int = _MAX_CARD_BYTES) -> list[list[str]]:
    """Split sections into cards that each stay under the Teams payload limit.

    Sections too large on their own (a long blog list, say) are split by line so
    the card is still accepted instead of the whole post being rejected.

    ponytail: re-serializes per candidate (O(n^2)); n is sections/lines of one
    digest, so switch to running byte counts only if that grows to thousands.
    """
    chunks: list[list[str]] = []
    current: list[str] = []

    for section in sections:
        for part in _split_oversized(section, max_bytes):
            candidate = [*current, part]
            if current and _card_size(candidate) > max_bytes:
                chunks.append(current)
                current = [part]
            else:
                current = candidate

    if current:
        chunks.append(current)
    return chunks


def _split_oversized(section: str, max_bytes: int) -> list[str]:
    """Split one section into line-aligned parts that each fit in a card."""
    if _card_size([section]) <= max_bytes:
        return [section]

    parts: list[str] = []
    current: list[str] = []

    for line in section.split("\n"):
        candidate = [*current, line]
        if current and _card_size(["\n".join(candidate)]) > max_bytes:
            parts.append("\n".join(current))
            current = [line]
        else:
            current = candidate

    if current:
        parts.append("\n".join(current))
    # A single line over the limit is left as-is; nothing to split on.
    return parts


def _card_size(sections: Sequence[str]) -> int:
    return len(json.dumps(build_adaptive_card(sections)).encode("utf-8"))
