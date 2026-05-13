## 2026-05-13 — Issue #16: Generator unit tests

Added 30 pytest tests across three files covering the models, app, and database generators. Tests operate on generated source strings (no code execution) using minimal inline `tmp_path` fixtures. Discovered and worked around a PosixPath vs str bug in the generators' logger initialization — generators must be passed `str` paths, not `pathlib.Path`. All 30 tests pass.

---

## 2026-05-13 — Issue #10: README rewrite

Rewrote README to replace the rough WIP checklist with a proper package overview, requirements list, Quick Start, and a structured production roadmap (Foundation → Code Quality → Production Readiness → Developer Experience → Optional). Also added CLAUDE.md with the 9-step development workflow and coding guidelines. No code changes.

---

