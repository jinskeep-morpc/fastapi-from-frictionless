"""Command-line interface for fastapifromfrictionless."""

import argparse
import pathlib


def _generate(args):
    from .app import app
    from .database import database
    from .model import models

    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    models(args.schema_folder).build().save(out / "models.py")
    app(args.schema_folder).build().save(out / "app.py")
    database(args.schema_folder).build(args.db_filename).save(out / "database.py")
    (out / "__init__.py").touch()

    print(f"Generated app.py, models.py, database.py in {out}")


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
    gen.set_defaults(func=_generate)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
