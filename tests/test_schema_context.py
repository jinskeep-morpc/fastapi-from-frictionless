"""Unit tests for SchemaContext."""

import textwrap

import pytest

from fastapifromfrictionless.schema_context import SchemaContext


def write_schema(tmp_path, name, content):
    (tmp_path / f"{name}.schema.yaml").write_text(textwrap.dedent(content))


@pytest.fixture()
def simple_folder(tmp_path):
    write_schema(
        tmp_path,
        "location",
        """\
        fields:
          - name: address
            type: string
            constraints:
              required: true
          - name: zipcode
            type: integer
        primaryKey:
          - address
        """,
    )
    return tmp_path


@pytest.fixture()
def hyphen_folder(tmp_path):
    write_schema(
        tmp_path,
        "weather-station",
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
    return tmp_path


@pytest.fixture()
def fk_folder(tmp_path):
    write_schema(
        tmp_path,
        "sensor",
        """\
        fields:
          - name: id
            type: integer
          - name: name
            type: string
            constraints:
              required: true
        primaryKey:
          - id
        """,
    )
    write_schema(
        tmp_path,
        "deployment",
        """\
        fields:
          - name: id
            type: integer
          - name: sensor_id
            type: integer
            constraints:
              required: true
        primaryKey:
          - id
        foreignKeys:
          - fields: [sensor_id]
            reference:
              resource: sensor
              fields: [id]
        """,
    )
    return tmp_path


@pytest.fixture()
def link_table_folder(tmp_path):
    write_schema(
        tmp_path,
        "sensor",
        """\
        fields:
          - name: id
            type: integer
          - name: name
            type: string
        primaryKey:
          - id
        """,
    )
    write_schema(
        tmp_path,
        "tag",
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
    write_schema(
        tmp_path,
        "link-sensor-tag",
        """\
        fields:
          - name: sensor_id
            type: integer
          - name: tag_id
            type: integer
        primaryKey:
          - sensor_id
          - tag_id
        foreignKeys:
          - fields: [sensor_id]
            reference:
              resource: sensor
              fields: [id]
          - fields: [tag_id]
            reference:
              resource: tag
              fields: [id]
        """,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# name_of
# ---------------------------------------------------------------------------


def test_name_of_simple(simple_folder):
    ctx = SchemaContext(str(simple_folder))
    assert ctx.name_of("location.schema.yaml") == "Location"


def test_name_of_hyphenated(hyphen_folder):
    ctx = SchemaContext(str(hyphen_folder))
    assert ctx.name_of("weather-station.schema.yaml") == "WeatherStation"


# ---------------------------------------------------------------------------
# foreign_keys_of
# ---------------------------------------------------------------------------


def test_foreign_keys_of_empty(simple_folder):
    ctx = SchemaContext(str(simple_folder))
    assert ctx.foreign_keys_of("location.schema.yaml") == []


def test_foreign_keys_of_present(fk_folder):
    ctx = SchemaContext(str(fk_folder))
    assert ctx.foreign_keys_of("deployment.schema.yaml") == ["sensor_id"]
    assert ctx.foreign_keys_of("sensor.schema.yaml") == []


# ---------------------------------------------------------------------------
# relationships_of
# ---------------------------------------------------------------------------


def test_relationships_of_referenced(fk_folder):
    ctx = SchemaContext(str(fk_folder))
    assert ctx.relationships_of("sensor.schema.yaml") == ["Deployment"]


def test_relationships_of_not_referenced(fk_folder):
    ctx = SchemaContext(str(fk_folder))
    assert ctx.relationships_of("deployment.schema.yaml") == []


def test_relationships_of_isolated_schema(simple_folder):
    ctx = SchemaContext(str(simple_folder))
    assert ctx.relationships_of("location.schema.yaml") == []


# ---------------------------------------------------------------------------
# is_link_table
# ---------------------------------------------------------------------------


def test_is_link_table_true(link_table_folder):
    ctx = SchemaContext(str(link_table_folder))
    assert ctx.is_link_table("link-sensor-tag.schema.yaml") is True


def test_is_link_table_false_no_fks(simple_folder):
    ctx = SchemaContext(str(simple_folder))
    assert ctx.is_link_table("location.schema.yaml") is False


def test_is_link_table_false_single_fk(fk_folder):
    ctx = SchemaContext(str(fk_folder))
    assert ctx.is_link_table("deployment.schema.yaml") is False


# ---------------------------------------------------------------------------
# primary_key_of
# ---------------------------------------------------------------------------


def test_primary_key_of_simple(simple_folder):
    ctx = SchemaContext(str(simple_folder))
    assert ctx.primary_key_of("location.schema.yaml") == "address"


def test_primary_key_of_id(fk_folder):
    ctx = SchemaContext(str(fk_folder))
    assert ctx.primary_key_of("sensor.schema.yaml") == "id"


# ---------------------------------------------------------------------------
# Single-load guarantee
# ---------------------------------------------------------------------------


def test_schema_of_returns_cached_instance(simple_folder):
    ctx = SchemaContext(str(simple_folder))
    first = ctx.schema_of("location.schema.yaml")
    second = ctx.schema_of("location.schema.yaml")
    assert first is second


def test_filenames_sorted(fk_folder):
    ctx = SchemaContext(str(fk_folder))
    assert ctx.filenames == sorted(ctx.filenames)
    assert "sensor.schema.yaml" in ctx.filenames
    assert "deployment.schema.yaml" in ctx.filenames
