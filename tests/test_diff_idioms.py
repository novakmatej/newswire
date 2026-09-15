"""The three diff idioms and the legacy state-field fallbacks."""

from __future__ import annotations

from newswire.sources.base import new_by_cursor, new_by_seen, read_cursor, read_seen
from newswire.sources.dbt_cloud_release_notes import find_changes_in_section


def test_new_by_cursor() -> None:
    tags = ["v3", "v2", "v1"]
    # Stored tag found -> everything before it is new
    assert new_by_cursor(tags, "v2") == 1
    # Newest already stored -> nothing new
    assert new_by_cursor(tags, "v3") == 0
    # Stored tag gone from the list -> everything is new
    assert new_by_cursor(tags, "v0") == 3
    # First run -> only the newest counts
    assert new_by_cursor(tags, None) == 1
    # Empty list
    assert new_by_cursor([], None) == 0
    assert new_by_cursor([], "v1") == 0


def test_new_by_seen() -> None:
    urls = ["u1", "u2", "u3"]
    assert new_by_seen(urls, {"u2", "u3"}) == ["u1"]
    assert new_by_seen(urls, set()) == urls
    assert new_by_seen(urls, {"u1", "u2", "u3", "u-removed"}) == []


def test_read_cursor_falls_back_to_legacy_fields() -> None:
    assert read_cursor({"cursor": "v3"}) == "v3"
    assert read_cursor({"last_id": "v2"}) == "v2"  # pre-1.0 releases key
    assert read_cursor({"last_url": "https://x/post"}) == "https://x/post"  # pre-1.0 blog key
    assert read_cursor({}) is None
    assert read_cursor(None) is None


def test_read_seen_falls_back_to_legacy_fields() -> None:
    assert read_seen({"seen": ["a", "b"]}) == {"a", "b"}
    assert read_seen({"last_urls": ["a"]}) == {"a"}  # pre-1.0 blog categories
    assert read_seen({"urls": ["a"]}) == {"a"}  # pre-1.0 webinars
    assert read_seen({"numbers": [1, 2]}) == {"1", "2"}  # pre-1.0 discussions
    assert read_seen(None) == set()


def test_section_compare_no_previous_state() -> None:
    changes = find_changes_in_section("November 2025", ["Item 1", "Item 2"], None, None)
    assert changes == ("November 2025", ("Item 1", "Item 2"), True)


def test_section_compare_new_heading() -> None:
    changes = find_changes_in_section("December 2025", ["Item 1"], "November 2025", ["Old item"])
    assert changes == ("December 2025", ("Item 1",), True)


def test_section_compare_same_heading_new_items() -> None:
    changes = find_changes_in_section(
        "November 2025", ["Item 1", "Item 2", "Item 3"], "November 2025", ["Item 1", "Item 2"]
    )
    assert changes == ("November 2025", ("Item 3",), False)


def test_section_compare_no_changes() -> None:
    assert (
        find_changes_in_section(
            "November 2025", ["Item 1", "Item 2"], "November 2025", ["Item 1", "Item 2"]
        )
        is None
    )


def test_section_compare_item_changed() -> None:
    changes = find_changes_in_section(
        "November 2025", ["Item 1", "Item 3"], "November 2025", ["Item 1", "Item 2"]
    )
    assert changes is not None
    heading, new_items, is_new = changes
    assert "Item 3" in new_items
    assert "Item 2" not in new_items
    assert is_new is False
