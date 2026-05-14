# Podman Deployment

Deploy a generated FastAPI application alongside a PostGIS database using Podman Compose.

## Overview

This folder contains everything needed to run `fastapifromfrictionless` in a containerized environment:

| File | Purpose |
|------|---------|
| `compose.yaml` | Defines the `postgres` (PostGIS) and `api` (FastAPI) services |
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

API_KEY=another_strong_random_password   # or leave empty to disable auth
ALLOWED_ORIGINS=*
API_URL=http://localhost:8000
```

> **Security**: `.env` is listed in `.gitignore`. Never commit it.

### 4. Start the services

```bash
podman-compose up -d
```

The first run builds the API image and pulls the PostGIS image (~2–3 minutes). On startup the API container:

1. Reads `*.schema.yaml` files from `schemas/`
2. Generates `models.py`, `app.py`, and `database.py`
3. Connects to the PostGIS database (waits for it to be healthy)
4. Creates all tables via SQLModel
5. Starts uvicorn on port 8000

### 5. Verify

```bash
# Check that both containers are running
podman-compose ps

# View API logs
podman-compose logs api

# Test the API
curl http://localhost:8000/docs
```

The interactive API docs are at **http://localhost:8000/docs**.

## Updating schemas

When you change or add schemas, rebuild the API image and restart:

```bash
podman-compose build api
podman-compose up -d api
```

## Stopping and cleaning up

```bash
# Stop containers (data is preserved in ./postgres/)
podman-compose down

# Stop and delete all data volumes (destructive)
podman-compose down -v
rm -rf ./postgres/
```

## Connecting to the database directly

The PostgreSQL service is exposed on port 5432. Connect from the host with:

```bash
psql -h localhost -p 5432 -U postgres -d mydb
```

Or use pgAdmin — see the [podgis](../podgis) repo for a pgAdmin setup example using the same network pattern.

## Network layout

Both services share a private bridge network (`app_network`):

| Service | IP | Port |
|---------|----|------|
| `postgres` | `10.91.0.5` | `5432` |
| `api` | `10.91.0.6` | `8000` |

The API connects to postgres using the service alias `postgres` as the hostname (via `DATABASE_URL`).

## Environment variable reference

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | — | PostgreSQL superuser name |
| `POSTGRES_PASSWORD` | — | PostgreSQL superuser password |
| `POSTGRES_DB` | — | Database name to create on first run |
| `DATABASE_URL` | *(set by compose)* | SQLAlchemy connection URL; automatically constructed from the postgres credentials |
| `API_KEY` | *(unset)* | If set, all API requests require `X-API-Key: <value>` header |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS allowed origins |
| `API_URL` | `http://localhost:8000` | Public base URL (used by the Excel export endpoint) |
