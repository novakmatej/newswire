# Notifier types

Every `type:` a `notifiers:` entry can use, with its options. Common keys (`id`, `enabled`,
`send_no_news`) are in [configuration.md](../configuration.md).

Every notifier builds its own digest from the sources routed to it, in `sources` order, and has a
"no news" message controlled by `send_no_news`.

## `slack`

Incoming-webhook messages built from Block Kit blocks: headers, mrkdwn sections, dividers, links
as `<url|text>`. Slack's hard limits are respected automatically: long bullet lists are split
into multiple section blocks (3000-char text cap) and a digest over 50 blocks goes out as
several messages — a big first run arriving as more than one message is expected.

| Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `webhook_url` | string | yes | — | Slack incoming webhook |
| `timeout` | number | no | `defaults.timeout` | Request timeout in seconds |

```yaml
- id: slack
  type: slack
  options:
    webhook_url: ${SLACK_WEBHOOK_URL}
```

Failure mode: a non-2xx webhook response fails the send; state for the routed sources is not
advanced, so the items are re-sent next run. Setup: [guides/slack.md](../guides/slack.md).

## `teams`

Adaptive Card posts to a Teams **Workflow** (Power Automate) webhook — not the retired Office 365
connector. TextBlocks take a markdown subset (`**bold**`, `- bullets`, `[text](url)`; no headings,
no tables). Payloads are chunked under ~25 KB; an oversized section is split by line.

| Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `webhook_url` | string | yes | — | Teams Workflow webhook (see [guides/teams.md](../guides/teams.md)) |
| `timeout` | number | no | `defaults.timeout` | Request timeout in seconds |

```yaml
- id: teams
  type: teams
  send_no_news: false
  options:
    webhook_url: ${TEAMS_WEBHOOK_URL}
```

Failure mode: as Slack. A digest over the size limit goes out as several cards, which is normal.

Next: [sources.md](sources.md), [state.md](state.md)
