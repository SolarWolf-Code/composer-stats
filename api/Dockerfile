# API Dockerfile using uv for fast, reproducible installs
FROM ghcr.io/astral-sh/uv:python3.11-bookworm AS base

ENV UV_PROJECT_ENVIRONMENT=/app/api/.venv \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy local path dependency and the API project
COPY composer-trade-mcp/ ./composer-trade-mcp/
COPY api/ ./api/

WORKDIR /app/api

# Install dependencies and project
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "composer_stats_api.app:app", "--host", "0.0.0.0", "--port", "8000"]


