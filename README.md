## Composer Stats – Monorepo

This repository contains:

- `api/`: FastAPI service exposing Composer portfolio performance endpoints (package: `composer-stats-api`)
- `web/`: Next.js frontend dashboard
- `composer-trade-mcp/`: Local MCP client used by the API (installed via path dependency)

### Prerequisites

- Python 3.11+
- Node.js 18+ (recommended 20)
- UV package manager for Python (recommended) – see `https://docs.astral.sh/uv/`
- Docker and Docker Compose (optional, for containerized dev/prod)

---

## Local development

### 1) API

```bash
cd api
# Install dependencies into a local virtualenv
uv sync

# Run (hot reload)
uv run uvicorn composer_stats_api.app:app --host 0.0.0.0 --port 8000 --reload

# Alternatively via console entrypoint
uv run composer-stats-api
```

- Health check: `http://localhost:8000/health`
- Performance API: `GET http://localhost:8000/api/performance`

No environment variables are required by the API. The frontend passes credentials per request via `Authorization: Basic` header (also mirrored with `x-api-key-id` and `x-api-secret`).

### 2) Web

```bash
cd web
npm install

# Run dev server
npm run dev
```

- App: `http://localhost:3000`

---

## Docker and Docker Compose

This repo ships with a `docker-compose.yml` that starts both the API and Web apps for local dev or simple deployment.

### Build and run

```bash
docker compose up --build
```

Services:

- API: `http://localhost:8123` (exposes `/health`, `/api/performance`)
- Web: `http://localhost:3123`

The web app calls the API at `http://localhost:8123` by default in Compose. You can override with `NEXT_PUBLIC_API_URL` in your environment. CORS is configured to allow localhost by default. Credentials are entered in the web UI (Login) and sent as headers per request.

To run in detached mode:

```bash
docker compose up --build -d
```

To stop and remove containers:

```bash
docker compose down
```

---

## Repository structure

```
composer-stats/
  api/
    src/composer_stats_api/        # FastAPI app package
    main.py                        # Thin ASGI shim (imports app)
    pyproject.toml                 # uv/PEP 621 project
    uv.lock                        # locked dependencies
    Dockerfile                     # container build for API
  web/                             # Next.js app
    Dockerfile                     # container build for web
  composer-trade-mcp/              # Local MCP client (path dependency for API)
  docker-compose.yml               # Multi-service setup (api + web)
  README.md
```

---

## Notes

- The API depends on `composer-trade-mcp` via a local path; the Docker build copies it into the API image to keep versions in sync.
- For production, consider building the web app (`npm run build`) and running `next start` instead of dev mode; adjust `web/Dockerfile` and `docker-compose.yml` accordingly.
- For custom domains/SSL, place a reverse proxy (e.g., Nginx, Traefik) in front of the services.


