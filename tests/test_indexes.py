"""Indexes declared with `index:` on a field.

Two delivery paths that must agree on names, or a database ends up with the same
index twice under different ones: __table_args__ for create_db_and_tables() on a
fresh database, and a generated indexes.sql for one that already exists.
"""

import textwrap

import pytest

from fastapifromfrictionless import indexes, models


def write_schema(tmp_path, name, content):
    (tmp_path / f"{name}.schema.yaml").write_text(textwrap.dedent(content))


@pytest.fixture()
def indexed_folder(tmp_path):
    write_schema(
        tmp_path,
        "reading",
        """\
        fields:
          - name: sensor_index
            type: integer
            constraints: {required: true}
          - name: time_stamp
            type: datetime
            constraints: {required: true}
            index: brin
          - name: label
            type: string
            index: true
          - name: plain
            type: string
        primaryKey: [sensor_index, time_stamp]
        """,
    )
    return tmp_path


@pytest.fixture()
def unindexed_folder(tmp_path):
    write_schema(
        tmp_path,
        "plainthing",
        """\
        fields:
          - name: id
            type: integer
            constraints: {required: true}
        primaryKey: [id]
        """,
    )
    return tmp_path


def _models_text(folder, tmp_path):
    out = tmp_path / "models.py"
    models(str(folder)).build().save(out)
    return out.read_text()


def test_true_gives_a_default_index(indexed_folder, tmp_path):
    text = _models_text(indexed_folder, tmp_path)
    assert "Index('ix_reading_label', 'label')" in text


def test_a_named_method_is_passed_through(indexed_folder, tmp_path):
    """BRIN is the point: a btree on an append-only timestamp costs far more."""
    text = _models_text(indexed_folder, tmp_path)
    assert "Index('ix_reading_time_stamp', 'time_stamp', postgresql_using='brin')" in text


def test_undeclared_fields_get_no_index(indexed_folder, tmp_path):
    assert "'plain'" not in _models_text(indexed_folder, tmp_path)


def test_schema_without_declarations_has_no_table_args(unindexed_folder, tmp_path):
    text = _models_text(unindexed_folder, tmp_path)
    assert "__table_args__" not in text
    assert "Index" not in text


def test_generated_models_import_and_create(indexed_folder, tmp_path):
    """__table_args__ is only valid if SQLAlchemy accepts it; import and build."""
    import importlib.util
    import sys

    from sqlmodel import SQLModel, create_engine

    out = tmp_path / "models.py"
    models(str(indexed_folder)).build().save(out)
    spec = importlib.util.spec_from_file_location("generated_index_models", out)
    module = importlib.util.module_from_spec(spec)
    sys.modules["generated_index_models"] = module
    try:
        spec.loader.exec_module(module)
        engine = create_engine("sqlite://")
        SQLModel.metadata.create_all(engine)
        names = {ix.name for ix in module.Reading.__table__.indexes}
        assert {"ix_reading_time_stamp", "ix_reading_label"} <= names
        engine.dispose()
    finally:
        sys.modules.pop("generated_index_models", None)


def test_sql_matches_the_model_names(indexed_folder, tmp_path):
    """If these drift, a database gets the same index twice under two names."""
    text = _models_text(indexed_folder, tmp_path)
    sql = indexes(str(indexed_folder)).build().render()
    for name in ("ix_reading_time_stamp", "ix_reading_label"):
        assert name in text
        assert name in sql


def test_sql_is_idempotent_and_names_the_method(indexed_folder):
    sql = indexes(str(indexed_folder)).build().render()
    assert (
        "CREATE INDEX IF NOT EXISTS ix_reading_time_stamp ON reading USING brin (time_stamp);"
        in sql
    )
    assert "CREATE INDEX IF NOT EXISTS ix_reading_label ON reading (label);" in sql


def test_sql_says_so_when_nothing_is_declared(unindexed_folder):
    gen = indexes(str(unindexed_folder)).build()
    assert gen.specs == []
    assert "No indexes are declared" in gen.render()


def test_foreign_key_columns_are_not_indexed_twice(tmp_path):
    """The generator already sets index=True on a foreign key column."""
    write_schema(
        tmp_path,
        "owner",
        """\
        fields:
          - name: id
            type: integer
            constraints: {required: true}
        primaryKey: [id]
        """,
    )
    write_schema(
        tmp_path,
        "item",
        """\
        fields:
          - name: id
            type: integer
            constraints: {required: true}
          - name: owner_id
            type: integer
            index: true
        primaryKey: [id]
        foreignKeys:
          - fields: [owner_id]
            reference: {resource: owner, fields: [id]}
        """,
    )
    text = _models_text(tmp_path, tmp_path)
    assert "index=True" in text  # from the foreign key
    assert "Index('ix_item_owner_id'" not in text
    assert indexes(str(tmp_path)).build().specs == []


def test_cli_writes_indexes_sql(indexed_folder, tmp_path):
    from fastapifromfrictionless.cli import main

    out = tmp_path / "out"
    main(["generate", str(indexed_folder), "--output", str(out)])
    assert (out / "indexes.sql").exists()
    assert "USING brin" in (out / "indexes.sql").read_text()


def test_cli_omits_indexes_sql_when_nothing_is_declared(unindexed_folder, tmp_path):
    from fastapifromfrictionless.cli import main

    out = tmp_path / "out"
    main(["generate", str(unindexed_folder), "--output", str(out)])
    assert not (out / "indexes.sql").exists()
