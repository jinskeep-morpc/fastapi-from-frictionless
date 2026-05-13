"""Command-line interface for fastapifromfrictionless."""

import argparse
import pathlib


def _generate(args):
    from .app import app
    from .database import database
    from .model import models

    gen_models = not args.no_models
    gen_app = not args.no_app
    gen_db = not args.no_db

    models_gen = models(args.schema_folder).build() if gen_models else None
    app_gen = app(args.schema_folder).build() if gen_app else None
    db_gen = database(args.schema_folder).build(args.db_filename) if gen_db else None

    if args.dry_run:
        if models_gen:
            _print_preview("models.py", models_gen)
        if app_gen:
            _print_preview("app.py", app_gen)
        if db_gen:
            _print_preview("database.py", db_gen)
        return

    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    if models_gen:
        models_gen.save(out / "models.py")
    if app_gen:
        app_gen.save(out / "app.py")
    if db_gen:
        db_gen.save(out / "database.py")
    if gen_models or gen_app or gen_db:
        (out / "__init__.py").touch()

    generated = [
        f
        for f, flag in [("models.py", gen_models), ("app.py", gen_app), ("database.py", gen_db)]
        if flag
    ]
    print(f"Generated {', '.join(generated)} in {out}")


def _print_preview(filename, generator):
    print(f"\n{'=' * 60}")
    print(f"# {filename}")
    print(f"{'=' * 60}")
    if hasattr(generator, "models"):
        from .model import _env

        header = _env.get_template("models_header.py.jinja2").render()
        print(header + "".join(generator.models))
    elif hasattr(generator, "endpoints"):
        from .app import _env

        header = _env.get_template("app_header.py.jinja2").render()
        print(header + "".join(generator.endpoints))
    else:
        print(generator.database)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="fastapifromfrictionless",
        description="Generate a FastAPI + SQLModel app from Frictionless schema files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser(
        "generate",
        help="Generate app.py, models.py, and database.py from *.schema.yaml files.",
    )
    gen.add_argument("schema_folder", help="Folder containing *.schema.yaml files.")
    gen.add_argument(
        "--output",
        default=".",
        help="Output directory for generated files (default: current directory).",
    )
    gen.add_argument(
        "--db",
        dest="db_filename",
        default="database.db",
        help="SQLite database filename (default: database.db).",
    )
    gen.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print generated file contents to stdout without writing files.",
    )
    gen.add_argument(
        "--no-models", action="store_true", default=False, help="Skip generating models.py."
    )
    gen.add_argument("--no-app", action="store_true", default=False, help="Skip generating app.py.")
    gen.add_argument(
        "--no-db", action="store_true", default=False, help="Skip generating database.py."
    )
    gen.set_defaults(func=_generate)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
