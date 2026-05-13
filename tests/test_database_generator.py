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


def test_save_writes_file(folder, tmp_path):
    out = tmp_path / "database.py"
    database(str(folder)).build("app.db").save(out)
    assert out.exists()
    content = out.read_text()
    assert "create_engine" in content
    assert "app.db" in content
