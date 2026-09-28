# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

FROM base AS build
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev
# Bake the embedding model into the image: no download at cold start and
# no outbound call from the running service to fetch it. Same code path as the
# app, so the files land where the Embedder looks for them.
RUN .venv/bin/python -c "from pathlib import Path; \
from curator.retrieval.embeddings import Embedder; \
Embedder('intfloat/multilingual-e5-large', Path('/app/.models')).download()"

FROM base AS runtime
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/.chroma /app/.runtime && chown -R app /app
WORKDIR /app
COPY --from=build --chown=app /app/.venv ./.venv
COPY --from=build --chown=app /app/.models ./.models
COPY --chown=app src ./src
COPY --chown=app data ./data
COPY --chown=app reports ./reports
USER app
ENV PATH="/app/.venv/bin:$PATH" \
    ENVIRONMENT=production \
    PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn curator.api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
