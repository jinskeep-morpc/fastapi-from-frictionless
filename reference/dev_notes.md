## 2026-05-14 — Pin package version in base image builds to avoid PyPI CDN lag (#91)

The Dockerfiles for base images installed fastapifromfrictionless without a version pin. When build-images.yml fired right after the PyPI publish, pip sometimes got the previous cached version. Added ARG PACKAGE_VERSION to both Dockerfiles and a PyPI polling step in the workflow that retries up to 12 minutes before starting the Docker builds. The workflow also now passes build-args: PACKAGE_VERSION=... to both builds.
## 2026-05-14 — Fix Frictionless 'any' type → typing.Any has no SQLAlchemy mapping (#89)

Frictionless 'any' type was mapped to typing.Any in the type_map, but typing.Any has no SQLAlchemy column type, causing ValueError at startup for any schema with an 'any' field. Changed mapping to 'str' (stored as text). Updated the corresponding test. 90 tests passing.
## 2026-05-14 — Fix NameError: Any not imported in generated models header (#85)

The models_header.py.jinja2 template imported Optional and List from typing but not Any, causing NameError at startup for schemas with field types 'any', 'object', or 'array'. Added Any to the import. 90 tests passing.
## 2026-05-14 — Fix geoalchemy2 missing dependency (#81)

Schemas without geo field types raised ModuleNotFoundError because models_header.py.jinja2 unconditionally imported from geoalchemy2. Added has_geo tracking in model.build() and made the import conditional in the template. Also added geoalchemy2 to pyproject.toml base dependencies and podman/Dockerfile.runtime-base so the runtime image includes it. 89 tests passing.
## Issue #66 — Update README and quickstart notebook

