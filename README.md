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
from fastapifromfrictionless.load import build_database

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
from fastapifromfrictionless.load import empty_excel, create_package, update_api_from_package

# Create a blank workbook with one sheet per schema
empty_excel(schema_folder="path/to/schemas", output_filepath="data.xlsx")

# Fill in data, then validate and sync to the API
create_package(folder="path/to/schemas", filename="data.xlsx")
update_api_from_package(api_url="http://localhost:8000", package_file="data.package.yaml")

# Or export all current API data to Excel
from fastapifromfrictionless.load import dump_to_excel
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

A ready-to-use Podman deployment lives in `podman/`. It spins up three containers — PostGIS database, pgAdmin web UI, and the generated FastAPI app — with no manual setup beyond dropping schemas into a folder and filling in a `.env` file.

The API image uses a **two-stage build**: Stage 1 generates FastAPI code from your schemas; Stage 2 produces a lean runtime image. Both stages pull **pre-built base images** from ghcr.io, so only the copy and generation steps run locally — no pip installs required.

```bash
cd podman/
cp .env.example .env          # fill in passwords and settings
# add *.schema.yaml files to schemas/
podman-compose build api      # generate app code from your schemas (~20 s)
podman-compose up -d          # start all three containers
```

After schema changes, re-run `podman-compose build api` then `podman-compose up -d api`.

See [`podman/README.md`](podman/README.md) for full instructions.

## Roadmap

Items are grouped by priority. Checked items are complete.

### Foundation

- [x] Generate SQLModel class hierarchies from Frictionless schemas
- [x] Generate FastAPI CRUD + query endpoints per resource
- [x] Generate `database.py` with SQLite engine setup
- [x] Excel workbook as data-entry interface (create and update)
- [x] Frictionless package wrapping for field-level validation
- [x] Export API data back to Excel (dump all records to workbook)
- [x] Validate schemas before code generation; surface clear error messages on malformed input

### Code Quality & Reliability

- [x] Add a test suite (unit tests for generators, integration tests for generated app)
- [x] Add CI pipeline (lint, type-check, tests on push)
- [x] Enforce type hints throughout; run `mypy` in CI
- [x] Replace raw string generation with a templating engine (e.g. Jinja2) for maintainability
- [x] Structured logging with configurable verbosity
- [x] Complete Frictionless field type coverage — all standard types map to concrete Python/SQLAlchemy types; `geoalchemy2` import emitted only when geo types are present; unknown types fall back gracefully

### Production Readiness

- [ ] Async database support (replace sync SQLModel sessions with async SQLAlchemy)
- [ ] Database migrations via [Alembic](https://alembic.sqlalchemy.org/) instead of `create_all`
- [x] Configuration management — accept settings via environment variables or a config file (database URL, allowed origins, etc.)
- [x] CORS and security headers in generated `app.py`
- [x] API key / token authentication ([FastAPI security](https://fastapi.tiangolo.com/tutorial/security/first-steps/)) — fail-closed: app refuses to start unless `API_KEY` is set or `ALLOW_NO_AUTH=true` is explicitly opted in
- [x] Pagination on list endpoints
- [x] Proper HTTP error responses with consistent JSON error bodies

### Developer Experience

- [x] CLI entry point (`fastapifromfrictionless generate <schema-folder>`) so users do not need to write Python
- [x] Dry-run / preview mode that prints generated code without writing files
- [x] Configurable output — opt in/out of specific endpoint types, choose database backend
- [x] Package versioning and automated releases (GitHub Actions → PyPI)
- [x] Expand documentation and examples in `doc/`

### Optional / Future

- [x] Support for PostgreSQL and other SQLAlchemy-compatible backends
- [x] Podman/container deployment (Compose stack with PostGIS, pgAdmin, and FastAPI; multi-stage Dockerfile with pre-built base images on ghcr.io; version-pinned builds with PyPI availability polling to prevent CDN lag)
- [x] All runtime dependencies declared in base package (`frictionless`, `python-multipart`, `geoalchemy2`) — generated app works out of the box without extras
- [ ] Auto-generated front-end form from schema fields
- [ ] DrawIO ERD → Frictionless schema converter
- [x] Default query routes for common patterns derived from schema metadata
- [x] GET/POST file endpoints for uploading and downloading the Excel workbook directly via the API
