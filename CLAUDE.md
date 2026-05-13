# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`fastapifromfrictionless` is a Python package (WIP) that reads [Frictionless Data Package](https://datapackage.org/standard/data-package/) schema files (`*.schema.yaml`) and **generates** Python source files for a fully-functional FastAPI + SQLModel application. The package is also the scaffolding tool — it generates the code that users then run as a standalone service.

## Install

```bash
pip install -e .
```

No test suite exists. Development happens primarily through the notebooks in `doc/`.

## Run the generated app

After running `build_database()` in a target directory, a `app.py`, `models.py`, and `database.py` are created there. Start the app with:

```bash
uvicorn app:app --reload
```

## Core architecture

The package has two distinct layers:

### 1. Code generators (`fastapifromfrictionless/`)

Three classes each read a folder of `*.schema.yaml` files and write a Python source file:

| Class | Input | Output |
|---|---|---|
| `models(folder)` | schemas | `models.py` — SQLModel class hierarchies |
| `app(folder)` | schemas | `app.py` — FastAPI CRUD + query routes |
| `database(folder)` | db filename | `database.py` — SQLite engine setup |

All three follow the same `.build().save(path)` pattern. `build_database()` in `load.py` calls all three in sequence.

### 2. Excel ↔ API data workflow (`load.py`)

Four utility functions bridge an Excel workbook with a running API:

- `empty_excel(schema_folder, output_filepath)` — creates a blank `.xlsx` with one sheet per schema (column headers from field names)
- `create_package(folder, filename)` — wraps the Excel file in a frictionless `.package.yaml` that maps each sheet to its schema
- `update_api_from_package(api_url, package_file)` — reads each sheet via the package, compares rows to the live API, and POSTs new rows or PATCHes changed ones
- HTTP helpers: `requests_post`, `requests_get_all`, `requests_update`

### Frictionless schema → SQLModel mapping

`model.py` applies these rules when generating classes for each schema:

- **`id` in `primaryKey`** → table model gets `id: int | None = Field(default=None, primary_key=True)` (auto-increment); omitted from Base
- **Two foreign keys + composite primary key** → detected as a many-to-many link table
- **`constraints.required: true`** on a field → non-optional type; absence → `type | None`
- **Foreign key convention**: field named `{table}_{column}` maps to `foreign_key='{table}.{column}'`  (underscore-to-dot substitution)
- **Relationships**: cross-schema detection — each schema is scanned for foreign keys pointing at other schemas to build bidirectional `Relationship` fields

Per schema, six model classes are generated:
1. `{Name}Base` — field definitions
2. `{Name}` (table=True) — adds `TimestampMixin` (`created_at`, `updated_at`) and all `Relationship` fields
3. `{Name}Create` — for POST body
4. `{Name}Update` — all fields made optional, for PATCH body
5. `{Name}Public` — includes `id` and timestamps
6. `{Name}PublicWithAll` — extends Public with nested related models (generated only if FK relationships exist)

### Generated FastAPI endpoint pattern

For each schema, `app.py` generates:
- `POST /{name}` — create
- `GET /{name}/all` — list all (uses `PublicWithAll` if relationships exist)
- `GET /{name}/{pk}` — get single
- `PATCH /{name}/{pk}` — update
- `DELETE /{name}/{pk}` — delete
- `GET /{name}/query` (only when schema has foreign keys) — `fastapi_querybuilder` dynamic query endpoint

## `doc/` directory

Contains a worked example (sensor tracking) with real schemas, a generated app, and Jupyter devlogs. The `doc/data/` schemas are the canonical usage reference. Generated files (`doc/app.py`, `doc/models.py`, `doc/database.py`) show expected output.

## Development Workflow

Follow these steps in order for every task:

For each item in the roadmap:

1. **Create a GitHub issue** — open an issue in this repo describing the work before making any changes.
2. **Create/switch branch** — create and check out the new branch from the issue.
3. **Make changes in logical commits** — implement the work; commit in small, focused units with clear messages.
4. **Write tests** — add or update tests covering the changes.
5. **Prepend notes to `reference/dev_notes.md`** — prepend a brief summary of what was done and why. Do **not** read the file first; always prepend only.
6. **Update README.md**  — update the readme to update the completed roadmap item and any changes to other sections. 
6. **Create the PR** — open a pull request against the main branch with a clear title and summary.

### Additional rules

- **grep/read before reading full files** — use `grep` or targeted reads to locate relevant sections before reading an entire file.
- **`reference/dev_notes.md` is prepend-only** — never read this file before writing; always write new content at the top.
