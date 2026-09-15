# CLI

Everything the `newswire` command accepts. `newswire --help` prints the same list.

## Invocation

```bash
newswire [--config PATH] [--dry-run] [--source ID ...] [--no-state-write]
python -m newswire ...        # identical
```

A `.env` file in the current directory is loaded automatically before anything else.

## Flags

| Flag | Default | Effect |
| --- | --- | --- |
| `--config PATH` | `config.yml`, or `$NOTIFIER_CONFIG` | Config file **or** directory — see [../config-layout.md](../config-layout.md) |
| `--dry-run` | off | Fetch and diff for real, print the rendered digest per notifier — but send nothing and write no state |
| `--source ID` | all enabled | Check only this source id (repeat the flag for several). Skips "no news" messages; an id that matches no enabled source is an error |
| `--no-state-write` | off | Send for real, but leave the state document (gist or file) untouched — the next run reports the same items as new. For live channel testing without consuming the news |
| `-h`, `--help` | — | Usage |

Flag combinations behave as expected: `--dry-run --source X` previews one source;
`--dry-run` already implies no state write.

## What a run does

1. Load and validate the config (fails here on unset `${ENV_VAR}`s, unknown keys/types/ids).
2. Load state, check every enabled source, print `Checked '<id>': N new item(s)` per source.
3. Assemble and send a digest per enabled notifier (`Sent N section(s) to '<id>'`), or the
   "no news" message where nothing is new and `send_no_news` is on.
4. Write state — a source's entry advances only if every notifier it routes to accepted the
   digest (`State for '<id>' not advanced ...` otherwise).

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Clean run (including "nothing new") |
| `1` | Config/state error (message starts with `Error:`), or a partial failure — some source fetch or notifier send failed (`Warning:` lines); everything else was still delivered |
| `2` | Bad command line (argparse) |

## Environment

| Variable | Effect |
| --- | --- |
| `NOTIFIER_CONFIG` | Default for `--config` |
| everything else | Referenced from the config via `${...}` — see [env-vars.md](env-vars.md) |

Next: [../guides/local.md](../guides/local.md), [env-vars.md](env-vars.md)