Fixed docs that became stale after the multi-stage Dockerfile (#60) and pre-built base images (#63):
- README Deployment section: three containers not two, explicit build step, pre-built image callout
- Notebook Step 1: updated folder listing, pre-built image explanation
- Notebook Step 3: added SCHEMA_FOLDER to .env example
- Notebook Step 4: rewritten — generation is at build time, not startup
- Notebook Step 8: rewritten — schema changes require rebuild not restart

---

## Issue #63 — Pre-built base images for faster Podman deployment

Added two base images published to ghcr.io on each release via `.github/workflows/build-images.yml`:
- `ghcr.io/jinskeep-morpc/fastapi-from-frictionless-generator` — python:3.12-slim + [generate] extras
- `ghcr.io/jinskeep-morpc/fastapi-from-frictionless-runtime` — python:3.12-slim + runtime deps

`podman/Dockerfile` now pulls these instead of re-running pip from scratch. Build time drops from ~3 min to ~20 s. Released as v0.2.1.

---

## Issue #60 — SCHEMA_FOLDER env variable

Made the schema folder name configurable via `SCHEMA_FOLDER` (default: `schemas`). The variable threads through the Dockerfile `ARG`, the compose `build.args`, and the runtime volume mount (`./${SCHEMA_FOLDER:-schemas}:/schemas:Z`). Updated `.env.example` and `podman/README.md` to document it.

---

## 2026-05-14 — Issue #60: Multi-stage Dockerfile

Moved `frictionless` and `jinja2` to an optional `[generate]` extra in `pyproject.toml` (also added both to `[dev]` so CI tests still pass). Made `validate.py` frictionless import lazy (moved inside functions). Removed dead top-level frictionless imports from `load.py`. Two-stage `podman/Dockerfile`: Stage 1 installs `fastapifromfrictionless[generate]`, copies `schemas/`, and generates the app code; Stage 2 installs the slim base (no frictionless/jinja2) and runs uvicorn against the pre-built code. Simplified `entrypoint.sh` (no generation step). Updated `podman/README.md` to document the new build-time generation workflow.

---

## 2026-05-14 — Issue #58: Replace doc/ with quickstart notebook

Removed all legacy content from `doc/` (two devlog notebooks, stale generated Python files pre-dating the Jinja2 templates, `__pycache__`, `.log`, `.db`). Created `doc/quickstart.ipynb`: a 9-step narrative walkthrough of the podman deployment workflow — define schemas (Python cells writing YAML), configure `.env`, start the stack (`podman-compose up -d`), explore the API (requests cells that work against a live stack), browse with pgAdmin, Excel import/export, schema updates, and cleanup. Shell commands shown inline in markdown; no attempt to run podman from within the notebook.

---

## 2026-05-14 — Issue #54: Podman deployment

Added `podman/` folder with six files: `compose.yaml` (two services — `postgres` using `docker.io/postgis/postgis` and `api` built from the local Dockerfile; shared bridge network `10.91.0.0/16` with static IPs following the podgis pattern), `Dockerfile` (Python 3.12-slim, installs `fastapifromfrictionless`, `uvicorn[standard]`, `psycopg2-binary`), `entrypoint.sh` (generates app files from mounted `/schemas` volume into `/app/api/` package at startup, then runs `uvicorn api.app:app`), `.env.example` (documents all env vars), `.gitignore` (ignores `.env` and `postgres/`), and `README.md` (setup instructions). The generated code uses relative imports so the entrypoint creates `api/__init__.py` to make the output directory a proper Python package before uvicorn starts.

---

## 2026-05-13 — Issue #52: Expand documentation

Rewrote README Quick Start with six numbered sections: CLI usage, starting the app, endpoint table per resource (POST, GET/all, GET/recent, GET/{pk}, PATCH, DELETE, GET/query, GET/excel/export, POST/excel/import), env var configuration table (DATABASE_URL, ALLOWED_ORIGINS, API_KEY, SCHEMA_FOLDER, API_URL), Excel workflow code examples, and CLI reference. Added jinja2 to Requirements list. Updated Core capabilities. No code changes.

---

## 2026-05-13 — Issue #50: Default query routes

Added `GET /{resource}/recent` endpoint to all generated schemas. Returns the N most recently created records ordered by `created_at.desc()`. Accepts `limit` param (default 10, max 100). Uses `TimestampMixin` which all table models already have. 3 tests added; all 82 pass.

---

## 2026-05-13 — Issue #48: GET/POST Excel file endpoints

Added `GET /excel/export` and `POST /excel/import` routes to the generated `app_header.py.jinja2`. Export calls `dump_to_excel()` using `API_URL` and `SCHEMA_FOLDER` env vars and returns an xlsx `FileResponse`. Import accepts an `UploadFile`, saves to a temp file, runs `create_package` + `update_api_from_package` to sync rows into the database. Added `File`, `UploadFile`, `FileResponse`, `tempfile`, and `Path` imports. 3 tests added; all 79 pass.

---

## 2026-05-13 — Issue #46: Package versioning and automated releases

Updated `.github/workflows/python-publish.yml`: now uses `ubuntu-latest`, `fetch-depth: 0` (so setuptools-scm can read git tags), Python 3.12 consistent with CI, and correct PyPI URL (`fastapifromfrictionless`). Added `[tool.setuptools_scm]` section to `pyproject.toml` documenting the path to full scm-based versioning. Release is triggered by creating a GitHub Release (publishing a `v*` tag).

---

## 2026-05-13 — Issue #44: Configurable output

Added `--no-models`, `--no-app`, `--no-db` flags to the CLI `generate` subcommand. Each defaults to False (all files generated). Useful when iterating on schemas after initial setup to regenerate only the changed file. 3 tests added; all 76 pass.

---

## 2026-05-13 — Issue #42: Dry-run / preview mode

Added `--dry-run` flag to the CLI `generate` subcommand. When set, generated file contents are printed to stdout (with `===` separators per file) instead of written to disk. Reuses the same Jinja2 environment and generator objects, just routes output to print instead of file.write. 4 tests added; all 73 pass.

---

## 2026-05-13 — Issue #40: API key authentication

Added `X-API-Key` header authentication to the generated `app_header.py.jinja2` template using FastAPI's `APIKeyHeader` and `Security`. If `API_KEY` env var is set, all requests must include a matching header (returns 403 otherwise). If unset, auth is disabled (dev-friendly default). Applied globally via `FastAPI(dependencies=[Depends(verify_api_key)])`. 2 tests added; all 69 pass.

---

## 2026-05-13 — Issue #38: CLI entry point

Added `fastapifromfrictionless/cli.py` with a `generate` subcommand. Accepts `schema_folder` positional arg, `--output` (default `.`), and `--db` (default `database.db`). Calls the three generators directly and writes files to the output directory. Wired via `[project.scripts]` in `pyproject.toml` so `pip install -e .` makes `fastapifromfrictionless generate <schema-folder>` available. 6 tests added; all 67 pass.

---

## 2026-05-13 — Issue #36: Configuration management

Generated `database.py` now reads `DATABASE_URL` from the environment, falling back to the default SQLite file. `connect_args` is set conditionally (`{"check_same_thread": False}` for SQLite, `{}` otherwise) to enable PostgreSQL or other backends in production. `ALLOWED_ORIGINS` was already in `app.py`. 1 test added; all 61 pass.

---

## 2026-05-13 — Issue #34: CORS and security headers

Added `CORSMiddleware` (origins from `ALLOWED_ORIGINS` env var, comma-separated, default `*` for development) and `SecurityHeadersMiddleware` (sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`) to the generated `app_header.py.jinja2` template. 2 tests added; all 60 pass.

---

## 2026-05-13 — Issue #32: Pagination

Added `offset: int = 0` and `limit: int = Query(default=100, le=1000)` parameters to all generated `GET /all` endpoints. Uses SQLModel's `.offset().limit()` chaining on the select statement. 3 tests added; all 58 pass.

---

## 2026-05-13 — Issue #30: HTTP error responses

Added custom `HTTPException` and `RequestValidationError` handlers to the generated `app_header.py.jinja2` template. Both return consistent JSON bodies: `{"error": ..., "status_code": ...}` for HTTP errors and `{"error": "Validation error", "detail": [...]}` for validation failures. 2 tests added; all 55 pass.

---

## 2026-05-13 — Issue #28: Structured logging

Added `fastapifromfrictionless/logging_config.py` with `configure_logging(level, fmt, datefmt)`. Sets level on the `fastapifromfrictionless` package root logger, clears existing handlers on repeated calls, attaches `StreamHandler(sys.stderr)` with a default format `%(asctime)s %(levelname)-8s %(name)s — %(message)s`, and sets `propagate=False`. Accepts both string level names (case-insensitive) and integer levels; raises `ValueError` for unknown strings. Exported from `__init__.py`. 9 tests added; all 53 pass.

---

## 2026-05-13 — Issue #26: Jinja2 templating

Replaced raw f-string generation in `model.py`, `app.py`, and `database.py` with Jinja2 templates in `fastapifromfrictionless/templates/`. Used custom delimiters (`<< >>` for variables, `<% %>` for blocks) to avoid conflicts with Python's `{}` syntax in generated code. All logic (FK detection, type mapping, relationship building) stays in Python; templates handle layout only. Added `jinja2` to runtime dependencies and `templates/*.jinja2` to package-data. Added `jinja2` to `pyproject.toml` runtime dependencies. All 44 tests pass; ruff and mypy clean.

---

## 2026-05-13 — Issue #22: Type hints and mypy

Fixed 19 mypy errors across the package: (1) renamed loop variable `field` to `field_name` in `model.py` to avoid shadowing between `str` and `frictionless.Field` types; (2) annotated `basemodel_fields: list[str]` explicitly; (3) cast `PathLike` to `str` in `logging.getChild()` calls in `model.py` and `app.py`; (4) stored `self.folder` as `str` in both generators; (5) replaced `filename.split(".")` with `pathlib.Path(filename).stem` in `load.py`. Added `[tool.mypy]` config to `pyproject.toml`, `mypy` to `[dev]` extras, and a mypy step to the CI workflow. Also fixed 51 ruff issues and reformatted all source files. mypy and all 44 tests clean.

---

## 2026-05-13 — Issue #20: CI pipeline

Added `.github/workflows/ci.yml` — runs `ruff check`, `ruff format --check`, and `pytest` on every push/PR. Added `[dev]` optional dependencies to `pyproject.toml` (`pip install -e ".[dev]"`). Configured ruff with `target-version = "py312"` (codebase uses 3.12 f-string syntax), `line-length = 100`, and ignores for E501/E402/F403/F401. Fixed 61 lint issues across the package and formatted all source files. All 44 tests still passing.

---
## 2026-05-13 — Issue #18: CLAUDE.md workflow refinement

User updated the development workflow: removed the "ask about branch" and "ask before PR" interactive steps to support fully autonomous operation. Added a "update README roadmap" step (step 6) after writing tests. No code changes.

---

## 2026-05-13 — Issue #16: Generator unit tests

Added 30 pytest tests across three files covering the models, app, and database generators. Tests operate on generated source strings (no code execution) using minimal inline `tmp_path` fixtures. Discovered and worked around a PosixPath vs str bug in the generators' logger initialization — generators must be passed `str` paths, not `pathlib.Path`. All 30 tests pass.
## 2026-05-13 — Issue #14: Schema validation before code generation

Added `fastapifromfrictionless/validate.py` with `validate_schemas(folder)` and `assert_schemas_valid(folder)`. Validation checks: folder exists and contains schemas, each schema loads cleanly via frictionless (which catches bad types and PK mismatches), and FK references point to known schemas in the same folder. `assert_schemas_valid` is called in `models.__init__` so bad schemas raise `ValueError` with a full error list before any code is generated. Exported both functions from `__init__.py`. 10 pytest tests all passing.
## 2026-05-13 — Issue #12: dump_to_excel

Added `dump_to_excel(api_url, schema_folder, output_filepath)` to `load.py`. Fetches all records from each endpoint, reorders columns to match schema field order, handles endpoint errors gracefully (writes empty sheet instead of aborting), and autofits columns. Also created `tests/` with 4 pytest tests covering data rows, empty API, error resilience, and column ordering.

---

## 2026-05-13 — Issue #10: README rewrite

Rewrote README to replace the rough WIP checklist with a proper package overview, requirements list, Quick Start, and a structured production roadmap (Foundation → Code Quality → Production Readiness → Developer Experience → Optional). Also added CLAUDE.md with the 9-step development workflow and coding guidelines. No code changes.

---


