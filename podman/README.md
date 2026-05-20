# Podman Deployment

Deploy a generated FastAPI application alongside a PostGIS database and pgAdmin using Podman Compose.
Services are accessed via local hostnames (`{project}.api`, `{project}.pgadmin`) routed through an nginx reverse proxy, so multiple deployments can run simultaneously on the same machine without port conflicts.

## Overview

This folder contains everything needed to run `fastapifromfrictionless` in a containerized environment:

| File | Purpose |
|------|---------|
| `compose.yaml` | Defines the `postgres`, `pgadmin`, `api`, and `nginx` services |
| `Dockerfile` | Builds the API image; installs `fastapifromfrictionless` and uvicorn |
| `entrypoint.sh` | Startup script: generates app from schemas, then launches uvicorn |
| `nginx.conf.template` | nginx config template — `$PROJECT_NAME` is filled in at container start |
| `setup.sh` | Adds `/etc/hosts` entries and starts the stack |
| `teardown.sh` | Stops the stack and removes `/etc/hosts` entries |
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
  nginx.conf.template
  setup.sh
  teardown.sh
  .env.example
  schemas/          # your *.schema.yaml files go here
```

### 2. Add your schemas

Copy your `*.schema.yaml` files into the `schemas/` folder. See `doc/data/` in the main repo for examples.

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with real values. The two new routing variables are the most important:

```
# Unique per deployment — drives hostnames and isolates ports
PROJECT_NAME=my-project       # results in my-project.api and my-project.pgadmin
NGINX_IP=127.0.1.1            # unique loopback IP; use 127.0.1.2 for a second stack, etc.

POSTGRES_USER=postgres
POSTGRES_PASSWORD=a_strong_random_password
POSTGRES_DB=mydb

PGADMIN_DEFAULT_EMAIL=you@example.com
PGADMIN_DEFAULT_PASSWORD=another_strong_password

API_KEY=yet_another_strong_password   # or leave empty to disable auth
ALLOWED_ORIGINS=*
API_URL=http://my-project.api         # match your PROJECT_NAME
```

> **Security**: `.env` is listed in `.gitignore`. Never commit it.

### 4. Build and start

```bash
./setup.sh
```

`setup.sh` will:
1. Add `{NGINX_IP} {PROJECT_NAME}.api` and `{NGINX_IP} {PROJECT_NAME}.pgadmin` to `/etc/hosts` (requires `sudo` once per deployment)
2. Build the API image
3. Start all four services

On the first run, Podman pulls the PostGIS, pgAdmin, nginx, and pre-built base images (~1–2 min on a fast connection). Subsequent builds skip the `pip install` steps and are very fast.

### 5. Verify

```bash
# Check that all four containers are running
podman-compose ps

# View API logs
podman-compose logs api
```

| Service | URL |
|---------|-----|
| API docs | `http://{PROJECT_NAME}.api/docs` |
| pgAdmin | `http://{PROJECT_NAME}.pgadmin` |
| Postgres (host) | `{NGINX_IP}:5432` |

### Running multiple stacks simultaneously

Each stack must use a different `PROJECT_NAME` and `NGINX_IP`:

| Deployment | `PROJECT_NAME` | `NGINX_IP` | API URL |
|------------|---------------|------------|---------|
| Stack 1 | `project-a` | `127.0.1.1` | http://project-a.api |
| Stack 2 | `project-b` | `127.0.1.2` | http://project-b.api |

Linux supports the full `127.0.0.0/8` loopback range, so there are 16 million available IPs.

## Using pgAdmin

1. Open `http://{PROJECT_NAME}.pgadmin` in your browser.
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
podman-compose build api
podman-compose up -d api
```

## Stopping and cleaning up

```bash
# Stop containers and remove /etc/hosts entries
./teardown.sh

# Also delete persisted data (destructive)
./teardown.sh
rm -rf ./postgres/ ./pgadmin/
```

## Connecting to the database directly

PostgreSQL is bound to `{NGINX_IP}:5432`. Connect from the host with:

```bash
psql -h 127.0.1.1 -p 5432 -U postgres -d mydb
```

## Pre-built base images

The `Dockerfile` references two images published to the GitHub Container Registry:

| Image | Tag | Purpose |
|-------|-----|---------|
| `ghcr.io/jinskeep-morpc/fastapi-from-frictionless-generator` | `latest` | Stage 1 base — `python:3.12-slim` + `fastapifromfrictionless[generate]` |
| `ghcr.io/jinskeep-morpc/fastapi-from-frictionless-runtime` | `latest` | Stage 2 base — `python:3.12-slim` + `fastapifromfrictionless` + `uvicorn` + `psycopg2-binary` |

These images are rebuilt automatically on each GitHub release via `.github/workflows/build-images.yml`. Both `latest` and version-pinned tags (e.g. `0.2.0`) are published.

To pin to a specific version, edit the `FROM` lines in `Dockerfile`:

```dockerfile
FROM ghcr.io/jinskeep-morpc/fastapi-from-frictionless-generator:0.2.0 AS generator
...
FROM ghcr.io/jinskeep-morpc/fastapi-from-frictionless-runtime:0.2.0
```

## Network layout

All services share a private bridge network (`app_network`). Host-facing ports are bound to `NGINX_IP` only — no service listens on `0.0.0.0`.

| Service | Internal IP | Exposed on host |
|---------|-------------|-----------------|
| `postgres` | `10.91.0.5` | `{NGINX_IP}:5432` |
| `pgadmin` | `10.91.0.6` | internal only |
| `api` | `10.91.0.7` | internal only |
| `nginx` | `10.91.0.8` | `{NGINX_IP}:80` |

## Environment variable reference

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_NAME` | — | Hostname prefix; produces `{PROJECT_NAME}.api` and `{PROJECT_NAME}.pgadmin` |
| `NGINX_IP` | `127.0.1.1` | Loopback IP for this deployment; must be unique per simultaneous stack |
| `POSTGRES_USER` | — | PostgreSQL superuser name |
| `POSTGRES_PASSWORD` | — | PostgreSQL superuser password |
| `POSTGRES_DB` | — | Database name to create on first run |
| `PGADMIN_DEFAULT_EMAIL` | — | Login email for the pgAdmin web UI |
| `PGADMIN_DEFAULT_PASSWORD` | — | Login password for the pgAdmin web UI |
| `DATABASE_URL` | *(set by compose)* | SQLAlchemy connection URL; automatically constructed from the postgres credentials |
| `SCHEMA_FOLDER` | `schemas` | Host-side folder name containing `*.schema.yaml` files |
| `API_KEY` | *(unset)* | If set, all API requests require `X-API-Key: <value>` header |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS allowed origins |
| `API_URL` | `http://{PROJECT_NAME}.api` | Public base URL (used by the Excel export endpoint) |
