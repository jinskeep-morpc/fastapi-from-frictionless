# fastapi-from-frictionless

> **Status: Work in Progress** — API and generated output are subject to change.

## Overview

`fastapifromfrictionless` is a Python scaffolding tool that reads [Frictionless Data Package](https://datapackage.org/standard/data-package/) schema files and generates a fully-functional [FastAPI](https://fastapi.tiangolo.com/) + [SQLModel](https://sqlmodel.tiangolo.com/) application — including models, CRUD endpoints, and dynamic query support — with no hand-written boilerplate.

The driving goal is to bridge the gap between familiar flat-file workflows (Excel workbooks, CSV files, Frictionless packages) and a production-grade relational database with a queryable REST API. Data stewards continue working in Excel; the package handles ingestion, validation, and API synchronization behind the scenes.

**Core capabilities:**

- Generate `models.py`, `app.py`, and `database.py` from `*.schema.yaml` files
- Automatic SQLModel class hierarchy per schema (base, table, create, update, public, public-with-relations)
- Full CRUD + dynamic query endpoints per resource
- Excel workbook as a data-entry interface — create or update API records from a `.xlsx` file
- Frictionless package wraps the workbook for field-level validation before ingestion

## Requirements

- Python >= 3.10
- [frictionless](https://pypi.org/project/frictionless/)
- [FastAPI](https://pypi.org/project/fastapi/)
- [SQLModel](https://pypi.org/project/sqlmodel/)
- [SQLAlchemy](https://pypi.org/project/sqlalchemy/)
- [fastapi-querybuilder](https://github.com/bhadri01/fastapi-querybuilder)
- [requests](https://pypi.org/project/requests/)
- [pandas](https://pypi.org/project/pandas/)
- [xlsxwriter](https://pypi.org/project/XlsxWriter/)

An ASGI server such as [uvicorn](https://www.uvicorn.org/) is required to run the generated application.

## Installation

```bash
pip install -e .
```

## Quick Start

1. Place `*.schema.yaml` files in a folder (see `doc/data/` for examples).
2. Run the build function to generate application files:

```python
from fastapifromfrictionless.load import build_database

build_database(schema_folder="path/to/schemas", output_dir="path/to/output")
```

3. Start the generated API:

```bash
uvicorn app:app --reload
```

4. (Optional) Create a blank Excel workbook pre-formatted for data entry:

```python
from fastapifromfrictionless.load import empty_excel

empty_excel(schema_folder="path/to/schemas", output_filepath="data.xlsx")
```

5. Ingest data from a filled-in workbook:

```python
from fastapifromfrictionless.load import create_package, update_api_from_package

create_package(folder="path/to/schemas", filename="data.xlsx")
update_api_from_package(api_url="http://localhost:8000", package_file="data.package.yaml")
```

See `doc/` for a worked example with real schemas and generated output.

## Roadmap

Items are grouped by priority. Checked items are complete.

### Foundation

- [x] Generate SQLModel class hierarchies from Frictionless schemas
- [x] Generate FastAPI CRUD + query endpoints per resource
- [x] Generate `database.py` with SQLite engine setup
- [x] Excel workbook as data-entry interface (create and update)
- [x] Frictionless package wrapping for field-level validation
- [ ] Export API data back to Excel (dump all records to workbook)
- [ ] Validate schemas before code generation; surface clear error messages on malformed input

### Code Quality & Reliability

- [ ] Add a test suite (unit tests for generators, integration tests for generated app)
- [ ] Add CI pipeline (lint, type-check, tests on push)
- [ ] Enforce type hints throughout; run `mypy` in CI
- [ ] Replace raw string generation with a templating engine (e.g. Jinja2) for maintainability
- [ ] Structured logging with configurable verbosity

### Production Readiness

- [ ] Async database support (replace sync SQLModel sessions with async SQLAlchemy)
- [ ] Database migrations via [Alembic](https://alembic.sqlalchemy.org/) instead of `create_all`
- [ ] Configuration management — accept settings via environment variables or a config file (database URL, allowed origins, etc.)
- [ ] CORS and security headers in generated `app.py`
- [ ] API key / token authentication ([FastAPI security](https://fastapi.tiangolo.com/tutorial/security/first-steps/))
- [ ] Pagination on list endpoints
- [ ] Proper HTTP error responses with consistent JSON error bodies

### Developer Experience

- [ ] CLI entry point (`fastapifromfrictionless generate <schema-folder>`) so users do not need to write Python
- [ ] Dry-run / preview mode that prints generated code without writing files
- [ ] Configurable output — opt in/out of specific endpoint types, choose database backend
- [ ] Package versioning and automated releases (GitHub Actions → PyPI)
- [ ] Expand documentation and examples in `doc/`

### Optional / Future

- [ ] Support for PostgreSQL and other SQLAlchemy-compatible backends
- [ ] Auto-generated front-end form from schema fields
- [ ] DrawIO ERD → Frictionless schema converter
- [ ] Default query routes for common patterns derived from schema metadata
- [ ] GET/POST file endpoints for uploading and downloading the Excel workbook directly via the API
