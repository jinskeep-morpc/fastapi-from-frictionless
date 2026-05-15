# Package Architecture Guide

This document explains how `fastapifromfrictionless` works from the inside. It is written for someone who is new to Python development and wants to understand the purpose of each file and how they connect.

---

## What the package does

In plain terms: you describe your data using simple YAML files, and this package automatically writes a working web API for you — complete with a database, endpoints to read and write records, and even Excel import/export.

```
You write:          The package writes:         You get:
schema YAML files → Python source code      → a running web API
                    (models.py, app.py,         + database
                     database.py)               + Excel endpoints
```

No manual coding of routes, database tables, or data models is needed.

---

## The two phases

The package operates in two distinct phases that run at different times:

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1 — CODE GENERATION  (runs once, at build time)          │
│                                                                 │
│  *.schema.yaml files  ──►  generator  ──►  models.py            │
│                                       ──►  app.py               │
│                                       ──►  database.py          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2 — RUNTIME  (runs continuously, when the API is up)     │
│                                                                 │
│  models.py + app.py + database.py  ──►  FastAPI web server      │
│                                         ──►  PostgreSQL database│
│                                         ──►  HTTP endpoints     │
└─────────────────────────────────────────────────────────────────┘
```

Phase 1 is triggered by the CLI command:
```bash
python -m fastapifromfrictionless.cli generate schemas/ --output api/
```

Phase 2 is triggered by starting the web server:
```bash
uvicorn api.app:app --host 0.0.0.0 --port 8000
```

---

## Repository layout

```
fastapi-from-frictionless/
│
├── fastapifromfrictionless/        ← the Python package
│   ├── __init__.py                 ← package entry point, exports public API
│   ├── cli.py                      ← command-line interface
│   ├── model.py                    ← generates models.py
│   ├── app.py                      ← generates app.py
│   ├── database.py                 ← generates database.py
│   ├── validate.py                 ← checks schemas before generation
│   ├── load.py                     ← Excel import/export utilities
│   ├── logging_config.py           ← logging setup helper
│   └── templates/                  ← Jinja2 template files
│       ├── models_header.py.jinja2 ← top of models.py (imports, mixins)
│       ├── model_block.py.jinja2   ← one model class per schema
│       ├── app_header.py.jinja2    ← top of app.py (FastAPI setup, Excel endpoints)
│       ├── endpoint_block.py.jinja2← CRUD routes per schema
│       └── database.py.jinja2      ← full database.py file
│
├── tests/                          ← automated tests
├── podman/                         ← Docker/Podman deployment files
├── doc/                            ← quickstart notebook
├── dev/                            ← developer documentation (you are here)
├── pyproject.toml                  ← package metadata and dependencies
└── .github/workflows/              ← CI/CD automation
```

---

## The source files in detail

### `cli.py` — the entry point

This is the front door of the package. When someone runs the `fastapifromfrictionless generate` command in a terminal, Python calls `main()` in this file.

```
User runs command
       │
       ▼
   cli.py  main()
       │
       ├──► model.py   → builds models.py
       ├──► app.py     → builds app.py
       └──► database.py→ builds database.py
```

It accepts flags like `--dry-run` (print to screen without writing files), `--no-models`, `--no-app`, and `--no-db` to skip specific outputs.

---

### `validate.py` — schema checker

Before any code is generated, this module checks that the schema files are valid. It is called automatically by `model.py` before generation starts.

| Check | What it catches |
|-------|-----------------|
| Folder exists | Typo in the path passed to the CLI |
| At least one `.schema.yaml` file found | Empty folder |
| Each schema loads without error | Malformed YAML or invalid field types |
| Foreign keys point to real schemas | A reference like `survey_id` pointing to a schema that doesn't exist |

If any check fails, generation stops with a clear error message listing every problem found.

---

### `model.py` — generates `models.py`

This file contains the `models` class. It reads each `.schema.yaml` file and translates it into Python class definitions that SQLModel understands.

**What is SQLModel?**
SQLModel is a library that lets you define a database table and its data shape using a single Python class. It bridges FastAPI (the web framework) and the database.

**What the generator does for each schema:**

```
schema.yaml
    │
    │  reads field names and types
    ▼
type_map (dictionary in model.py)
    │
    │  converts e.g. "string" → "str", "integer" → "int",
    │  "geopoint" → "Geometry('POINT')"
    ▼
model_block.py.jinja2
    │
    │  fills in a template to produce several classes:
    ▼
  SurveyBase          ← shared fields
  Survey              ← the actual database table
  SurveyCreate        ← shape for creating new records
  SurveyUpdate        ← shape for editing records (all fields optional)
  SurveyPublic        ← shape returned by the API
  SurveyPublicWithAll ← same but with related records included
