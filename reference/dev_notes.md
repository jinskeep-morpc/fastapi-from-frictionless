## 2026-05-13 — Issue #22: Type hints and mypy

Fixed 19 mypy errors across the package: (1) renamed loop variable `field` to `field_name` in `model.py` to avoid shadowing between `str` and `frictionless.Field` types; (2) annotated `basemodel_fields: list[str]` explicitly; (3) cast `PathLike` to `str` in `logging.getChild()` calls in `model.py` and `app.py`; (4) stored `self.folder` as `str` in both generators; (5) replaced `filename.split(".")` with `pathlib.Path(filename).stem` in `load.py`. Added `[tool.mypy]` config to `pyproject.toml`, `mypy` to `[dev]` extras, and a mypy step to the CI workflow. Also fixed 51 ruff issues and reformatted all source files. mypy and all 44 tests clean.

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

