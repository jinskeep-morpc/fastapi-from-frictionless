"""Unit tests for the CLI entry point."""

import textwrap

import pytest

from fastapifromfrictionless.cli import main


def write_schema(tmp_path, name, content):
    (tmp_path / f"{name}.schema.yaml").write_text(textwrap.dedent(content))


@pytest.fixture()
def schema_folder(tmp_path):
    src = tmp_path / "schemas"
    src.mkdir()
    write_schema(
        src,
        "item",
        """\
        fields:
          - name: id
            type: integer
          - name: label
            type: string
        primaryKey:
          - id
        """,
    )
    return src


def test_generate_creates_models_py(schema_folder, tmp_path):
    out = tmp_path / "out"
    main(["generate", str(schema_folder), "--output", str(out)])
    assert (out / "models.py").exists()


def test_generate_creates_app_py(schema_folder, tmp_path):
    out = tmp_path / "out"
    main(["generate", str(schema_folder), "--output", str(out)])
    assert (out / "app.py").exists()


def test_generate_creates_database_py(schema_folder, tmp_path):
    out = tmp_path / "out"
    main(["generate", str(schema_folder), "--output", str(out)])
    assert (out / "database.py").exists()


def test_generate_custom_db_filename(schema_folder, tmp_path):
    out = tmp_path / "out"
    main(["generate", str(schema_folder), "--output", str(out), "--db", "myapp.db"])
    content = (out / "database.py").read_text()
    assert "myapp.db" in content


def test_generate_default_db_filename(schema_folder, tmp_path):
    out = tmp_path / "out"
    main(["generate", str(schema_folder), "--output", str(out)])
    content = (out / "database.py").read_text()
    assert "database.db" in content


def test_no_command_exits():
    with pytest.raises(SystemExit):
        main([])
