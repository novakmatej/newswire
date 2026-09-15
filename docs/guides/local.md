# Run locally

Develop, debug, and test on your machine with `.env` and `--dry-run`.

1. Install:
   ```bash
   uv sync
   ```
2. Copy the env template and fill in what your config references:
   ```bash
   cp .env.example .env
   ```
3. Copy a config and adjust it:
   ```bash
   cp config.example.yml config.yml
   ```
4. Dry run — fetches and renders everything, sends nothing, writes no state:
   ```bash
   uv run newswire --config config.yml --dry-run
   ```
5. Real run:
   ```bash
   uv run newswire --config config.yml
   ```

## Flags

| Flag | Effect |
| --- | --- |
| `--config PATH` | Config file or directory. Default `config.yml`, or `$NOTIFIER_CONFIG` |
| `--dry-run` | Fetch + render, print per-notifier output, no sends, no state writes |
| `--source ID` | Check only this source (repeatable). Skips "no news" messages |
| `--no-state-write` | Send for real, but leave state (gist or file) untouched — the next run treats the same items as new. For testing real delivery without "using up" the news |

Debugging one source:

```bash
uv run newswire --config config.yml --dry-run --source dbt-core-releases
```

## Local state

Use the `local_file` backend while testing so you never touch a production Gist:

```yaml
state:
  backend: local_file
  options:
    path: state.test.json
```

First run with empty state is intentionally big: cursor sources send their newest item, seen-set
sources send everything they currently list.

Next: [../reference/env-vars.md](../reference/env-vars.md),
[github-actions.md](github-actions.md)
