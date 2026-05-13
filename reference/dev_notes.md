## 2026-05-13 — Issue #12: dump_to_excel

Added `dump_to_excel(api_url, schema_folder, output_filepath)` to `load.py`. Fetches all records from each endpoint, reorders columns to match schema field order, handles endpoint errors gracefully (writes empty sheet instead of aborting), and autofits columns. Also created `tests/` with 4 pytest tests covering data rows, empty API, error resilience, and column ordering.

---

## 2026-05-13 — Issue #10: README rewrite

Rewrote README to replace the rough WIP checklist with a proper package overview, requirements list, Quick Start, and a structured production roadmap (Foundation → Code Quality → Production Readiness → Developer Experience → Optional). Also added CLAUDE.md with the 9-step development workflow and coding guidelines. No code changes.

---

