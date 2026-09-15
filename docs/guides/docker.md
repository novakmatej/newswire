# Run in Docker

Second deployment path: one image, config mounted in, secrets via `--env-file`.

1. Build the image:
   ```bash
   docker build -t newswire .
   ```
2. Prepare `.env` (start from `.env.example`) and your `config.yml`.
3. Run once:
   ```bash
   docker run --rm --env-file .env -v "$PWD/config.yml:/app/config.yml" newswire
   ```
4. Schedule it with the host's cron (`crontab -e`):
   ```
   0 7 * * 1 docker run --rm --env-file /opt/newswire/.env -v /opt/newswire/config.yml:/app/config.yml newswire
   ```

## State in Docker

The `github_gist` backend needs nothing extra. For `local_file`, mount a volume so state survives
the container:

```bash
docker run --rm --env-file .env \
  -v "$PWD/config.yml:/app/config.yml" \
  -v "$PWD/data:/app/data" \
  newswire
```

with the config pointing inside the mount:

```yaml
state:
  backend: local_file
  options:
    path: data/state.json
```

## Dry run and flags

Anything after the image name is passed to the CLI:

```bash
docker run --rm --env-file .env -v "$PWD/config.yml:/app/config.yml" newswire \
  newswire --config /app/config.yml --dry-run
```

Next: [github-actions.md](github-actions.md), [local.md](local.md)
