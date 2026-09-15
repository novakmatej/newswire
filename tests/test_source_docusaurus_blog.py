"""docusaurus_blog source: HTML parsing and cursor diff via check()."""

from __future__ import annotations

import pytest
from requests import RequestException

from newswire.sources.base import SourceError
from newswire.sources.docusaurus_blog import DocusaurusBlogSource, scrape_blog_posts
from tests.helpers import StubResponse

HTML = """
<html>
<body>
    <main>
        <article class="margin-bottom--xl">
            <header>
                <h2 class="title_f1Hy">
                    <a href="/blog/test-post">Test Blog Post</a>
                </h2>
                <time datetime="2025-01-15T00:00:00.000Z">January 15, 2025</time>
            </header>
        </article>
        <article class="margin-bottom--xl">
            <header>
                <h2 class="title_f1Hy">
                    <a href="/blog/another-post">Another Post</a>
                </h2>
                <time datetime="2025-01-10T00:00:00.000Z">January 10, 2025</time>
            </header>
        </article>
    </main>
</body>
</html>
"""


def _stub_get(monkeypatch: pytest.MonkeyPatch, html: str) -> None:
    monkeypatch.setattr(
        "newswire.sources.docusaurus_blog.requests.get",
        lambda url, timeout=None: StubResponse(content=html.encode("utf-8")),
    )


def test_scrape_blog_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_get(monkeypatch, HTML)
    posts = scrape_blog_posts("https://docs.getdbt.com/blog")

    assert len(posts) == 2
    assert posts[0].title == "Test Blog Post"
    assert posts[0].url == "https://docs.getdbt.com/blog/test-post"
    assert posts[0].date == "2025-01-15T00:00:00.000Z"
    assert posts[1].url == "https://docs.getdbt.com/blog/another-post"


def test_scrape_blog_posts_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "newswire.sources.docusaurus_blog.requests.get",
        lambda *a, **k: (_ for _ in ()).throw(RequestException("network error")),
    )
    with pytest.raises(SourceError):
        scrape_blog_posts("https://docs.getdbt.com/blog")


def test_check_cursor_diff_with_legacy_last_url(
    monkeypatch: pytest.MonkeyPatch, source_cfg
) -> None:
    _stub_get(monkeypatch, HTML)
    source = DocusaurusBlogSource(
        source_cfg("blog", options={"url": "https://docs.getdbt.com/blog"})
    )

    # Legacy 'last_url' entry still works as the cursor
    section, next_entry = source.check({"last_url": "https://docs.getdbt.com/blog/another-post"})
    assert [item.title for item in section.items] == ["Test Blog Post"]
    assert next_entry == {
        "cursor": "https://docs.getdbt.com/blog/test-post",
        "last_check": "2025-01-15T00:00:00.000Z",
    }

    # Newest already stored -> nothing, state untouched
    section, next_entry = source.check({"cursor": "https://docs.getdbt.com/blog/test-post"})
    assert section is None and next_entry is None

    # First run -> only the newest post counts
    section, _ = source.check(None)
    assert len(section.items) == 1
