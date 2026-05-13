## 2026-05-13 — Issue #14: Schema validation before code generation

Added `fastapifromfrictionless/validate.py` with `validate_schemas(folder)` and `assert_schemas_valid(folder)`. Validation checks: folder exists and contains schemas, each schema loads cleanly via frictionless (which catches bad types and PK mismatches), and FK references point to known schemas in the same folder. `assert_schemas_valid` is called in `models.__init__` so bad schemas raise `ValueError` with a full error list before any code is generated. Exported both functions from `__init__.py`. 10 pytest tests all passing.
## 2026-05-13 — Issue #12: dump_to_excel

Added `dump_to_excel(api_url, schema_folder, output_filepath)` to `load.py`. Fetches all records from each endpoint, reorders columns to match schema field order, handles endpoint errors gracefully (writes empty sheet instead of aborting), and autofits columns. Also created `tests/` with 4 pytest tests covering data rows, empty API, error resilience, and column ordering.

---

## 2026-05-13 — Issue #10: README rewrite

Rewrote README to replace the rough WIP checklist with a proper package overview, requirements list, Quick Start, and a structured production roadmap (Foundation → Code Quality → Production Readiness → Developer Experience → Optional). Also added CLAUDE.md with the 9-step development workflow and coding guidelines. No code changes.

---

