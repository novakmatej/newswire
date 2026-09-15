# One config file or a config directory

`--config` accepts either. One loading rule, one validator, identical results — the shipped
examples ([`config.example.yml`](../config.example.yml) and
[`config.example/`](../config.example/)) load byte-for-byte equal, enforced by a test.

## Single file

```
config.yml        # everything: defaults, digest, state, sources, notifiers
```

## Directory — the file name is the key it contributes

```
config/
  config.yml      # any top-level key; put defaults and digest here
  state.yml       # -> the `state` block
  notifiers.yml   # -> the `notifiers` list
  sources.yml     # -> the `sources` list
```

For a large setup, split one key further with a `<key>.d/` directory of fragments:

```
config/
  config.yml
  notifiers.yml
  sources.d/
    10-dbt.yml
    20-airflow.yml
    30-kubernetes.yml
```

A fragment may be a bare list/mapping (preferred, used in the examples) or wrapped under its key
(`sources:` at the top). Only `.yml` and `.yaml` count.

## Merge rules

1. **Load order is lexicographic by full path.** `sources` order is digest order, so order must be
   predictable: use the `10-`, `20-`, `30-` prefix convention. **Renaming a file reorders the
   digest.** (Note: `sources.d/...` sorts *before* `sources.yml`.)
2. Lists (`sources`, `notifiers`) concatenate in load order.
3. Mappings (`defaults`, `digest`, `state`) merge key-by-key, recursively; later wins.
4. A duplicate `id` is an **error** naming both files — never a silent override.
5. Any unexpected file in a config directory is an **error** (a typo'd `sources.yaml.bak` must not
   be silently ignored). Dotfiles are the only exception.
6. No `include:`, no cross-file references, no templating beyond `${ENV_VAR}`. Explicit ordering is
   what the numeric prefixes are for.

Next: [configuration.md](configuration.md), [routing.md](routing.md)
