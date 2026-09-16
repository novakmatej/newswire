# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository. (`AGENTS.md` points here for other agent tools.)

## Map — where to find what

| Task | Read first | Code |
| --- | --- | --- |
| Add a source type | `docs/add-a-source.md` | `src/newswire/sources/` + one import in its `__init__.py`; document in `docs/reference/sources.md` and both example configs (CI-enforced) |
| Add a notifier type | `docs/add-a-notifier.md` | `src/newswire/notifiers/` + import in `__init__.py`; document in `docs/reference/notifiers.md` |
| Add a state backend | `docs/reference/state.md` | `src/newswire/state/` + import in `__init__.py` |
| Config keys, `${ENV}` rules, validation | `docs/configuration.md`, `docs/config-layout.md` | `src/newswire/config.py` |
| Routing (`notify:`), per-notifier digests | `docs/routing.md` | `src/newswire/core.py` |
| Diff idioms + legacy state-field fallbacks | this file, Architecture | `src/newswire/sources/base.py` |
| Rendering model (Section/Item, 3 kinds) | this file, Architecture | `src/newswire/models.py`, `src/newswire/notifiers/base.py` |
| CLI flags, exit codes | `docs/reference/cli.md` | `src/newswire/cli.py` |
| Env vars | `docs/reference/env-vars.md` | — |
| Deployment (Actions/Docker/local) | `docs/guides/` | `.github/workflows/pipeline.yml`, `Dockerfile` |
| Releases + changelog labels | `docs/releasing.md` | `.chronicle.yaml`, `.github/workflows/release.yml` |
| Live deployment config | — | `config/` (ids = state keys, do not rename) |
| Symptom → fix | `docs/troubleshooting.md` | — |

Tests mirror the layout: `tests/test_source_*.py`, `tests/test_notifier_*.py`,
`tests/test_config.py`, `tests/test_core.py` (routing/state contract), `tests/test_examples.py`
and `tests/test_docs_coverage.py` (docs-rot guards).

## Commands

```bash
uv sync                                   # install incl. dev tools (PEP 735 dev group)
uv run pytest                             # all tests (network is mocked everywhere)
uv run pytest tests/test_core.py::test_failed_delivery_blocks_state_advance   # one test
uv run ruff check . && uv run ruff format .
uv run newswire --config config/ --dry-run      # fetches live pages, sends nothing, writes no state
uv run newswire --config config/                # REAL run: posts to the channels in config/ and writes state
uv run newswire --config config/ --source dbt-core-releases --dry-run       # one source only
```

CI (`.github/workflows/ci.yml`) runs ruff + pytest on every PR and push to `main`. The scheduled
job (`pipeline.yml`) runs Mondays 07:00 UTC with the committed `config.yml`. `release.yml` fires
on `v*` tags and builds release notes with chronicle (label mapping in `.chronicle.yaml`;
process in `docs/releasing.md`).

## Workflow rules

- Every change goes through a feature branch and conventional commits (`feat:`, `fix:`, `docs:`,
  `test:`). PR titles use the same convention — chronicle reads them for release notes.
- **Never merge locally and never push to `main`.** `main` only moves through a PR merged on
  GitHub. **Do not push at all** — the author reviews commits locally first.
- Never run `newswire` without `--dry-run` unless the maintainer has confirmed which config and
  which notifier ids the run will hit.
- Docs and code comments in English.

## Architecture

One pass, four stages: `config.py` loads and validates YAML → `core.run()` orchestrates →
`sources/*` fetch and diff → `notifiers/*` render and send; `state/*` persists what was sent.

- **`config.py`** — the whole interface. Loads a file or a config directory (file name = top-level
  key, `<key>.d/` fragments, lexicographic order, lists concatenate, mappings merge). `${ENV_VAR}`
  interpolation on enabled entries only; validation errors name file + key. No pydantic —
  hand-rolled on purpose.
- **`registry.py`** — three dicts (`SOURCE_TYPES`, `NOTIFIER_TYPES`, `STATE_BACKENDS`) filled by
  decorators at import time (the package `__init__`s import every module). Adding a type = one
  module + one import line + a reference-docs entry (`tests/test_docs_coverage.py` fails CI
  otherwise) + an example-config entry (`tests/test_examples.py`).
- **`models.py`** — the normalised layer: sources emit `Section`s of `Item`s with a render `kind`
  (`cards` = per-release card, `links` = title+url bullets, `notes` = markdown bullets + subtitle +
  footer). Which sections exist and their order is config; per-channel payloads stay separate
  implementations by design (Block Kit vs Adaptive Card genuinely differ).
- **`sources/*`** — each type implements `check(state_entry) -> (Section | None, next_entry |
  None)`. Three diff idioms live in `sources/base.py` and are not interchangeable: cursor
  (releases, docusaurus blog), seen-set (discussions, html_list), section compare
  (dbt_cloud_release_notes). `read_cursor`/`read_seen` also accept the pre-1.0 field names (`last_id`,
  `last_url`, `urls`, `last_urls`, `numbers`) so an old Gist migrates in place — keep that.
- **`state/*`** — one JSON document keyed by **source id**. Renaming a source id resets its
  history. (The `type:` of a source is not part of state — renaming a type is safe.)
- **`core.run()`** — routing (`notify:`, omitted = all enabled notifiers) and the delivery
  contract: a source's state entry advances only when every routed notifier accepted the digest
  (at-least-once delivery; this replaced the old fire-and-forget defect). Source failures are
  isolated warnings; the run exits 1 if anything failed.
- **`notifiers/*`** — each type implements `send_digest(sections)`, `send_section(section)`,
  `send_no_news()` and renders all three kinds. Gotchas that must survive refactors: Teams targets
  a *Workflow* webhook (Adaptive Card, chunked under ~25 KB, oversized sections split by line);
  Slack enforces 3000 chars per section text and 50 blocks per message, so bullet lists are split
  into multiple blocks and oversized digests into multiple posts (a first run trips this
  otherwise - Slack answers 400 invalid_payload).
  The Resend email notifier was removed in the rewrite review — if email ever comes back, it must
  use the Broadcasts API for unsubscribe links and must **never extract inner HTML with regexes**
  (that made digest sections nest deeper and deeper before the rewrite).

Ruff: line-length 100, rules `E,F,B,I`.

## Configs in the repo

- `config/` — the live dbt deployment, split by concern (`config.yml` = defaults + digest,
  `state.yml`, `notifiers.yml`, `sources.yml`); used by `pipeline.yml`. Source ids are state
  keys: do not rename them.
- `config.example.yml` + `config.example/` — the same example in both layouts; a test asserts
  they load equal and that every registered type appears in them.
