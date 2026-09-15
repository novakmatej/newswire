# Routing: each source picks its channels

Send dbt news to one Slack channel, Airflow news to another, some sources to both.

## How

1. Give every notifier an `id`. Two `slack` entries with different webhooks are two channels.
2. Add `notify: [<notifier-id>, ...]` to a source that should not go everywhere.
3. Omit `notify` for the common case — the source posts to **every enabled notifier**.

```yaml
sources:
  - id: dbt-core-releases        # no notify: -> both channels
    type: github_releases
    options: {repo: dbt-labs/dbt-core}

  - id: airflow-releases
    type: github_releases
    notify: [slack-platform]     # only this channel
    options: {repo: apache/airflow}

notifiers:
  - id: slack-data
    type: slack
    options: {webhook_url: ${SLACK_WEBHOOK_DATA}}
  - id: slack-platform
    type: slack
    options: {webhook_url: ${SLACK_WEBHOOK_PLATFORM}}
```

## Rules

- An unknown id in `notify` is a config error at load time, naming the source and the id.
- Pointing `notify` at a disabled notifier is allowed; that route is simply inactive.
- **The digest is assembled per notifier** from the sources routed to it, in `sources` order.
  There is no global digest.
- A notifier whose sources produced nothing sends its "no news" message — or nothing, with
  `send_no_news: false`.
- State stays keyed by source: a source is fetched once and feeds every channel it routes to.
  Adding a notifier to an existing source means that channel starts from *now* — it is not
  backfilled.
- Delivery is at-least-once: if one routed channel fails, the source's state is not advanced and
  the items go out again next run — to every routed channel, including those that already got them.

Next: [reference/notifiers.md](reference/notifiers.md), [guides/slack.md](guides/slack.md)
