# Slack setup

Get a webhook, wire it into the config — including several channels.

1. Open <https://api.slack.com/apps> → **Create New App** → From scratch.
2. Name it, pick your workspace.
3. In the app: **Incoming Webhooks** → toggle **On** → **Add New Webhook to Workspace**.
4. Pick the channel; copy the webhook URL (`https://hooks.slack.com/services/...`).
5. Store it in the environment (`.env` locally, a repository secret on Actions):
   ```
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T000/B000/xxxx
   ```
6. Reference it in the config:
   ```yaml
   notifiers:
     - id: slack
       type: slack
       options:
         webhook_url: ${SLACK_WEBHOOK_URL}
   ```

## Multiple channels

One webhook posts to one channel. For a second channel, repeat steps 3–5 for it and add a second
notifier entry:

```yaml
notifiers:
  - id: slack-data
    type: slack
    options: {webhook_url: ${SLACK_WEBHOOK_DATA}}
  - id: slack-platform
    type: slack
    options: {webhook_url: ${SLACK_WEBHOOK_PLATFORM}}
```

Then route sources with `notify: [slack-platform]` — see [../routing.md](../routing.md).

## Rendering notes

- Section headings come from each source's `title` + `emoji` in the config.
- Release cards show up to 3 bullets per Features/Fixes/... section, then "...and N more" with a
  link to the full notes.
- A channel with nothing new gets the "no news" message unless `send_no_news: false`.

Next: [../routing.md](../routing.md), [teams.md](teams.md)
