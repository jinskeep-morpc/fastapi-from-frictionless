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


def test_dry_run_does_not_write_files(schema_folder, tmp_path, capsys):
    out = tmp_path / "out"
    main(["generate", str(schema_folder), "--output", str(out), "--dry-run"])
    assert not (out / "models.py").exists()
    assert not (out / "app.py").exists()
    assert not (out / "database.py").exists()


def test_dry_run_prints_models(schema_folder, tmp_path, capsys):
    out = tmp_path / "out"
    main(["generate", str(schema_folder), "--output", str(out), "--dry-run"])
    captured = capsys.readouterr()
    assert "models.py" in captured.out
    assert "SQLModel" in captured.out


def test_dry_run_prints_app(schema_folder, tmp_path, capsys):
    out = tmp_path / "out"
    main(["generate", str(schema_folder), "--output", str(out), "--dry-run"])
    captured = capsys.readouterr()
    assert "app.py" in captured.out
    assert "FastAPI" in captured.out


def test_no_models_skips_models_py(schema_folder, tmp_path):
    out = tmp_path / "out"
    main(["generate", str(schema_folder), "--output", str(out), "--no-models"])
    assert not (out / "models.py").exists()
    assert (out / "app.py").exists()


def test_no_app_skips_app_py(schema_folder, tmp_path):
    out = tmp_path / "out"
    main(["generate", str(schema_folder), "--output", str(out), "--no-app"])
    assert not (out / "app.py").exists()
    assert (out / "models.py").exists()


def test_no_db_skips_database_py(schema_folder, tmp_path):
    out = tmp_path / "out"
    main(["generate", str(schema_folder), "--output", str(out), "--no-db"])
    assert not (out / "database.py").exists()
    assert (out / "models.py").exists()


def test_dry_run_prints_database(schema_folder, tmp_path, capsys):
    out = tmp_path / "out"
    main(["generate", str(schema_folder), "--output", str(out), "--dry-run"])
    captured = capsys.readouterr()
    assert "database.py" in captured.out
    assert "create_engine" in captured.out
