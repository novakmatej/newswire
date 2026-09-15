"""Orchestration: routing, per-notifier digests, delivery-aware state, dry-run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from newswire.config import (
    Config,
    ConfigError,
    DigestConfig,
    NotifierConfig,
    SourceConfig,
    StateConfig,
)
from newswire.core import run
from newswire.models import LINKS, Item, Section
from newswire.notifiers.base import NotificationError
from newswire.registry import NOTIFIER_TYPES, SOURCE_TYPES
from newswire.sources.base import SourceError, new_by_seen, read_seen


class FakeSource:
    """Seen-set source emitting the titles configured in options['items']."""

    def __init__(self, cfg: SourceConfig):
        self.id = cfg.id
        self.title = cfg.title
        self.items = cfg.options.get("items", [])
        self.fail = cfg.options.get("fail", False)

    def check(self, entry: dict[str, Any] | None):
        if self.fail:
            raise SourceError("fetch blew up")
        new_titles = new_by_seen(self.items, read_seen(entry))
        next_entry = {"seen": list(self.items)}
        if not new_titles:
            return None, next_entry
        section = Section(
            source_id=self.id,
            title=self.title,
            kind=LINKS,
            items=tuple(Item(title=t, url=f"https://x/{t}") for t in new_titles),
        )
        return section, next_entry


class FakeNotifier:
    """Records sent digests on a shared log; optionally fails."""

    log: list[tuple[str, Any]] = []

    def __init__(self, cfg: NotifierConfig, digest: DigestConfig):
        self.id = cfg.id
        self.send_no_news_enabled = cfg.send_no_news
        self.fail = cfg.options.get("fail", False)

    def send_digest(self, sections):
        if self.fail:
            raise NotificationError("channel down")
        FakeNotifier.log.append((self.id, [s.source_id for s in sections]))

    def send_section(self, section):
        FakeNotifier.log.append((self.id, section.source_id))

    def send_no_news(self):
        if self.fail:
            raise NotificationError("channel down")
        FakeNotifier.log.append((self.id, "no-news"))


@pytest.fixture(autouse=True)
def fake_types(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(SOURCE_TYPES, "fake", FakeSource)
    monkeypatch.setitem(NOTIFIER_TYPES, "fake", FakeNotifier)
    FakeNotifier.log = []


def make_config(
    tmp_path: Path,
    sources: list[SourceConfig],
    notifiers: list[NotifierConfig],
    state: dict | None = None,
) -> Config:
    state_path = tmp_path / "state.json"
    if state is not None:
        state_path.write_text(json.dumps(state), encoding="utf-8")
    return Config(
        state=StateConfig(backend="local_file", options={"path": str(state_path)}),
        digest=DigestConfig(),
        sources=tuple(sources),
        notifiers=tuple(notifiers),
    )


def src(source_id: str, items: list[str], **kwargs) -> SourceConfig:
    options = {"items": items, **kwargs.pop("options", {})}
    return SourceConfig(id=source_id, type="fake", title=source_id, options=options, **kwargs)


def chan(notifier_id: str, **kwargs) -> NotifierConfig:
    return NotifierConfig(id=notifier_id, type="fake", **kwargs)


def read_state(tmp_path: Path) -> dict:
    path = tmp_path / "state.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def test_digest_assembled_per_notifier_in_config_order(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        sources=[
            src("cloud", ["c1"]),
            src("core", ["r1"], notify=("slack-data",)),
            src("blog", ["b1"]),
        ],
        notifiers=[chan("slack-data"), chan("slack-platform")],
    )

    assert run(config) == 0

    sent = dict(FakeNotifier.log)
    # omitted notify -> every enabled notifier; explicit notify -> only that one
    assert sent["slack-data"] == ["cloud", "core", "blog"]  # config order = digest order
    assert sent["slack-platform"] == ["cloud", "blog"]
    # both sources' state written
    assert read_state(tmp_path)["core"] == {"seen": ["r1"]}


def test_source_order_in_config_is_digest_order(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        sources=[src("z-last", ["1"]), src("a-first", ["2"])],
        notifiers=[chan("chan")],
    )
    run(config)
    assert dict(FakeNotifier.log)["chan"] == ["z-last", "a-first"]


def test_no_news_respects_per_notifier_flag(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        sources=[src("quiet", [])],
        notifiers=[chan("loud"), chan("silent", send_no_news=False)],
    )
    run(config)
    assert FakeNotifier.log == [("loud", "no-news")]


def test_failed_delivery_blocks_state_advance(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        sources=[src("core", ["r1"])],
        notifiers=[chan("ok"), chan("down", options={"fail": True})],
    )

    assert run(config) == 1  # partial failure surfaces in the exit code

    # 'ok' got the digest, but state must NOT advance - 'down' never received it
    assert dict(FakeNotifier.log)["ok"] == ["core"]
    assert "core" not in read_state(tmp_path)


def test_failed_delivery_on_unrouted_channel_does_not_block(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        sources=[src("core", ["r1"], notify=("ok",)), src("other", ["x1"], notify=("down",))],
        notifiers=[chan("ok"), chan("down", options={"fail": True})],
    )

    run(config)

    state = read_state(tmp_path)
    assert state["core"] == {"seen": ["r1"]}  # its only channel delivered
    assert "other" not in state  # its only channel failed


def test_source_failure_isolated_and_state_untouched(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        sources=[src("broken", [], options={"fail": True}), src("fine", ["f1"])],
        notifiers=[chan("chan")],
        state={"broken": {"seen": ["old"]}},
    )

    assert run(config) == 1

    assert dict(FakeNotifier.log)["chan"] == ["fine"]
    state = read_state(tmp_path)
    assert state["broken"] == {"seen": ["old"]}  # untouched
    assert state["fine"] == {"seen": ["f1"]}


def test_disabled_source_keeps_leftover_state_key(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        sources=[src("off", ["x"], enabled=False), src("on", ["y"])],
        notifiers=[chan("chan")],
        state={"off": {"seen": ["x"]}, "unknown-key": {"seen": ["z"]}},
    )

    assert run(config) == 0

    state = read_state(tmp_path)
    assert state["off"] == {"seen": ["x"]}  # leftover keys survive untouched
    assert state["unknown-key"] == {"seen": ["z"]}


def test_seen_set_state_refreshes_even_without_news(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        sources=[src("webinars", ["w1", "w2"])],
        notifiers=[chan("chan")],
        state={"webinars": {"seen": ["w1", "w2", "w-gone"]}},
    )
    run(config)
    # nothing new, but the disappeared item is dropped from state
    assert read_state(tmp_path)["webinars"] == {"seen": ["w1", "w2"]}


def test_dry_run_sends_nothing_and_writes_no_state(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    config = make_config(
        tmp_path,
        sources=[src("core", ["r1"])],
        notifiers=[chan("chan")],
    )

    assert run(config, dry_run=True) == 0

    assert FakeNotifier.log == []
    assert not (tmp_path / "state.json").exists()
    out = capsys.readouterr().out
    assert "dry-run: notifier 'chan'" in out
    assert "r1" in out


def test_only_filter_checks_selected_source_and_skips_no_news(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        sources=[src("core", []), src("blog", [])],
        notifiers=[chan("chan")],
    )
    run(config, only=["core"])
    assert FakeNotifier.log == []  # nothing new and no-news suppressed with --source

    with pytest.raises(ConfigError, match="--source 'nope'"):
        run(config, only=["nope"])


def test_no_enabled_notifiers_fails(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        sources=[src("core", ["x"])],
        notifiers=[chan("chan", enabled=False)],
    )
    with pytest.raises(ConfigError, match="no enabled notifiers"):
        run(config)


def test_unknown_type_fails_with_known_list(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        sources=[SourceConfig(id="x", type="does_not_exist")],
        notifiers=[chan("chan")],
    )
    with pytest.raises(ConfigError, match="unknown source type 'does_not_exist'"):
        run(config)


def test_no_state_write_sends_but_keeps_state(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        sources=[src("core", ["r1"])],
        notifiers=[chan("chan")],
        state={"core": {"seen": []}},
    )

    assert run(config, write_state=False) == 0

    assert dict(FakeNotifier.log)["chan"] == ["core"]  # really sent
    assert read_state(tmp_path) == {"core": {"seen": []}}  # state untouched
