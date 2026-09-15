# Configuration

The YAML config is the whole interface: which sources run, where they post, in what order.
Start from [`config.example.yml`](../config.example.yml).

## Top-level blocks

| Block | Type | Required | Description |
| --- | --- | --- | --- |
| `defaults` | mapping | no | Shared defaults; currently just `timeout` (seconds, default `10`) |
| `digest` | mapping | no | `title` (headers/subjects, default `News`) and `intro` (greeting line, default `Here's what's been happening:`) |
| `state` | mapping | **yes** | `backend` + `options` — see [reference/state.md](reference/state.md) |
| `sources` | list | yes | What to check. **List order is digest order.** |
| `notifiers` | list | yes | Where to post — see [reference/notifiers.md](reference/notifiers.md) |

## Keys every source entry takes

| Key | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | string | yes | — | Unique. Also the state key — renaming re-notifies from scratch |
| `type` | string | yes | — | A registered source type — see [reference/sources.md](reference/sources.md) |
| `enabled` | bool | no | `true` | `false` skips the source; its state key is left untouched |
| `title` | string | no | the `id` | Section heading in the digest |
| `emoji` | string | no | — | Prepended to the heading |
| `notify` | list | no | all enabled notifiers | Notifier ids this source posts to — see [routing.md](routing.md) |
| `options` | mapping | no | `{}` | Type-specific options |

## Keys every notifier entry takes

| Key | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | string | yes | — | Unique; what `notify:` refers to |
| `type` | string | yes | — | A registered notifier type |
| `enabled` | bool | no | `true` | `false` skips the channel |
| `send_no_news` | bool | no | `true` | Post a "no news" message when nothing is new; `false` stays quiet |
| `options` | mapping | no | `{}` | Type-specific options |

## `${ENV_VAR}` interpolation

- Works in every string value. Secrets never live in the file itself.
- A referenced variable that is unset **or empty** fails the load, naming the variable and the
  config entry: `config.yml: notifier 'slack': environment variable SLACK_WEBHOOK_URL is not set`.
- Disabled entries are not interpolated, so `enabled: false` entries may reference unset variables.
- There is no other templating: no `include:`, no defaults-in-place, no cross-file references.

## Validation

The config is validated on load; errors are one human-readable line pointing at the offending
file and key, never a traceback. Checked: unknown top-level keys, unknown entry keys, duplicate
ids, unknown `type:` values, `notify:` ids that match no notifier, missing required options.

Next: [config-layout.md](config-layout.md), [routing.md](routing.md)