```

It also detects:
- **Auto-incrementing IDs**: if a schema has `id` as its primary key, it gets `id: int | None = Field(default=None, primary_key=True)` automatically.
- **Foreign keys**: if a field name matches a pattern like `survey_id`, it becomes a database foreign key linking to the `survey` table.
- **Relationships**: it scans all other schemas to find which ones reference the current one, then adds SQLModel `Relationship` fields so related records can be fetched together.
- **Link tables**: if a schema has exactly two foreign key fields and a composite primary key (two columns together form the unique key), it is treated as a many-to-many join table.

---

### `app.py` — generates `app.py`

This file contains the `app` class. It reads each schema and generates a set of HTTP routes (endpoints) for it.

**What endpoints are generated per schema?**

| Method | URL pattern | What it does |
|--------|-------------|--------------|
| `POST` | `/{resource}` | Create a new record |
| `GET` | `/{resource}/all` | Get all records (paginated) |
| `GET` | `/{resource}/recent` | Get the most recently created records |
| `GET` | `/{resource}/query` | Filtered query (only for schemas with foreign keys) |
| `GET` | `/{resource}/{id}` | Get a single record by its primary key |
| `PATCH` | `/{resource}/{id}` | Update a record |
| `DELETE` | `/{resource}/{id}` | Delete a record |

The `app_header.py.jinja2` template also adds the following shared infrastructure to every generated `app.py`:

| Feature | What it does |
|---------|--------------|
| API key auth | Checks `X-API-Key` header on every request if `API_KEY` env var is set |
| CORS middleware | Controls which websites can call the API (set via `ALLOWED_ORIGINS`) |
| Security headers | Adds `X-Frame-Options`, `Strict-Transport-Security`, etc. to every response |
| Error handlers | Returns consistent JSON error bodies for 404s, 422s, etc. |
| Startup hook | Creates all database tables on first run |
| `GET /excel/export` | Downloads the whole database as an `.xlsx` file |
| `POST /excel/import` | Uploads an `.xlsx` file and upserts all rows into the database |

---

### `database.py` — generates `database.py`

This is the simplest generator. It fills in the `database.py.jinja2` template with the database file path and produces a file that:

1. Creates a SQLAlchemy engine (the connection to the database)
2. Provides a `create_db_and_tables()` function that the generated `app.py` calls on startup

The generated app supports both SQLite (for local development) and PostgreSQL (for production — configured via the `DATABASE_URL` environment variable).

---

### `load.py` — Excel import and export

This module is **not a code generator** — it is utility code that the generated `app.py` imports at runtime to power the Excel endpoints.

**Key functions:**

| Function | What it does |
|----------|--------------|
| `dump_to_excel()` | Calls each `/{resource}/all` endpoint, collects the data, and writes it all to a multi-sheet `.xlsx` file |
| `create_package()` | Reads an uploaded `.xlsx` file and builds a Frictionless `Package` YAML that describes its contents |
| `update_api_from_package()` | Reads a Frictionless Package, then for each sheet calls `GET /all` to see what already exists, and upserts rows using `POST` (new) or `PATCH` (existing) |
| `requests_get_all()` | Helper — fetches all rows from one endpoint, returns a pandas DataFrame |
| `requests_post()` | Helper — creates one new record via `POST` |
| `requests_update()` | Helper — updates one record via `PATCH` |

**How import works end-to-end:**

```
User uploads export.xlsx
         │
         ▼
import_excel()  (in generated app.py)
         │
         ├──► create_package()
         │         reads the xlsx, creates a .package.yaml
         │         describing its sheets and columns
         │
         └──► update_api_from_package()
                   for each sheet:
                     GET /{resource}/all  (fetch current state)
                     compare row by row
                     POST  for new rows
                     PATCH for changed rows
