# Documentation map

One line per page. Start with the README quickstart, then come back here.

## Configure

- [configuration.md](configuration.md) — top-level keys, entry keys, `${ENV}` rules, validation
- [config-layout.md](config-layout.md) — single file vs `config/` directory, naming, merge order
- [routing.md](routing.md) — sending different sources to different channels

## Reference

- [reference/cli.md](reference/cli.md) — every flag, exit codes, what a run does
- [reference/sources.md](reference/sources.md) — every source type + its options
- [reference/notifiers.md](reference/notifiers.md) — every notifier type + its options
- [reference/state.md](reference/state.md) — every state backend + its options
- [reference/env-vars.md](reference/env-vars.md) — every environment variable, who needs it

## Deploy

- [guides/github-actions.md](guides/github-actions.md) — the primary deployment, step by step
- [guides/docker.md](guides/docker.md) — Docker image + host cron
- [guides/local.md](guides/local.md) — run on your machine with `.env` and `--dry-run`

## Channels

- [guides/slack.md](guides/slack.md) — webhook setup, multiple channels
- [guides/teams.md](guides/teams.md) — Workflow/Power Automate webhook (not the retired connector)

## Extend

- [add-a-source.md](add-a-source.md) — new source type: one module + one registry line
- [add-a-notifier.md](add-a-notifier.md) — new notifier type

## Maintain

- [releasing.md](releasing.md) — labels → chronicle → tag → GitHub Release
- [troubleshooting.md](troubleshooting.md) — symptom → cause → fix
- [migrating-from-0.0.1.md](migrating-from-0.0.1.md) — for pre-rewrite deployments
