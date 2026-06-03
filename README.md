# fastapi-from-frictionless

> **Status: Work in Progress** — API and generated output are subject to change.

## Overview

`fastapifromfrictionless` is a Python scaffolding tool that reads [Frictionless Data Package](https://datapackage.org/standard/data-package/) schema files and generates a fully-functional [FastAPI](https://fastapi.tiangolo.com/) + [SQLModel](https://sqlmodel.tiangolo.com/) application — including models, CRUD endpoints, and dynamic query support — with no hand-written boilerplate.

The driving goal is to bridge the gap between familiar flat-file workflows (Excel workbooks, CSV files, Frictionless packages) and a production-grade relational database with a queryable REST API. Data stewards continue working in Excel; the package handles ingestion, validation, and API synchronization behind the scenes.

**Core capabilities:**

- Generate `models.py`, `app.py`, and `database.py` from `*.schema.yaml` files
- Automatic SQLModel class hierarchy per schema (base, table, create, update, public, public-with-relations)
- Full CRUD + pagination + recent-records endpoints per resource
- Excel workbook as a data-entry interface — create or update API records from a `.xlsx` file
- Frictionless package wraps the workbook for field-level validation before ingestion
- CLI entry point: `fastapifromfrictionless generate <schema-folder>`

## Requirements

- Python >= 3.10
- [frictionless](https://pypi.org/project/frictionless/)
- [FastAPI](https://pypi.org/project/fastapi/)
- [SQLModel](https://pypi.org/project/sqlmodel/)
- [SQLAlchemy](https://pypi.org/project/sqlalchemy/)
- [fastapi-querybuilder](https://github.com/bhadri01/fastapi-querybuilder)
- [jinja2](https://pypi.org/project/Jinja2/)
- [requests](https://pypi.org/project/requests/)
- [pandas](https://pypi.org/project/pandas/)
- [xlsxwriter](https://pypi.org/project/XlsxWriter/)

An ASGI server such as [uvicorn](https://www.uvicorn.org/) is required to run the generated application.

## Installation

```bash
pip install -e .
```

## Quick Start

### 1. Generate application files from schemas

Place `*.schema.yaml` files in a folder (see `doc/data/` for examples), then run:

```bash
fastapifromfrictionless generate path/to/schemas --output path/to/output
```

Or from Python:

```python
from fastapifromfrictionless.scaffolding import build_database

build_database(schema_folder="path/to/schemas", db_filename="app.db")
```

### 2. Start the generated API

```bash
cd path/to/output
uvicorn app:app --reload
```

### 3. Generated endpoints

For each schema resource, the generated app exposes the following endpoints (replace `{resource}` with the schema name, e.g. `sensor`, `location`, `permit`):

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/{resource}` | Create a record |
| `POST` | `/{resource}s/bulk` | Create many records in a single request (one commit) |
| `GET` | `/{resource}/all` | List all (paginated: `?offset=0&limit=100`) |
| `GET` | `/{resource}/recent` | Most recent records (`?limit=10`) |
| `GET` | `/{resource}/{id}` | Get one by primary key |
| `PATCH` | `/{resource}/{id}` | Update a record |
| `DELETE` | `/{resource}/{id}` | Delete a record |
| `GET` | `/{resource}/query` | Dynamic filter query (FK schemas only) |
| `GET` | `/excel/export` | Download all data as `.xlsx` |
| `POST` | `/excel/import` | Upload and sync an `.xlsx` workbook |

### 4. Configuration via environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///database.db` | Database connection URL (overrides SQLite default) |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS allowed origins |
| `API_KEY` | *(required)* | All requests require `X-API-Key: <value>` header. App refuses to start if unset unless `ALLOW_NO_AUTH=true` is also set. |
| `ALLOW_NO_AUTH` | *(unset)* | Set to `true` to start the app without `API_KEY` (dev only — logs a warning, do not use in production) |
| `SCHEMA_FOLDER` | `.` | Path to `*.schema.yaml` files (used by Excel import/export) |
| `API_URL` | `http://localhost:8000` | Base URL of this app (used by Excel export) |

### 5. Excel data workflow

```python
from fastapifromfrictionless.runtime import (
    empty_excel, create_package, update_api_from_package, dump_to_excel
)

# Create a blank workbook with one sheet per schema
empty_excel(schema_folder="path/to/schemas", output_filepath="data.xlsx")

# Fill in data, then validate and sync to the API
create_package(folder="path/to/schemas", filename="data.xlsx")
update_api_from_package(api_url="http://localhost:8000", package_file="data.package.yaml")

# Or export all current API data to Excel
dump_to_excel(api_url="http://localhost:8000", schema_folder="path/to/schemas", output_filepath="export.xlsx")
```

### 6. CLI reference

```
fastapifromfrictionless generate <schema_folder> [options]

Options:
  --output DIR      Output directory (default: current directory)
  --db FILENAME     SQLite database filename (default: database.db)
  --dry-run         Print generated code to stdout without writing files
  --no-models       Skip generating models.py
  --no-app          Skip generating app.py
  --no-db           Skip generating database.py
```

See [`doc/quickstart.ipynb`](doc/quickstart.ipynb) for a step-by-step walkthrough of the full deployment workflow.

## Deployment

A ready-to-use container deployment lives in `podman/`. It spins up three containers — PostGIS database, pgAdmin web UI, and the generated FastAPI app — and works with Docker Desktop, Podman, or any `docker compose`-compatible tool on Linux, macOS, and Windows.

Multiple deployments can run simultaneously on the same machine by assigning each a unique `SUBNET_BASE` and port set (`API_PORT`, `PGADMIN_PORT`, `DB_PORT`).

The API image uses a **two-stage build**: Stage 1 installs the code-generator and produces FastAPI source from your schemas; Stage 2 installs only the runtime dependencies and serves the generated app. The `pip install` layer is cached, so schema-only rebuilds are fast.

```bash
cd podman/
cp .env.example .env          # set ports, passwords, and settings
# add *.schema.yaml files to schemas/
docker compose up -d          # or: podman-compose up -d
```

After schema changes, re-run `docker compose build api` then `docker compose up -d api`. To stop and clean up, run `docker compose down`.

See [`podman/README.md`](podman/README.md) for full instructions.
