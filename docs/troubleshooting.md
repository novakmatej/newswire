# Troubleshooting

Symptom → cause → fix.

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Error: ...: environment variable X is not set` | An enabled entry references `${X}` and it is unset or empty | Set the variable, or set `enabled: false` on that entry |
| `Error: ...: config file or directory not found` | Wrong `--config` path or missing default `config.yml` | Pass `--config`, or set `NOTIFIER_CONFIG` |
| `unknown source type 'x'` | Typo in `type:`, or a custom type whose module is not imported | Check [reference/sources.md](reference/sources.md); register the import in the package `__init__` |
| `duplicate source id '...' in A and B` | The same id in two config fragments | Rename one — ids are state keys, so pick which keeps the history |
| `unexpected file in config directory` | A file that matches no config name (e.g. `sources.yaml.bak`) | Remove it, or rename it to a `<key>.yml` / `<key>.d/*.yml` name |
| `source '...' routes to unknown notifier id` | `notify:` names an id no notifier has | Fix the id; check `notifiers:` entries |
| Everything re-sent on every run | State never persists: wrong Gist id/token, or `local_file` on a throwaway disk (Actions) | Verify the state backend; use `github_gist` on Actions |
| One source re-notifies from scratch | Its `id` was renamed — the id is the state key | Restore the old id, or accept the one-time replay |
| `source 'x' failed: Failed to scrape ...` | Page markup changed (scrapers are coupled to it) | Adjust the selector options; see [reference/sources.md](reference/sources.md) |
| Discussions: `GraphQL errors` / token error | `github_discussions` has no token, or the Actions built-in token is used | Use a PAT — see [reference/env-vars.md](reference/env-vars.md) |
| GitHub sources: 403 / rate-limit errors | Anonymous REST calls (60 req/h) | Set `token: ${GITHUB_TOKEN}` on the source |
| Teams: nothing arrives, HTTP 400 | The retired O365 connector URL, not a Workflow webhook | Recreate via Workflows — see [guides/teams.md](guides/teams.md) |
| Teams: digest arrives as several messages | Payload chunking under the ~28 KB card limit | Expected behaviour, not a bug |
| Slack: digest arrives as several messages | Chunking under Slack's 50-blocks-per-message cap | Expected behaviour on big (first) runs |
| Items delivered twice to a healthy channel | Another routed channel failed last run; delivery is at-least-once | Fix the failing channel; duplicates stop |
| `no enabled notifiers` / `no enabled sources` | Everything is `enabled: false` | Enable at least one of each |
| Huge first digest | Empty state: seen-set sources send everything they currently list | Expected on first run; cursor sources send only their newest |

Still stuck? Run with `--dry-run --source <id>` to isolate one source without sending anything.

Next: [index.md](index.md), [guides/local.md](guides/local.md)
