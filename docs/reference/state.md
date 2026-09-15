# State backends

Where newswire remembers what it already sent: one JSON document, keyed by source `id`.

Two rules worth knowing:

- **The source `id` is the state key.** Rename a source and it starts from scratch (and re-notifies
  its first-run set). Keep ids stable.
- A state entry is advanced only after every notifier the source routes to accepted the digest.
  A failed channel means the items are re-sent to all routed channels next run (at-least-once).

## `github_gist`

The state document lives in a GitHub Gist — works from GitHub Actions and from several machines.

| Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `gist_id` | string | yes | — | Id from the gist URL |
| `token` | string | yes | — | PAT with the `gist` scope |
| `filename` | string | no | `state.json` | File name inside the gist; must match an existing deployment's file |
| `timeout` | number | no | `defaults.timeout` | Request timeout in seconds |

```yaml
state:
  backend: github_gist
  options:
    gist_id: ${GIST_ID}
    token: ${GIST_TOKEN}
    filename: dbt-news-state.json
```

Create the gist once (any content, e.g. `{}`), secret or public — the token does the writing.

## `local_file`

The state document is a JSON file on disk — for local runs, cron on one machine, or a Docker
volume. Parent directories are created on first save; a missing file means empty state.

| Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `path` | string | yes | — | Path to the JSON file |

```yaml
state:
  backend: local_file
  options:
    path: state.json
```

Do not use `local_file` in GitHub Actions — the runner's disk is thrown away after every run and
each run would re-notify everything.

Next: [env-vars.md](env-vars.md), [../configuration.md](../configuration.md)
