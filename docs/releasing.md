# Releasing

How a release happens, written for someone who has never tagged one. Release notes are generated
by [anchore/chronicle](https://github.com/anchore/chronicle) from merged PRs, grouped by label —
there is no hand-maintained CHANGELOG.md (GitHub Releases are the changelog).

## 1. Make PRs show up in the notes

Chronicle reads, in order of precedence:

1. **A label on the PR** — see the mapping in [`.chronicle.yaml`](../.chronicle.yaml):
   `enhancement`/`feature` → Added Features (minor bump), `bug`/`fix` → Bug Fixes (patch),
   `breaking-change`/`major` → Breaking Changes (major), `security` → Security Fixes,
   `deprecated` → Deprecated, `removed` → Removed.
2. **The PR title's conventional-commit prefix** as fallback: `feat:` → minor, `fix:`/`perf:` →
   patch, a `!` (e.g. `feat!:`) → major.

A PR with neither a label nor a recognised prefix **silently produces no changelog entry**. Label
it or fix the title before merging.

## 2. Preview the changelog locally

```bash
curl -sSfL https://get.anchore.io/chronicle | sudo sh -s -- -b /usr/local/bin
export GITHUB_TOKEN=ghp_yourtoken
chronicle --since-tag v1.0.0            # notes accumulated since v1.0.0
chronicle -n                            # also guess the next version from the changes
```

## 3. Cut the release

1. Bump `version` in `pyproject.toml` to match the tag (it is synced manually — one line, no
   build-time magic), commit it via a PR, merge.
2. Tag the merge commit on `main` and push the tag:
   ```bash
   git checkout main && git pull
   git tag -a v1.1.0 -m "v1.1.0"
   git push origin v1.1.0
   ```
3. The `Release` workflow (`.github/workflows/release.yml`) triggers on the tag: runs ruff and
   pytest, installs chronicle, generates the notes up to that tag, and creates the GitHub Release
   with them.
4. Check the release page; edit the notes there if something needs a human sentence.

## 4. Fix a tag pushed by mistake

```bash
git push --delete origin v1.1.0   # remove the remote tag (delete the GitHub release first if created)
git tag -d v1.1.0                 # remove it locally
```

Then re-tag the right commit and push again.

## Versioning policy

- Semantic versioning, tags `vMAJOR.MINOR.PATCH`.
- `v0.0.1` is the pre-rewrite snapshot (pre-release); `v1.0.0` is the first supported release.
- `enforce-v0: false` in `.chronicle.yaml`: breaking changes bump major.
- No PyPI publishing; install from the repo (pip/uv/Docker).

Next: [../CONTRIBUTING.md](../CONTRIBUTING.md), [index.md](index.md)
