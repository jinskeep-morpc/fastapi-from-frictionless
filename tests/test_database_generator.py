"""Unit tests for the database.py code generator."""

import pytest

from fastapifromfrictionless import database


@pytest.fixture()
def folder(tmp_path):
    return tmp_path


def test_build_returns_self(folder):
    db = database(str(folder))
    result = db.build("test.db")
    assert result is db


def test_output_contains_db_filename(folder):
    db = database(str(folder)).build("my_app.db")
    assert "my_app.db" in db.database


def test_output_contains_sqlite_url(folder):
    db = database(str(folder)).build("app.db")
    assert "sqlite:///" in db.database


def test_output_contains_engine_creation(folder):
    db = database(str(folder)).build("app.db")
    assert "create_engine" in db.database


def test_output_contains_create_db_function(folder):
    db = database(str(folder)).build("app.db")
    assert "def create_db_and_tables()" in db.database
    assert "SQLModel.metadata.create_all(engine)" in db.database


def test_database_url_env_var_in_output(folder):
    db = database(str(folder)).build("app.db")
    assert "DATABASE_URL" in db.database
    assert "os.getenv" in db.database


def test_save_writes_file(folder, tmp_path):
    out = tmp_path / "database.py"
    database(str(folder)).build("app.db").save(out)
    assert out.exists()
    content = out.read_text()
    assert "create_engine" in content
    assert "app.db" in content


def _load_generated(folder, tmp_path, monkeypatch, url):
    """Generate database.py, import it with DATABASE_URL=url, and return the module."""
    import importlib.util

    out = tmp_path / "database.py"
    database(str(folder)).build("app.db").save(out)
    monkeypatch.setenv("DATABASE_URL", url)
    spec = importlib.util.spec_from_file_location("generated_database", out)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@db:5432/app",
        "postgres://u:p@db:5432/app",
    ],
)
def test_bare_postgres_url_uses_psycopg2(folder, tmp_path, monkeypatch, url):
    """#179: SQLAlchemy 2.1 maps a bare postgresql:// to psycopg 3, which the app does not ship."""
    module = _load_generated(folder, tmp_path, monkeypatch, url)
    assert module.engine.dialect.driver == "psycopg2"
    assert module.database_url == "postgresql+psycopg2://u:p@db:5432/app"


def test_url_naming_a_driver_is_left_alone(folder, tmp_path, monkeypatch):
    url = "postgresql+psycopg2://u:p@db:5432/app"
    module = _load_generated(folder, tmp_path, monkeypatch, url)
    assert module.database_url == url


def test_sqlite_url_is_left_alone(folder, tmp_path, monkeypatch):
    url = "sqlite:///other.db"
    module = _load_generated(folder, tmp_path, monkeypatch, url)
    assert module.database_url == url
    assert module.engine.dialect.name == "sqlite"
