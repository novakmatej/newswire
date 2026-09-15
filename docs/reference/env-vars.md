# Environment variables

Every variable the shipped configs reference. Newswire itself defines only `NOTIFIER_CONFIG`; the
rest exist because the config files reference them with `${...}` — rename or add your own freely.

| Variable | Used by | Required | What breaks without it |
| --- | --- | --- | --- |
| `NOTIFIER_CONFIG` | CLI | no | Falls back to `--config`, then `./config.yml` |
| `GIST_ID` | `state: github_gist` | yes* | Run fails at startup: state cannot load |
| `GIST_TOKEN` | `state: github_gist` | yes* | Run fails at startup: state cannot load |
| `GITHUB_TOKEN` | `github_releases` (optional), `github_discussions` (**required**) | mixed | Releases: 60 req/h anonymous rate limit. Discussions: the source fails — GraphQL rejects anonymous requests |
| `SLACK_WEBHOOK_URL` | `slack` notifier | yes* | Config load fails naming the variable |
| `TEAMS_WEBHOOK_URL` | `teams` notifier | yes* | Config load fails naming the variable |

\* required only while the entry referencing it is `enabled: true`. Disabled entries skip
`${...}` interpolation entirely, so you can ship a config with channels switched off and no
variables set for them.

An empty string counts as unset — the run fails loudly rather than posting to an empty URL.

## The Actions `GITHUB_TOKEN` is not enough for discussions

`secrets.GITHUB_TOKEN` in GitHub Actions is scoped to the repository the workflow runs in. The
`github_discussions` source queries *another* repo's discussions over GraphQL, which that token
cannot do.

1. Create a fine-grained PAT (or classic PAT with `public_repo`).
2. Save it as a repository secret, e.g. `GH_PAT`.
3. Pass it into the run as `GITHUB_TOKEN`:

```yaml
env:
  GITHUB_TOKEN: ${{ secrets.GH_PAT }}
```

Locally, put the variables in `.env` (loaded automatically) — start from `.env.example`.

Next: [../guides/github-actions.md](../guides/github-actions.md),
[../configuration.md](../configuration.md)
