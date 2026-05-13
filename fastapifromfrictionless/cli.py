"""Command-line interface for fastapifromfrictionless."""

import argparse
import pathlib


def _generate(args):
    from .app import app
    from .database import database
    from .model import models

    models_gen = models(args.schema_folder).build()
    app_gen = app(args.schema_folder).build()
    db_gen = database(args.schema_folder).build(args.db_filename)

    if args.dry_run:
        _print_preview("models.py", models_gen)
        _print_preview("app.py", app_gen)
        _print_preview("database.py", db_gen)
        return

    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    models_gen.save(out / "models.py")
    app_gen.save(out / "app.py")
    db_gen.save(out / "database.py")
    (out / "__init__.py").touch()

    print(f"Generated app.py, models.py, database.py in {out}")


def _print_preview(filename, generator):
    print(f"\n{'=' * 60}")
    print(f"# {filename}")
    print(f"{'=' * 60}")
    if hasattr(generator, "models"):
        # models generator stores header separately
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
    gen.set_defaults(func=_generate)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
