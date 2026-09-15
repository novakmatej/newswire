"""Orchestration: load state, check every source, route, send, persist.

Delivery/state contract: a source's state entry is advanced only when every
enabled notifier it routes to accepted the digest. A failed channel therefore
means the items are re-sent on the next run - to every routed channel, so
delivery is at-least-once, never lost (this fixes the pre-1.0 defect where
state advanced even when a channel was down).
"""

from __future__ import annotations

from typing import Sequence

# Importing the packages runs the registry registrations.
import newswire.notifiers  # noqa: F401
import newswire.sources  # noqa: F401
import newswire.state  # noqa: F401
from newswire.config import Config, ConfigError, SourceConfig
from newswire.models import Section
from newswire.notifiers.base import NotificationError, Notifier
from newswire.registry import NOTIFIER_TYPES, SOURCE_TYPES, STATE_BACKENDS, resolve
from newswire.sources.base import SourceError


def _routed_ids(source: SourceConfig, enabled_notifier_ids: set[str]) -> set[str]:
    """Enabled notifier ids a source is routed to (omitted notify = all enabled)."""
    if source.notify is None:
        return set(enabled_notifier_ids)
    return set(source.notify) & enabled_notifier_ids


def render_text(sections: Sequence[Section]) -> str:
    """Plain-text rendering of sections, used by --dry-run."""
    lines = []
    for section in sections:
        heading = f"{section.emoji} {section.title}" if section.emoji else section.title
        lines.append(f"## {heading}  [{section.source_id}, {section.kind}]")
        if section.subtitle:
            lines.append(f"   {section.subtitle}")
        for item in section.items:
            suffix = f" <{item.url}>" if item.url else ""
            tag = ""
            if section.kind == "cards" and item.tag and item.tag not in item.title:
                tag = f"{item.tag} "
            lines.append(f"   • {tag}{item.title}{suffix}")
        if section.link:
            lines.append(f"   (view all: {section.link})")
    return "\n".join(lines)


def run(
    config: Config,
    *,
    dry_run: bool = False,
    only: Sequence[str] | None = None,
    write_state: bool = True,
) -> int:
    """One full run. Returns a process exit code (0 = clean, 1 = partial failure).

    With ``dry_run`` nothing is sent and state is not written. With ``only``,
    just the named source ids are checked and "no news" messages are skipped.
    With ``write_state=False`` (--no-state-write) items are really sent but the
    state stays untouched, so the next run reports them as new again.
    """
    source_cfgs = list(config.enabled_sources())
    if only:
        known = {cfg.id for cfg in source_cfgs}
        for source_id in only:
            if source_id not in known:
                raise ConfigError(
                    f"--source '{source_id}' does not match an enabled source id "
                    f"(enabled: {', '.join(sorted(known)) or 'none'})"
                )
        source_cfgs = [cfg for cfg in source_cfgs if cfg.id in set(only)]
    if not source_cfgs:
        raise ConfigError("no enabled sources - enable at least one in the config")

    notifier_cfgs = list(config.enabled_notifiers())
    if not notifier_cfgs:
        raise ConfigError("no enabled notifiers - enable at least one in the config")

    sources = [(cfg, resolve(SOURCE_TYPES, cfg.type, "source")(cfg)) for cfg in source_cfgs]
    notifiers: list[tuple[str, Notifier]] = [
        (cfg.id, resolve(NOTIFIER_TYPES, cfg.type, "notifier")(cfg, config.digest))
        for cfg in notifier_cfgs
    ]
    backend = resolve(STATE_BACKENDS, config.state.backend, "state backend")(config.state)
    enabled_notifier_ids = {notifier_id for notifier_id, _ in notifiers}

    state = backend.load()
    errors: list[str] = []
    results: list[tuple[SourceConfig, Section | None, dict | None]] = []
    for cfg, source in sources:
        try:
            section, next_entry = source.check(state.get(cfg.id))
        except SourceError as exc:
            message = f"source '{cfg.id}' failed: {exc}"
            print(f"Warning: {message}")
            errors.append(message)
            continue
        results.append((cfg, section, next_entry))
        count = len(section.items) if section else 0
        print(f"Checked '{cfg.id}': {count} new item(s)")

    delivered_ok: dict[str, bool] = {}
    for notifier_id, notifier in notifiers:
        digest_sections = [
            section
            for cfg, section, _ in results
            if section is not None and notifier_id in _routed_ids(cfg, enabled_notifier_ids)
        ]
        if dry_run:
            print(f"\n=== dry-run: notifier '{notifier_id}' ===")
            if digest_sections:
                print(render_text(digest_sections))
            elif only:
                print("(nothing new for the selected sources)")
            elif notifier.send_no_news_enabled:
                print("(nothing new - would send the 'no news' message)")
            else:
                print("(nothing new - would stay quiet, send_no_news is off)")
            continue

        if digest_sections:
            try:
                notifier.send_digest(digest_sections)
                delivered_ok[notifier_id] = True
                print(f"Sent {len(digest_sections)} section(s) to '{notifier_id}'")
            except NotificationError as exc:
                delivered_ok[notifier_id] = False
                message = f"notifier '{notifier_id}' failed: {exc}"
                print(f"Warning: {message}")
                errors.append(message)
        else:
            delivered_ok[notifier_id] = True  # nothing owed to this channel
            if notifier.send_no_news_enabled and not only:
                try:
                    notifier.send_no_news()
                    print(f"Sent 'no news' to '{notifier_id}'")
                except NotificationError as exc:
                    # Nothing to resend, so this never blocks state.
                    print(f"Warning: 'no news' via '{notifier_id}' failed: {exc}")

    if not dry_run and not write_state:
        print("State not written (--no-state-write); this run's items stay marked as new")
    if not dry_run and write_state:
        changed = False
        for cfg, section, next_entry in results:
            if next_entry is None:
                continue
            if section is not None:
                targets = _routed_ids(cfg, enabled_notifier_ids)
                if not all(delivered_ok.get(target, False) for target in targets):
                    print(
                        f"State for '{cfg.id}' not advanced (delivery failed); "
                        "its items will be re-sent next run"
                    )
                    continue
            state[cfg.id] = next_entry
            changed = True
        if changed:
            backend.save(state)

    return 1 if errors else 0