```

> **Note:** `update_api_from_package` calls the API's own endpoints over HTTP. The session it creates includes the `X-API-Key` header so these internal requests are not rejected when authentication is enabled.

---

### `logging_config.py` — logging helper

A small utility. Call `configure_logging()` at the start of a script to turn on structured log output from the package. By default nothing is printed — this lets the package be imported silently into other projects.

```python
from fastapifromfrictionless import configure_logging
configure_logging(level="DEBUG")   # now you'll see detailed logs
```

---

### `__init__.py` — the public surface

This file defines what is exported when someone does `import fastapifromfrictionless`. It sets the version number and exposes the most useful functions.

The generator classes (`app`, `models`, `database`) are imported inside a `try/except` block — this means the package can be installed in a "runtime-only" mode (without Jinja2 and the full Frictionless library) and still work for the Excel import/export functions.

---

## The templates

The `templates/` folder contains [Jinja2](https://jinja.palletsprojects.com/) template files. A template is a text file with placeholders that get filled in by Python code. The placeholders use `<< variable >>` syntax (instead of the usual `{{ variable }}` — this avoids conflicts with Python's own `{` characters).

### How template rendering works

```
Python variables (name, fields, foreign_keys…)
                    │
                    ▼
          Jinja2 template file
          (model_block.py.jinja2)
                    │
                    ▼
          Rendered Python source code
          (class SurveyBase(SQLModel): ...)
```

### Template responsibilities

| Template | Produces | Purpose |
|----------|----------|---------|
| `models_header.py.jinja2` | Top of `models.py` | All imports, the `TimestampMixin` base class (adds `created_at` / `updated_at` to every table) |
| `model_block.py.jinja2` | One block per schema | The six model classes (`Base`, table, `Create`, `Update`, `Public`, `PublicWithAll`) |
| `app_header.py.jinja2` | Top of `app.py` | FastAPI setup, auth, CORS, middleware, startup hook, Excel endpoints |
| `endpoint_block.py.jinja2` | One block per schema | The seven CRUD routes for that resource |
| `database.py.jinja2` | The full `database.py` | Engine, session factory, `create_db_and_tables()` |

---

## How a schema becomes code

Here is a concrete example. Given this schema file (`survey.schema.yaml`):

```yaml
fields:
  - name: id
    type: integer
  - name: title
    type: string
    constraints:
      required: true
  - name: created_date
    type: date
primaryKey: [id]
```

The generator produces (simplified):

```python
# in models.py
class SurveyBase(SQLModel):
    title: str
    created_date: date | None

class Survey(SurveyBase, TimestampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)

class SurveyCreate(SurveyBase):
    pass

class SurveyUpdate(SurveyBase):
    title: str | None
    created_date: date | None

class SurveyPublic(SurveyBase):
    id: int
    created_at: datetime
    updated_at: datetime

# in app.py
@app.post('/survey', response_model=SurveyPublic)
def create_survey(*, session: Session = Depends(get_session), survey: SurveyCreate):
    ...

@app.get('/survey/all', response_model=list[SurveyPublic])
def read_surveys(*, session: Session = Depends(get_session), offset: int = 0, limit: int = ...):
    ...
```

---

## Dependencies

| Library | Role |
|---------|------|
| **frictionless** | Reads and validates `.schema.yaml` files |
| **jinja2** | Fills in the code templates |
| **FastAPI** | The web framework used in generated `app.py` |
| **SQLModel** | Combines Pydantic (data validation) and SQLAlchemy (database) |
| **sqlalchemy** | Low-level database engine |
| **pandas** | Used in `load.py` to read/write tabular data |
| **xlsxwriter** | Used in `load.py` to create `.xlsx` files |
| **requests** | Used in `load.py` to call the API's own endpoints during import |
| **python-multipart** | Enables file uploads (`POST /excel/import`) |
| **geoalchemy2** | Adds PostGIS geometry column support |
| **fastapi_querybuilder** | Powers the `/query` filtered endpoint |

The package has two install modes:

```
pip install fastapifromfrictionless          ← runtime only (no code generation)
pip install fastapifromfrictionless[generate] ← includes jinja2 + frictionless for generation
```

---

## CI/CD workflows

The `.github/workflows/` folder contains four automation files that run on GitHub:

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `ci.yml` | Every push / PR | Runs `ruff` (linting), `mypy` (type checking), `pytest` (tests) |
| `python-publish.yml` | A GitHub release is published | Builds the wheel and uploads it to PyPI |
| `build-images.yml` | After PyPI publish succeeds | Pulls the new version from PyPI, builds Docker/Podman base images, pushes to `ghcr.io` |
| `todo_to_issue.yml` | Push to `main` | Scans code for `# TODO` comments and opens GitHub issues automatically |

**The release pipeline in sequence:**

```
Developer creates a GitHub release
              │
              ▼
     python-publish.yml
     builds wheel → uploads to PyPI
              │
              ▼ (triggered automatically)
     build-images.yml
     waits for PyPI CDN to serve the new version
     builds generator base image (pip install fastapifromfrictionless[generate])
     builds runtime base image   (pip install fastapifromfrictionless)
     pushes both to ghcr.io with :latest and :<version> tags
```

---

## Data flow during a live API request

```
HTTP request arrives
(e.g. GET /survey/42)
        │
        ▼
FastAPI router (app.py)
        │
        ├──► verify_api_key()    checks X-API-Key header
        │
        ▼
read_survey()  endpoint function
        │
        ├──► get_session()       opens a database connection
        │
        ├──► session.get(Survey, 42)
        │         SQLAlchemy translates this to:
        │         SELECT * FROM survey WHERE id = 42
        │
        ▼
SurveyPublic  Pydantic validates and shapes the result
        │
        ▼
JSON response  {"id": 42, "title": "...", "created_at": "..."}
```

---

## Adding a new schema

To add a new data table:

1. Create `schemas/mynewtable.schema.yaml` following the Frictionless schema format.
2. Run the generator: `python -m fastapifromfrictionless.cli generate schemas/ --output api/`
3. Rebuild the container image (generation happens at build time).

The new table and all seven CRUD endpoints appear automatically. No other files need to be edited.
