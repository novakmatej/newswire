# Contributing

1. Branch from `main`; `main` only moves through merged PRs.
2. Use conventional commits (`feat:`, `fix:`, `docs:`, `test:`) — **and the same convention in the
   PR title**: chronicle builds release notes from PR titles when a PR carries no label.
3. Label the PR (or rely on the title prefix) so it appears in the changelog: `enhancement` /
   `feature` → Added Features, `bug` / `fix` → Bug Fixes, `breaking-change` → Breaking Changes,
   `security` → Security Fixes. A PR with neither a label nor a `feat:`/`fix:`/`perf:`/`!` title
   produces **no changelog entry**. Details: [docs/releasing.md](docs/releasing.md).
4. Before pushing:
   ```bash
   uv run ruff check . && uv run ruff format --check . && uv run pytest
   ```
5. Tests mock all network calls — no live APIs in the suite.
6. New source or notifier type? Follow [docs/add-a-source.md](docs/add-a-source.md) /
   [docs/add-a-notifier.md](docs/add-a-notifier.md) — including the reference-docs entry and the
   example config, both enforced by CI.
