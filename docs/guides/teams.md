# Microsoft Teams setup

Newswire posts Adaptive Cards to a Teams **Workflow** (Power Automate) webhook. The old Office 365
"Incoming Webhook" connector is retired and its MessageCard format does not work here.

1. In Teams, open the target channel → **⋯** → **Workflows**.
2. Pick the template **"Post to a channel when a webhook request is received"**.
3. Accept the defaults, confirm the team/channel, and create the flow.
4. Copy the HTTP URL the wizard shows (`https://prod-XX....logic.azure.com:443/workflows/...`).
5. Store it in the environment:
   ```
   TEAMS_WEBHOOK_URL=https://prod-00.westeurope.logic.azure.com:443/workflows/...
   ```
6. Reference it in the config:
   ```yaml
   notifiers:
     - id: teams
       type: teams
       options:
         webhook_url: ${TEAMS_WEBHOOK_URL}
   ```

## Rendering notes

- Adaptive Card TextBlocks accept only a markdown subset: `**bold**`, `_italic_`, `- bullets`,
  `[text](url)`. No headings, no tables — section titles render as bold text.
- Teams rejects card payloads around 28 KB. Newswire chunks a digest into multiple cards under
  ~25 KB and splits an oversized section by line; several cards for one big digest is expected.
- The digest opens with an intro card (`digest.title` + `digest.intro`).

Next: [slack.md](slack.md), [../routing.md](../routing.md)
