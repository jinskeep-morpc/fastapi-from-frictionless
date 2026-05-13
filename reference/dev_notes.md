## 2026-05-13 — Issue #20: CI pipeline

Added `.github/workflows/ci.yml` — runs `ruff check`, `ruff format --check`, and `pytest` on every push/PR. Added `[dev]` optional dependencies to `pyproject.toml` (`pip install -e ".[dev]"`). Configured ruff with `target-version = "py312"` (codebase uses 3.12 f-string syntax), `line-length = 100`, and ignores for E501/E402/F403/F401. Fixed 61 lint issues across the package and formatted all source files. All 44 tests still passing.

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

