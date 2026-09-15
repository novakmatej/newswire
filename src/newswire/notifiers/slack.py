"""Slack notifier: Block Kit blocks, mrkdwn, links as <url|text>, *bold*.

Options: ``webhook_url`` (required), ``timeout``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

import requests

from newswire.config import ConfigError, DigestConfig, NotifierConfig
from newswire.models import CARDS, LINKS, NOTES, Item, Section
from newswire.notifiers.base import (
    SECTION_EMOJI,
    NotificationError,
    bold_leading_tag,
    convert_markdown_links,
    heading_text,
    parse_release_sections,
)
from newswire.registry import notifier_type


class SlackNotificationError(NotificationError):
    """Raised when sending a Slack notification fails."""


def _slack_links(text: str) -> str:
    """Convert [text](url) markdown links to Slack's <url|text>."""
    return convert_markdown_links(text, r"<\2|\1>")


def _header_block(text: str) -> dict[str, Any]:
    return {"type": "header", "text": {"type": "plain_text", "text": text, "emoji": True}}


def _mrkdwn_block(text: str) -> dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


# Slack hard limits: 3000 chars of text per section block, 50 blocks per message.
_MAX_TEXT = 2900
_MAX_BLOCKS = 50


def _mrkdwn_blocks(text: str) -> list[dict[str, Any]]:
    """One or more section blocks, each under Slack's 3000-char text limit.

    Splits on lines (bullets); a single over-long line is hard-cut.
    """
    lines: list[str] = []
    for line in text.split("\n"):
        while len(line) > _MAX_TEXT:
            lines.append(line[:_MAX_TEXT])
            line = line[_MAX_TEXT:]
        lines.append(line)

    blocks: list[dict[str, Any]] = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if current and len(candidate) > _MAX_TEXT:
            blocks.append(_mrkdwn_block(current))
            current = line
        else:
            current = candidate
    if current:
        blocks.append(_mrkdwn_block(current))
    return blocks


def _context_link_block(url: str, label: str) -> dict[str, Any]:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": f"<{url}|{label}>"}]}


def _format_body_section(section_name: str, items: list[str], limit: int = 3) -> str:
    """One parsed release-body section (Features, Fixes, ...) as mrkdwn."""
    if not items:
        return ""
    emoji = SECTION_EMOJI.get(section_name, "•")
    formatted = [f"  • {_slack_links(item)}" for item in items[:limit]]
    if len(items) > limit:
        formatted.append(f"  • _...and {len(items) - limit} more_")
    return f"*{emoji} {section_name}*\n" + "\n".join(formatted)


def format_card(section: Section, item: Item) -> list[dict[str, Any]]:
    """One release as Slack blocks: header, parsed sections, footer link."""
    header = f"{section.emoji} {section.title}" if section.emoji else section.title
    if item.tag:
        header += f" {item.tag}"
    if item.date:
        header += f" • {item.date[:10]}"

    blocks = [_header_block(header)]

    if item.body:
        parts = [
            text
            for name, items in parse_release_sections(item.body).items()
            if (text := _format_body_section(name, items))
        ]
        main_text = (
            "\n\n".join(parts)
            if parts
            else item.body[:500] + ("..." if len(item.body) > 500 else "")
        )
    else:
        main_text = "_No release notes provided_"
    blocks.extend(_mrkdwn_blocks(main_text))

    if item.url:
        blocks.append(_context_link_block(item.url, "View full release notes on GitHub"))
    return blocks


def format_links(section: Section) -> list[dict[str, Any]]:
    """A titled bullet list of links as Slack blocks."""
    bullets = "\n".join(f"• <{item.url}|{item.title}>" for item in section.items)
    return [_header_block(heading_text(section)), *_mrkdwn_blocks(bullets)]


def format_notes(section: Section) -> list[dict[str, Any]]:
    """Release-notes bullets (subtitle + tagged items + footer link) as Slack blocks."""
    bullets = "\n".join(
        f"• {bold_leading_tag(_slack_links(item.title), '*')}" for item in section.items
    )
    blocks = [_header_block(heading_text(section))]
    if section.subtitle:
        blocks.append(_mrkdwn_block(f"*{section.subtitle}*"))
    blocks.extend(_mrkdwn_blocks(bullets))
    if section.link:
        blocks.append(_context_link_block(section.link, "View all release notes"))
    return blocks


def render_section(section: Section) -> list[dict[str, Any]]:
    if section.kind == CARDS:
        blocks = []
        for item in section.items:
            blocks.extend(format_card(section, item))
        return blocks
    if section.kind == NOTES:
        return format_notes(section)
    if section.kind == LINKS:
        return format_links(section)
    raise NotificationError(f"Unknown section kind: {section.kind}")


@notifier_type("slack")
class SlackNotifier:
    def __init__(self, cfg: NotifierConfig, digest: DigestConfig):
        self.id = cfg.id
        self.send_no_news_enabled = cfg.send_no_news
        self.digest = digest
        self.webhook_url = cfg.options.get("webhook_url")
        if not self.webhook_url:
            raise ConfigError(f"notifier '{cfg.id}': slack requires option 'webhook_url'")
        self.timeout = float(cfg.options.get("timeout", 10))

    def send_digest(self, sections: Sequence[Section]) -> None:
        today = datetime.now().strftime("%B %d, %Y")
        blocks: list[dict[str, Any]] = [
            _header_block(f"📬 {self.digest.title} • {today}"),
            {"type": "divider"},
        ]
        for index, section in enumerate(sections):
            blocks.extend(render_section(section))
            if index < len(sections) - 1:
                blocks.append({"type": "divider"})
        self._send_blocks(blocks)

    def send_section(self, section: Section) -> None:
        self._send_blocks(render_section(section))

    def send_no_news(self) -> None:
        today = datetime.now().strftime("%B %d, %Y")
        self._send_blocks(
            [
                _header_block(f"📬 {self.digest.title} • {today}"),
                {"type": "divider"},
                _mrkdwn_block(
                    "📭 *No new updates today*"
                    "\n\nThere's currently nothing new to learn. Check back next time!"
                ),
            ]
        )

    def _send_blocks(self, blocks: Sequence[dict[str, Any]]) -> None:
        """Post blocks, split into messages of at most 50 blocks (Slack's cap).

        ponytail: splits blindly every 50 blocks; align to section boundaries
        if a mid-card cut ever bothers anyone.
        """
        blocks = list(blocks)
        for start in range(0, len(blocks), _MAX_BLOCKS):
            payload = {"blocks": blocks[start : start + _MAX_BLOCKS]}
            try:
                response = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
                response.raise_for_status()
            except requests.RequestException as exc:
                raise SlackNotificationError(f"Failed to post Slack notification: {exc}") from exc
