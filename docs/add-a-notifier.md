# Add a notifier type

A notifier type is one module implementing three methods, registered under a name. Existing
notifiers and the orchestration stay untouched.

1. Create `src/newswire/notifiers/my_channel.py`:

   ```python
   from typing import Sequence

   from newswire.config import ConfigError, DigestConfig, NotifierConfig
   from newswire.models import Section
   from newswire.notifiers.base import NotificationError, heading_text
   from newswire.registry import notifier_type


   @notifier_type("my_channel")
   class MyChannelNotifier:
       def __init__(self, cfg: NotifierConfig, digest: DigestConfig):
           self.id = cfg.id
           self.send_no_news_enabled = cfg.send_no_news
           self.digest = digest
           self.url = cfg.options.get("url")
           if not self.url:
               raise ConfigError(f"notifier '{cfg.id}': my_channel requires option 'url'")

       def send_digest(self, sections: Sequence[Section]) -> None:
           text = "\n\n".join(self._render(s) for s in sections)
           self._post(f"{self.digest.title}\n\n{text}")  # raise NotificationError on failure

       def send_section(self, section: Section) -> None:
           self._post(self._render(section))

       def send_no_news(self) -> None:
           self._post("No new updates today.")

       def _render(self, section: Section) -> str:
           lines = [heading_text(section)]
           lines += [f"- {item.title} {item.url or ''}" for item in section.items]
           return "\n".join(lines)
   ```

2. Register the import in `src/newswire/notifiers/__init__.py`.
3. Document it in [reference/notifiers.md](reference/notifiers.md) — a CI test fails otherwise.
4. Add it (usually `enabled: false`) to `config.example.yml` and `config.example/`.
5. Test the payload shape with a mocked transport — see `tests/test_notifier_slack.py`.

## The contract

- Constructor gets `(NotifierConfig, DigestConfig)`; read options, validate, raise `ConfigError`
  for missing ones. Expose `id` and `send_no_news_enabled`.
- `send_digest(sections)` receives only the sections routed to this notifier, already in config
  order. Render all three kinds (`cards`, `links`, `notes`); helpers for parsing release bodies,
  markdown links, and leading tags live in `newswire.notifiers.base`.
- Raise `NotificationError` on delivery failure — the run then keeps state so the items are
  re-sent next run.

Next: [add-a-source.md](add-a-source.md), [reference/notifiers.md](reference/notifiers.md)
