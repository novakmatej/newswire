"""Generic "list of linked headings" scraper, seen-set diff on URL.

Covers both getdbt.com blog-category pages and the upcoming-webinars page with
one parsing rule: select heading elements, take the link inside each.

Options: ``url`` (required), ``item_selector`` (default ``h3.heading-4``),
``section_id`` (optional - when set, only headings inside the ``div.grid``
that follows the element with this HTML id are considered; used by the
category pages' "latest-posts" section), ``timeout``. Scraper - breaks when
the page markup changes. Renders as ``links``.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from newswire.config import ConfigError, SourceConfig
from newswire.models import LINKS, Item, Section
from newswire.registry import source_type
from newswire.sources.base import SourceError, new_by_seen, read_seen

DEFAULT_ITEM_SELECTOR = "h3.heading-4"
_MIN_TITLE_LENGTH = 5


def scrape_html_list(
    url: str,
    item_selector: str = DEFAULT_ITEM_SELECTOR,
    section_id: str | None = None,
    timeout: float = 10.0,
) -> list[Item]:
    """Scrape linked headings as normalised items, deduplicated by URL."""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "lxml")
        container = soup
        if section_id:
            anchor = soup.find(id=section_id)
            if not anchor:
                return []
            container = anchor.find_next("div", class_="grid")
            if not container:
                return []

        items = []
        seen_urls = set()
        for heading in container.select(item_selector):
            link = heading if heading.name == "a" else heading.find("a", href=True)
            if not link:
                continue

            title = link.get_text(strip=True)
            if not title or len(title) < _MIN_TITLE_LENGTH:
                continue

            href = link.get("href", "")
            if not href:
                continue
            full_url = href if href.startswith("http") else urljoin(url, href)

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            items.append(Item(title=title, url=full_url))

        return items

    except requests.RequestException as exc:
        raise SourceError(f"Failed to scrape {url}: {exc}") from exc
    except Exception as exc:
        raise SourceError(f"Failed to parse HTML from {url}: {exc}") from exc


@source_type("html_list")
class HtmlListSource:
    def __init__(self, cfg: SourceConfig):
        self.id = cfg.id
        self.title = cfg.title
        self.emoji = cfg.emoji
        options = cfg.options
        self.url = options.get("url")
        if not self.url:
            raise ConfigError(f"source '{cfg.id}': html_list requires option 'url'")
        self.item_selector = options.get("item_selector", DEFAULT_ITEM_SELECTOR)
        self.section_id = options.get("section_id")
        self.timeout = float(options.get("timeout", 10))

    def check(self, entry: dict[str, Any] | None) -> tuple[Section | None, dict[str, Any] | None]:
        items = scrape_html_list(self.url, self.item_selector, self.section_id, self.timeout)
        if not items:
            return None, None
        new_urls = set(new_by_seen([item.url or "" for item in items], read_seen(entry)))
        new = [item for item in items if item.url in new_urls]
        next_entry = {"seen": [item.url for item in items], "last_check": ""}
        if not new:
            return None, next_entry
        section = Section(
            source_id=self.id, title=self.title, kind=LINKS, items=tuple(new), emoji=self.emoji
        )
        return section, next_entry
