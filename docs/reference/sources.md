# Source types

Every `type:` a `sources:` entry can use, with its options. Common keys (`id`, `title`,
`emoji`, `notify`, ...) are in [configuration.md](../configuration.md).

## `github_releases`

GitHub REST API, `/repos/{repo}/releases`. Diff idiom: **cursor** — everything newer than the
stored tag; first run sends only the newest release. Renders as rich cards (release notes parsed
into Features/Fixes/... sections).

| Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `repo` | string | yes | — | `owner/name`, e.g. `dbt-labs/dbt-core` |
| `token` | string | no | — | GitHub token; raises the rate limit from 60 to 5000 req/h |
| `per_page` | int | no | `30` | Releases fetched per run (max 100) |
| `timeout` | number | no | `defaults.timeout` | Request timeout in seconds |

```yaml
- id: dbt-core-releases
  type: github_releases
  title: "dbt-core"
  emoji: "🚀"
  options:
    repo: dbt-labs/dbt-core
```

Failure mode: API errors (rate limit, typo in `repo`) skip this source for the run and leave its
state untouched.

## `github_discussions`

GitHub GraphQL API, one discussion category. Diff idiom: **seen-set** — discussion numbers not in
the stored set are new; numbers that disappear are dropped silently. Renders as a link list.

| Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `repo` | string | yes | — | `owner/name` |
| `category` | string | yes | — | Discussion category slug, e.g. `announcements` |
| `token` | string | **yes** | — | The GraphQL API rejects anonymous requests. In GitHub Actions a PAT, not `secrets.GITHUB_TOKEN` — see [env-vars.md](env-vars.md) |
| `first` | int | no | `10` | Discussions fetched per run |
| `timeout` | number | no | `defaults.timeout` | Request timeout in seconds |

```yaml
- id: dbt-fusion-discussions
  type: github_discussions
  title: "Fusion Discussions"
  emoji: "💬"
  options:
    repo: dbt-labs/dbt-fusion
    category: announcements
    token: ${GITHUB_TOKEN}
```

Failure mode: a missing/insufficient token or an unknown category fails the source (the error
lists the available category slugs).

## `docusaurus_blog`

BeautifulSoup scraper for a Docusaurus-style blog listing. Diff idiom: **cursor** on the post
URL; first run sends only the newest post. Renders as a link list.

| Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `url` | string | yes | — | Blog listing page |
| `item_selector` | string | no | `article.margin-bottom--xl` | CSS selector for one post |
| `title_selector` | string | no | `h2.title_f1Hy a` | Selector for the title link inside a post |
| `date_selector` | string | no | `time` | Selector for the date element inside a post |
| `timeout` | number | no | `defaults.timeout` | Request timeout in seconds |

```yaml
- id: dbt-blog
  type: docusaurus_blog
  title: "Developer Blog Posts"
  emoji: "📰"
  options:
    url: https://docs.getdbt.com/blog
```

Failure mode: scraper — breaks when the page markup changes; selector defaults match
docs.getdbt.com.

## `html_list`

Generic BeautifulSoup scraper: select heading elements, take the link inside each, dedupe by URL.
Diff idiom: **seen-set** on URLs; items that disappear are dropped from state silently. Renders as
a link list.

| Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `url` | string | yes | — | Page to scrape |
| `item_selector` | string | no | `h3.heading-4` | CSS selector for the linked headings |
| `section_id` | string | no | — | When set, only headings inside the `div.grid` following the element with this HTML id count (getdbt.com category pages use `latest-posts`) |
| `timeout` | number | no | `defaults.timeout` | Request timeout in seconds |

```yaml
- id: dbt-webinars
  type: html_list
  title: "Upcoming Webinars"
  emoji: "🎥"
  options:
    url: https://www.getdbt.com/resources/webinars/category/upcoming
```

Failure mode: scraper — breaks when the page markup changes. Titles shorter than 5 characters are
skipped as navigation noise.

## `dbt_cloud_release_notes`

BeautifulSoup scraper for the dbt Cloud release-notes page (`h2` month headings with bullet
lists) — named after its target on purpose: the parsing is coupled to that page's structure.
Diff idiom: **section compare** — the newest `h2` and its bullets against the stored ones: a new
heading reports all its bullets, the same heading reports only bullets not stored yet. Links in
bullets are kept. Renders as a bullet-note section with a "view all" footer link.

| Option | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `url` | string | yes | — | Release-notes page |
| `timeout` | number | no | `defaults.timeout` | Request timeout in seconds |

```yaml
- id: dbt-cloud-releases
  type: dbt_cloud_release_notes
  title: "dbt Cloud Release Notes"
  emoji: "☁️"
  options:
    url: https://docs.getdbt.com/docs/dbt-versions/release-notes/cloud
```

Failure mode: scraper — breaks when the page markup changes. The `h2`/`ul` selectors are fixed;
headings are trimmed to their first two words (built for "November 2025"-style month headings).

Next: [notifiers.md](notifiers.md), [state.md](state.md)
