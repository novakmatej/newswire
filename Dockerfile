FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Mount your config at /app/config.yml (see docs/guides/docker.md):
#   docker run --env-file .env -v "$PWD/config.yml:/app/config.yml" newswire
CMD ["newswire", "--config", "/app/config.yml"]
