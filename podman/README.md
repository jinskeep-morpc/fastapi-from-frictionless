# Container Deployment

Deploy a generated FastAPI application alongside a PostGIS database and pgAdmin using Docker Compose or Podman Compose. Works on Linux, macOS, and Windows.

## Overview

This folder contains everything needed to run `fastapifromfrictionless` in a containerized environment:

| File | Purpose |
|------|---------|
| `compose.yaml` | Defines the `postgres`, `pgadmin`, and `api` services |
| `Dockerfile` | Builds the API image; installs `fastapifromfrictionless` and uvicorn |
| `.env.example` | Template for required environment variables |
| `schemas/` | Place your `*.schema.yaml` files here |

## Prerequisites

**Linux / WSL2:**
```bash
sudo apt -y install podman podman-compose
```

**Windows (Docker Desktop):** Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) — `docker compose` is included.

**macOS:** Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) or `brew install podman podman-compose`.

## Setup

### 1. Create a deployment folder

Copy the contents of this folder to a new directory on your machine:

```
my-deployment/
  compose.yaml
  Dockerfile
  .env.example
  schemas/          # your *.schema.yaml files go here
```

### 2. Add your schemas

Copy your `*.schema.yaml` files into the `schemas/` folder. See `doc/data/` in the main repo for examples.

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with real values:

```
SUBNET_BASE=10.91             # unique per concurrent stack (10.91, 10.92, …)

API_PORT=8000                 # unique per concurrent stack
PGADMIN_PORT=5050
DB_PORT=5432

POSTGRES_USER=postgres
POSTGRES_PASSWORD=a_strong_random_password
POSTGRES_DB=mydb

PGADMIN_DEFAULT_EMAIL=you@example.com
PGADMIN_DEFAULT_PASSWORD=another_strong_password

API_KEY=yet_another_strong_password   # or leave empty to disable auth
ALLOWED_ORIGINS=*
API_URL=http://localhost:8000         # must match API_PORT
```

> **Security**: `.env` is listed in `.gitignore`. Never commit it.

### 4. Build and start

```bash
docker compose up -d
# or
podman-compose up -d
```

On the first run, images are pulled from ghcr.io (~1–2 min on a fast connection). Subsequent builds are fast.

### 5. Verify

```bash
docker compose ps
docker compose logs api
```

| Service | URL |
|---------|-----|
| API docs | `http://localhost:${API_PORT}/docs` |
| pgAdmin | `http://localhost:${PGADMIN_PORT}` |
| Postgres (host) | `localhost:${DB_PORT}` |

### Running multiple stacks simultaneously

Each stack must use a different `SUBNET_BASE` and port set. Example:

| | Stack A | Stack B |
|---|---------|---------|
| `SUBNET_BASE` | `10.91` | `10.92` |
| `API_PORT` | `8000` | `8100` |
| `PGADMIN_PORT` | `5050` | `5150` |
| `DB_PORT` | `5432` | `5532` |
| API URL | `http://localhost:8000` | `http://localhost:8100` |

## Using pgAdmin

1. Open `http://localhost:${PGADMIN_PORT}` in your browser.
2. Log in with `PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD` from your `.env`.
3. Click **Add New Server** (or right-click Servers → Register → Server).
4. In the **General** tab, give the server a name (e.g. `app-db`).
5. In the **Connection** tab:
   - **Host**: `postgres` (the service alias inside the container network)
   - **Port**: `5432`
   - **Username**: value of `POSTGRES_USER` in your `.env`
   - **Password**: value of `POSTGRES_PASSWORD` in your `.env`
   - Check **Save password**
6. Click **Save**. The database and its tables should appear in the left panel.

pgAdmin data (saved connections, sessions) is persisted in `./pgadmin/` and is excluded from git via `.gitignore`.

## Updating schemas

Schema changes require rebuilding the API image (generation happens at build time, not startup):

```bash
docker compose build api
docker compose up -d api
```

## Stopping and cleaning up

```bash
# Stop containers
docker compose down

# Also delete persisted data (destructive)
docker compose down
rm -rf ./postgres/ ./pgadmin/
```

## Connecting to the database directly

PostgreSQL is exposed on `localhost:${DB_PORT}`. Connect from the host:

```bash
psql -h localhost -p ${DB_PORT} -U postgres -d mydb
```

## Pre-built base images

The `Dockerfile` references two images published to the GitHub Container Registry:

| Image | Tag | Purpose |
|-------|-----|---------|
| `ghcr.io/jinskeep-morpc/fastapi-from-frictionless-generator` | `latest` | Stage 1 base — `python:3.12-slim` + `fastapifromfrictionless[generate]` |
| `ghcr.io/jinskeep-morpc/fastapi-from-frictionless-runtime` | `latest` | Stage 2 base — `python:3.12-slim` + `fastapifromfrictionless` + `uvicorn` + `psycopg2-binary` |

These images are rebuilt automatically on each GitHub release via `.github/workflows/build-images.yml`. Both `latest` and version-pinned tags (e.g. `0.2.16`) are published.

To pin to a specific version, edit the `FROM` lines in `Dockerfile`:

```dockerfile
FROM ghcr.io/jinskeep-morpc/fastapi-from-frictionless-generator:0.2.16 AS generator
...
FROM ghcr.io/jinskeep-morpc/fastapi-from-frictionless-runtime:0.2.16
```

## Network layout

All services share a private bridge network (`app_network`). Each service also has a host-facing port binding. Internal IPs use the `SUBNET_BASE` prefix.

| Service | Internal IP | Host port |
|---------|-------------|-----------|
| `postgres` | `{SUBNET_BASE}.0.5` | `DB_PORT` |
| `pgadmin` | `{SUBNET_BASE}.0.6` | `PGADMIN_PORT` |
| `api` | `{SUBNET_BASE}.0.7` | `API_PORT` |

## Environment variable reference

| Variable | Default | Description |
|----------|---------|-------------|
| `SUBNET_BASE` | `10.91` | First two octets of the internal bridge network; must be unique per simultaneous stack |
| `API_PORT` | `8000` | Host port for the FastAPI service; must be unique per simultaneous stack |
| `PGADMIN_PORT` | `5050` | Host port for pgAdmin; must be unique per simultaneous stack |
| `DB_PORT` | `5432` | Host port for PostgreSQL; must be unique per simultaneous stack |
| `PROJECT_NAME` | — | Informational label; no longer drives hostnames |
| `POSTGRES_USER` | — | PostgreSQL superuser name |
| `POSTGRES_PASSWORD` | — | PostgreSQL superuser password |
| `POSTGRES_DB` | — | Database name to create on first run |
| `PGADMIN_DEFAULT_EMAIL` | — | Login email for the pgAdmin web UI |
| `PGADMIN_DEFAULT_PASSWORD` | — | Login password for the pgAdmin web UI |
| `SCHEMA_FOLDER` | `schemas` | Host-side folder name containing `*.schema.yaml` files |
| `API_KEY` | *(unset)* | If set, all API requests require `X-API-Key: <value>` header |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS allowed origins |
| `API_URL` | `http://localhost:8000` | Public base URL (used by the Excel export endpoint); must match `API_PORT` |
