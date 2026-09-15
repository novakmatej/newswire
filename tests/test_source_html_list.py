"""html_list source: category pages (section_id) and webinar-style pages."""

from __future__ import annotations

import pytest
from requests import RequestException

from newswire.sources.base import SourceError
from newswire.sources.html_list import HtmlListSource, scrape_html_list
from tests.helpers import StubResponse

CATEGORY_HTML = """
<html>
<body>
    <section>
        <h3 class="heading-3 mb-6" id="latest-posts">Latest posts</h3>
        <div class="grid grid-cols-1 gap-6 gap-y-12 md:grid-cols-3">
            <div class="w-full rounded-2xl col-span-1">
                <h3 class="heading-4 my-3 text-left">
                    <a href="/blog/test-post-1">Test Post 1</a>
                </h3>
            </div>
            <div class="w-full rounded-2xl col-span-1">
                <h3 class="heading-4 my-3 text-left">
                    <a href="/blog/test-post-2">Test Post 2</a>
                </h3>
            </div>
        </div>
    </section>
</body>
</html>
"""

WEBINAR_HTML = """
<html>
<body>
    <section>
        <h3 class="heading-4 my-3 text-left">
            <a href="/resources/webinars/webinar-1">Smarter pipelines webinar</a>
        </h3>
        <h3 class="heading-4 my-3 text-left">
            <a href="/resources/webinars/webinar-2">Fast track workshop</a>
        </h3>
        <h3 class="heading-4 my-3 text-left">
            <a href="/resources/webinars/webinar-1">Smarter pipelines webinar</a>
        </h3>
    </section>
</body>
</html>
"""


def _stub_get(monkeypatch: pytest.MonkeyPatch, html: str) -> None:
    monkeypatch.setattr(
        "newswire.sources.html_list.requests.get",
        lambda url, timeout=None: StubResponse(content=html.encode("utf-8")),
    )


def test_scrape_category_page_with_section_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_get(monkeypatch, CATEGORY_HTML)
    items = scrape_html_list(
        "https://www.getdbt.com/blog/category/company-news", section_id="latest-posts"
    )
    assert [item.title for item in items] == ["Test Post 1", "Test Post 2"]
    assert items[0].url == "https://www.getdbt.com/blog/test-post-1"


def test_scrape_category_page_missing_anchor_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_get(monkeypatch, "<html><body><div>nothing here</div></body></html>")
    assert (
        scrape_html_list("https://www.getdbt.com/blog/category/x", section_id="latest-posts") == []
    )


def test_scrape_webinar_page_dedupes_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_get(monkeypatch, WEBINAR_HTML)
    items = scrape_html_list("https://www.getdbt.com/resources/webinars/category/upcoming")
    assert [item.title for item in items] == ["Smarter pipelines webinar", "Fast track workshop"]
    assert items[0].url == "https://www.getdbt.com/resources/webinars/webinar-1"


def test_scrape_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "newswire.sources.html_list.requests.get",
        lambda *a, **k: (_ for _ in ()).throw(RequestException("network error")),
    )
    with pytest.raises(SourceError):
        scrape_html_list("https://www.getdbt.com/x")


def test_check_seen_set_with_legacy_urls(monkeypatch: pytest.MonkeyPatch, source_cfg) -> None:
    _stub_get(monkeypatch, WEBINAR_HTML)
    source = HtmlListSource(
        source_cfg(
            "webinars",
            options={"url": "https://www.getdbt.com/resources/webinars/category/upcoming"},
        )
    )

    # Legacy webinar entry ('urls') still diffs correctly
    section, next_entry = source.check(
        {"urls": ["https://www.getdbt.com/resources/webinars/webinar-2"]}
    )
    assert [item.title for item in section.items] == ["Smarter pipelines webinar"]
    assert next_entry["seen"] == [
        "https://www.getdbt.com/resources/webinars/webinar-1",
        "https://www.getdbt.com/resources/webinars/webinar-2",
    ]

    # A stored item that disappeared is dropped from state silently
    section, next_entry = source.check(
        {
            "seen": [
                "https://www.getdbt.com/resources/webinars/webinar-1",
                "https://www.getdbt.com/resources/webinars/webinar-2",
                "https://www.getdbt.com/resources/webinars/webinar-removed",
            ]
        }
    )
    assert section is None
    assert "https://www.getdbt.com/resources/webinars/webinar-removed" not in next_entry["seen"]


def test_check_legacy_category_entry(monkeypatch: pytest.MonkeyPatch, source_cfg) -> None:
    _stub_get(monkeypatch, CATEGORY_HTML)
    source = HtmlListSource(
        source_cfg(
            "press",
            options={
                "url": "https://www.getdbt.com/blog/category/press",
                "section_id": "latest-posts",
            },
        )
    )
    # Legacy blog-category entry ('last_urls') still diffs correctly
    section, _ = source.check({"last_urls": ["https://www.getdbt.com/blog/test-post-2"]})
    assert [item.title for item in section.items] == ["Test Post 1"]
