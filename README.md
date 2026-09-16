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
pip install fastapifromfrictionless
```

For environments that run the **generated app** (FK query endpoints, geo field types):

```bash
pip install "fastapifromfrictionless[app]"
```

### Windows

The base install works on Windows without any prerequisites.

The `[app]` extra includes `geoalchemy2`, which requires **GDAL**. If your schemas use geographic field types, install GDAL first:

> [GDAL installation guide for Windows](https://github.com/djayepro3/gdal-easy-installation-guide-windows-linux-macos/blob/main/README.md#%EF%B8%8F-installation-on-windows)

Then install the extra:

```bash
pip install "fastapifromfrictionless[app]"
```

If your schemas do not use geo fields, `pip install fastapifromfrictionless` is sufficient and no GDAL install is needed.

### Unique constraints

Frictionless `constraints.unique: true` emits a unique constraint on the column:

```python
name: str = Field(unique=True)
```

The flag is merged into whatever the field already carries, so a foreign key keeps its
settings:

```python
sensor_name: str | None = Field(foreign_key="sensor.name", index=True, unique=True)
```

Primary keys are skipped — already unique, so a second constraint would only add a duplicate
index.

**This matters for foreign keys.** PostgreSQL requires a FK to reference a column with a unique
or primary key constraint. If a schema's `foreignKeys` targets a non-PK column, mark that column
`unique: true` or table creation fails with:

```
psycopg2.errors.InvalidForeignKey: there is no unique constraint matching given keys
for referenced table "sensor"
```

SQLite does not enforce this, so such a schema works locally and fails only on a real
deployment.

### Geo field types

Frictionless `geopoint` and `geojson` fields generate a geoalchemy2 column rather than a plain
annotation:

```python
location: Any | None = Field(default=None, sa_column=Column(Geometry("POINT")))
footprint: Any = Field(sa_column=Column(Geometry("GEOMETRY"), nullable=False))
```

**These columns require a spatial database.** `create_db_and_tables()` fails on plain SQLite
with `no such function: RecoverGeometryColumn`, because geoalchemy2 emits SpatiaLite calls.
The generated `database.py` defaults to SQLite, so a schema with a geo field needs
`DATABASE_URL` pointed at PostGIS (as in the `podman/` stack) or SpatiaLite loaded into SQLite.

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

#### Related objects in responses

`GET` endpoints return a `*PublicWithAll` model that embeds related records. Cardinality follows
the foreign key: the schema that **owns** the FK gets a single object, the referenced schema gets
a list.

Given `deployment.sensor_name` referencing `sensor.name`:

```jsonc
// GET /deployment/all
{ "name": "DEP_001", "sensor": { "name": "MORPC_001", ... }, "readings": [ ... ] }

// GET /sensor/all
{ "name": "MORPC_001", "deployments": [ { "name": "DEP_001", ... } ] }
```

The singular key (`sensor`) is the many-to-one side and is `null` when the FK is unset; plural
keys are always lists.

### Browser CRUD UI

Generated apps are JSON-only by default. Add `--with-ui` to also generate `ui.py`, a small
server-rendered interface for people who need to edit records without curl or Swagger:

```bash
python -m fastapifromfrictionless.cli generate schemas/ --output api/ \
    --with-ui --skip-ui reading
```

It mounts at `/ui` and gives you an index, a paginated list per resource, and create, edit and
delete forms. Inputs are chosen by field type, and a foreign key renders as a select of existing
values rather than a free-text id. Jinja2 and HTMX, server-rendered: no separate service, no
build step, no JavaScript toolchain.

`--skip-ui` omits resources. A table with tens of millions of rows should not get a browse page,
and its count queries would be slow enough to notice.

A list row opens a **read-only detail page** showing every field, any records that point at it,
and — for a `geopoint` field — a small map. Edit and delete both live there, so deleting takes a
deliberate navigation rather than a stray click on a row you were scanning.

**Foreign key values link through** to the record they reference. These usually do not point at
the target's primary key (`deployment.sensor_name` references `sensor.name` while the key is
`macaddr`), so values are resolved in one query per target table and linked directly; anything
that does not resolve falls back to the filtered list.

Map tiles come from OpenStreetMap by default. `UI_MAP_TILE_URL` and `UI_MAP_ATTRIBUTION` point
at another source — your own tile server, or a provider with an API key.

Geometry columns are shown, never edited: they render as a map and coordinates on the detail
page, and forms leave them out entirely rather than round-tripping a binary value through a text
box. Populating them is a per-schema concern — a trigger deriving the point from latitude and
longitude, for instance.

List views can be filtered and sorted. The search box matches case-insensitively across every
column — values are cast to text, so it finds numbers and dates as well as strings — and column
headers sort, toggling ascending and descending. Filter, sort and page survive each other, and
HTMX swaps just the table so typing narrows the list without a reload. A sort column is checked
against the resource's own fields, so an unknown one is ignored rather than reaching the query.

Writes go through the same models as the API, so validation is not bypassed.

#### Signing in

The API authenticates with an `X-API-Key` header, which a browser form post cannot send, so the
UI accepts the same key from an HttpOnly cookie set by a small sign-in page. Nothing is
reachable without it.

For real per-user identity, put an identity-aware proxy in front — Cloudflare Access, Tailscale,
oauth2-proxy — and name the header it injects:

```
UI_PROXY_IDENTITY_HEADER=Cf-Access-Authenticated-User-Email
```

The UI then trusts that header and shows who is signed in. **Only set this where the proxy is
the only route to the app**: anything able to reach it directly can forge the header. If the
header is configured but absent, the UI falls back to the cookie rather than locking everyone
out.

One shared key means no per-user audit trail. That is a deliberate limit — the UI is built for a
few trusted editors, and anything more needs real accounts.

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
    empty_excel,
    create_package,
    update_api_from_package,
    dump_to_excel,
)

# Create a blank workbook with one sheet per schema
empty_excel(schema_folder="path/to/schemas", output_filepath="data.xlsx")

# Fill in data, then validate and sync to the API
create_package(folder="path/to/schemas", filename="data.xlsx")
update_api_from_package(api_url="http://localhost:8000", package_file="data.package.yaml")

# Or export all current API data to Excel
dump_to_excel(
    api_url="http://localhost:8000", schema_folder="path/to/schemas", output_filepath="export.xlsx"
)
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
