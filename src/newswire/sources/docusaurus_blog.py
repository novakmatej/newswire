"""Docusaurus-style blog listing scraper, cursor diff on post URL.

Options: ``url`` (required), ``item_selector``, ``title_selector``,
``date_selector``, ``timeout``. Selector defaults match docs.getdbt.com/blog;
point them elsewhere for another Docusaurus site. Scraper - breaks when the
page markup changes. Renders as ``links``.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from newswire.config import ConfigError, SourceConfig
from newswire.models import LINKS, Item, Section
from newswire.registry import source_type
from newswire.sources.base import SourceError, new_by_cursor, read_cursor

DEFAULT_ITEM_SELECTOR = "article.margin-bottom--xl"
DEFAULT_TITLE_SELECTOR = "h2.title_f1Hy a"
DEFAULT_DATE_SELECTOR = "time"


def scrape_blog_posts(
    url: str,
    item_selector: str = DEFAULT_ITEM_SELECTOR,
    title_selector: str = DEFAULT_TITLE_SELECTOR,
    date_selector: str = DEFAULT_DATE_SELECTOR,
    timeout: float = 10.0,
) -> list[Item]:
    """Scrape blog posts (newest first) as normalised items."""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "lxml")
        posts = []

        for article in soup.select(item_selector):
            title_link = article.select_one(title_selector)
            if not title_link:
                continue

            title = title_link.get_text(strip=True)
            href = title_link.get("href", "")
            full_url = href if href.startswith("http") else urljoin(url, href)

            published_date = None
            date_elem = article.select_one(date_selector)
            if date_elem:
                published_date = date_elem.get("datetime") or date_elem.get_text(strip=True)

            posts.append(Item(title=title, url=full_url, date=published_date))

        return posts

    except requests.RequestException as exc:
        raise SourceError(f"Failed to scrape blog {url}: {exc}") from exc
    except Exception as exc:
        raise SourceError(f"Failed to parse blog HTML from {url}: {exc}") from exc


@source_type("docusaurus_blog")
class DocusaurusBlogSource:
    def __init__(self, cfg: SourceConfig):
        self.id = cfg.id
        self.title = cfg.title
        self.emoji = cfg.emoji
        options = cfg.options
        self.url = options.get("url")
        if not self.url:
            raise ConfigError(f"source '{cfg.id}': docusaurus_blog requires option 'url'")
        self.item_selector = options.get("item_selector", DEFAULT_ITEM_SELECTOR)
        self.title_selector = options.get("title_selector", DEFAULT_TITLE_SELECTOR)
        self.date_selector = options.get("date_selector", DEFAULT_DATE_SELECTOR)
        self.timeout = float(options.get("timeout", 10))

    def check(self, entry: dict[str, Any] | None) -> tuple[Section | None, dict[str, Any] | None]:
        posts = scrape_blog_posts(
            self.url, self.item_selector, self.title_selector, self.date_selector, self.timeout
        )
        count = new_by_cursor([post.url or "" for post in posts], read_cursor(entry))
        new = posts[:count]
        if not new:
            return None, None
        section = Section(
            source_id=self.id, title=self.title, kind=LINKS, items=tuple(new), emoji=self.emoji
        )
        next_entry = {"cursor": posts[0].url, "last_check": posts[0].date or ""}
        return section, next_entry
