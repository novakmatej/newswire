# Deploy on GitHub Actions

The primary deployment: a scheduled workflow runs newswire and posts the digest. This repo's own
[`pipeline.yml`](../../.github/workflows/pipeline.yml) is the working reference.

1. Fork or clone this repo into your own GitHub repository.
2. Edit the `config/` directory in the repo root (`sources.yml`, `notifiers.yml`, `state.yml`,
   `config.yml`) — pick sources, notifiers, digest title. Commit it; it contains `${...}`
   references, never secrets.
3. Create a Gist for state: <https://gist.github.com> → any filename → content `{}`. Note the id
   from its URL.
4. Create a PAT with the `gist` scope: Settings → Developer settings → Personal access tokens.
5. Add repository secrets (Settings → Secrets and variables → Actions):

   | Secret | Value |
   | --- | --- |
   | `GIST_ID` | the id from step 3 |
   | `GIST_TOKEN` | the PAT from step 4 |
   | `SLACK_WEBHOOK_URL` | your webhook ([slack.md](slack.md)) |
   | `GITHUB_TOKEN` | a PAT — required for `github_discussions`, see below |

   Add `TEAMS_WEBHOOK_URL` only when your config enables the Teams channel.
6. Check the workflow schedule in `.github/workflows/pipeline.yml` (`0 7 * * 1` = Mondays
   07:00 UTC) and adjust the `env:` block to the secrets your config needs.
7. Trigger a first run manually: Actions → News Notifier → Run workflow.

## The token caveat

The Actions built-in `secrets.GITHUB_TOKEN` cannot read discussions on another org's repo. If your
config uses `github_discussions`, store a PAT under a secret name of your choice (e.g. `GH_PAT`)
and map it in the workflow:

```yaml
env:
  GITHUB_TOKEN: ${{ secrets.GH_PAT }}
```

Details: [../reference/env-vars.md](../reference/env-vars.md).

## Verifying a run

1. Open the run log: it prints each source checked, the item counts, and each notifier it sent to.
2. A failing source or channel prints a `Warning:` line and exits the run with code 1 — the rest
   still goes out, and undelivered items are re-sent next run.

Next: [local.md](local.md), [docker.md](docker.md)
