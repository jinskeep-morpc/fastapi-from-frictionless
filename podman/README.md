# Podman Deployment

Deploy a generated FastAPI application alongside a PostGIS database and pgAdmin using Podman Compose.

## Overview

This folder contains everything needed to run `fastapifromfrictionless` in a containerized environment:

| File | Purpose |
|------|---------|
| `compose.yaml` | Defines the `postgres` (PostGIS), `pgadmin`, and `api` (FastAPI) services |
| `Dockerfile` | Builds the API image; installs `fastapifromfrictionless` and uvicorn |
| `entrypoint.sh` | Startup script: generates app from schemas, then launches uvicorn |
| `.env.example` | Template for required environment variables |
| `schemas/` | Place your `*.schema.yaml` files here |

## Prerequisites

Install Podman and podman-compose:

```bash
# Linux
sudo apt -y install podman podman-compose

# Windows: see https://github.com/containers/podman/blob/main/docs/tutorials/podman-for-windows.md
```

## Setup

### 1. Create a deployment folder

Copy the contents of this folder to a new directory on your machine:

```
my-deployment/
  compose.yaml
  Dockerfile
  entrypoint.sh
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
POSTGRES_USER=postgres
POSTGRES_PASSWORD=a_strong_random_password
POSTGRES_DB=mydb

PGADMIN_DEFAULT_EMAIL=you@example.com
PGADMIN_DEFAULT_PASSWORD=another_strong_password

API_KEY=yet_another_strong_password   # or leave empty to disable auth
ALLOWED_ORIGINS=*
API_URL=http://localhost:8000
```

> **Security**: `.env` is listed in `.gitignore`. Never commit it.

### 4. Build and start the services

The API image uses a **two-stage build**: Stage 1 generates the FastAPI application from your schemas; Stage 2 produces a lean runtime image without the generation tools.

```bash
# Build the API image (reads schemas/ and generates the app code)
podman-compose build api

# Start all three services
podman-compose up -d
```

The first run pulls the PostGIS and pgAdmin images and builds the API image (~3–5 minutes). Subsequent builds are fast because the heavy pip install layer is cached.

On startup the API container:

1. Connects to the PostGIS database (waits for it to be healthy)
2. Creates all tables via SQLModel
3. Starts uvicorn on port 8000 — no generation step at runtime

### 5. Verify

```bash
# Check that all three containers are running
podman-compose ps

# View API logs
podman-compose logs api

# Test the API
curl http://localhost:8000/docs
```

| Service | URL |
|---------|-----|
| API docs | http://localhost:8000/docs |
| pgAdmin | http://localhost:8080 |

## Using pgAdmin

1. Open **http://localhost:8080** in your browser.
2. Log in with `PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD` from your `.env`.
3. Click **Add New Server** (or right-click Servers → Register → Server).
4. In the **General** tab, give the server a name (e.g. `app-db`).
5. In the **Connection** tab:
   - **Host**: `10.91.0.5` (the postgres container IP)
   - **Port**: `5432`
   - **Username**: value of `POSTGRES_USER` in your `.env`
   - **Password**: value of `POSTGRES_PASSWORD` in your `.env`
   - Check **Save password**
6. Click **Save**. The database and its tables should appear in the left panel.

pgAdmin data (saved connections, sessions) is persisted in `./pgadmin/` and is excluded from git via `.gitignore`.

## Updating schemas

Schema changes require rebuilding the API image (generation happens at build time, not startup):

```bash
podman-compose build api
podman-compose up -d api
```

The schemas are baked into the image during the build. The `schemas/` volume is still mounted at runtime so the Excel import/export endpoints can read the schema definitions.

## Stopping and cleaning up

```bash
# Stop containers (data is preserved in ./postgres/ and ./pgadmin/)
podman-compose down

# Stop and delete all data volumes (destructive)
podman-compose down -v
rm -rf ./postgres/ ./pgadmin/
```

## Connecting to the database directly

The PostgreSQL service is exposed on port 5432. Connect from the host with:

```bash
psql -h localhost -p 5432 -U postgres -d mydb
```

## Network layout

All services share a private bridge network (`app_network`):

| Service | IP | Port |
|---------|----|------|
| `postgres` | `10.91.0.5` | `5432` |
| `pgadmin` | `10.91.0.6` | `8080` → `80` |
| `api` | `10.91.0.7` | `8000` |

The API connects to postgres using the service alias `postgres` as the hostname (via `DATABASE_URL`).

## Environment variable reference

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | — | PostgreSQL superuser name |
| `POSTGRES_PASSWORD` | — | PostgreSQL superuser password |
| `POSTGRES_DB` | — | Database name to create on first run |
| `PGADMIN_DEFAULT_EMAIL` | — | Login email for the pgAdmin web UI |
| `PGADMIN_DEFAULT_PASSWORD` | — | Login password for the pgAdmin web UI |
| `DATABASE_URL` | *(set by compose)* | SQLAlchemy connection URL; automatically constructed from the postgres credentials |
| `API_KEY` | *(unset)* | If set, all API requests require `X-API-Key: <value>` header |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS allowed origins |
| `API_URL` | `http://localhost:8000` | Public base URL (used by the Excel export endpoint) |
