# Add a source type

A source type is one module: a class with a `check()` method, registered under a name. No edits to
orchestration code or to any notifier.

1. Create `src/newswire/sources/my_feed.py`:

   ```python
   from typing import Any

   from newswire.config import ConfigError, SourceConfig
   from newswire.models import LINKS, Item, Section
   from newswire.registry import source_type
   from newswire.sources.base import SourceError, new_by_seen, read_seen


   @source_type("my_feed")
   class MyFeedSource:
       def __init__(self, cfg: SourceConfig):
           self.id = cfg.id
           self.title = cfg.title
           self.emoji = cfg.emoji
           self.url = cfg.options.get("url")
           if not self.url:
               raise ConfigError(f"source '{cfg.id}': my_feed requires option 'url'")

       def check(self, entry: dict[str, Any] | None):
           items = self._fetch()  # -> list[Item]; raise SourceError on failure
           new_ids = set(new_by_seen([i.url for i in items], read_seen(entry)))
           new = [i for i in items if i.url in new_ids]
           next_entry = {"seen": [i.url for i in items]}
           if not new:
               return None, next_entry
           return Section(
               source_id=self.id, title=self.title, kind=LINKS,
               items=tuple(new), emoji=self.emoji,
           ), next_entry
   ```

2. Register the import in `src/newswire/sources/__init__.py` (one line in the import list).
3. Document it in [reference/sources.md](reference/sources.md) — a CI test fails if a registered
   type has no reference entry.
4. Add it to `config.example.yml` and `config.example/` (another test checks every type appears).
5. Test with mocked HTTP — see `tests/test_source_html_list.py` for the pattern.

## The contract

- `check(entry)` returns `(Section | None, next_entry | None)`: the section holds only *new* items;
  `next_entry` replaces the stored state entry, `None` leaves it untouched.
- Pick a diff idiom from `newswire.sources.base`: `new_by_cursor` (newest-first feeds),
  `new_by_seen` (unordered sets). Raise `SourceError` on fetch/parse failure — the run isolates it.
- Pick a render `kind`: `cards` (rich per-item body), `links` (title+url bullets), `notes`
  (markdown text bullets + subtitle + footer link). All notifiers already render all three.

Next: [add-a-notifier.md](add-a-notifier.md), [reference/sources.md](reference/sources.md)
