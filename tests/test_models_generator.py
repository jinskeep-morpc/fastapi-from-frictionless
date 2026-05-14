"""Unit tests for the models code generator."""

import textwrap

import pytest

from fastapifromfrictionless import models


def write_schema(tmp_path, name, content):
    (tmp_path / f"{name}.schema.yaml").write_text(textwrap.dedent(content))


def folder_str(p):
    """Generators pass folder to logging.getChild, which requires str not PosixPath."""
    return str(p)


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
def id_pk_folder(tmp_path):
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


# ---------------------------------------------------------------------------
# Class name generation
# ---------------------------------------------------------------------------


def test_generates_all_six_model_classes(simple_folder):
    output = "".join(models(folder_str(simple_folder)).build().models)
    assert "class LocationBase(SQLModel)" in output
    assert "class Location(LocationBase" in output
    assert "class LocationCreate(LocationBase)" in output
    assert "class LocationUpdate(LocationBase)" in output
    assert "class LocationPublic(LocationBase)" in output


def test_no_public_with_all_when_no_relationships(simple_folder):
    output = "".join(models(folder_str(simple_folder)).build().models)
    assert "LocationPublicWithAll" not in output


# ---------------------------------------------------------------------------
# Field optionality
# ---------------------------------------------------------------------------


def test_required_field_is_not_optional(simple_folder):
    output = "".join(models(folder_str(simple_folder)).build().models)
    # In the Base class, `address` is required and should appear as `str` (not optional).
    # The Update model intentionally makes all fields optional, so only check the Base block.
    base_block = output.split("class LocationBase")[1].split("class Location(")[0]
    assert "address: str" in base_block
    assert "address: str | None" not in base_block


def test_optional_field_is_none_union(simple_folder):
    output = "".join(models(folder_str(simple_folder)).build().models)
    assert "zipcode: int | None" in output


# ---------------------------------------------------------------------------
# Auto-increment id primary key
# ---------------------------------------------------------------------------


def test_id_pk_excluded_from_base(id_pk_folder):
    output = "".join(models(str(id_pk_folder)).build().models)
    # id should NOT appear in SensorBase
    base_block = output.split("class SensorBase")[1].split("class Sensor(")[0]
    assert "id" not in base_block


def test_id_pk_added_to_table_model(id_pk_folder):
    output = "".join(models(str(id_pk_folder)).build().models)
    assert "id: int | None = Field(default=None, primary_key=True)" in output


def test_id_included_in_public_model(id_pk_folder):
    output = "".join(models(str(id_pk_folder)).build().models)
    public_block = output.split("class SensorPublic")[1].split("class Sensor")[0]
    assert "id: int" in public_block


# ---------------------------------------------------------------------------
# Foreign keys and relationships
# ---------------------------------------------------------------------------


def test_fk_field_has_foreign_key_annotation(fk_folder):
    output = "".join(models(str(fk_folder)).build().models)
    assert "foreign_key='sensor.id'" in output


def test_relationship_added_to_table_model(fk_folder):
    output = "".join(models(str(fk_folder)).build().models)
    assert "Relationship(back_populates=" in output


def test_public_with_all_generated_when_relationships_exist(fk_folder):
    output = "".join(models(str(fk_folder)).build().models)
    assert "SensorPublicWithAll" in output
    assert "DeploymentPublicWithAll" in output


# ---------------------------------------------------------------------------
# Timestamp mixin
# ---------------------------------------------------------------------------


def test_table_model_includes_timestamp_mixin(simple_folder):
    output = "".join(models(folder_str(simple_folder)).build().models)
    assert "TimestampMixin" in output


def test_public_model_includes_timestamps(simple_folder):
    output = "".join(models(folder_str(simple_folder)).build().models)
    assert "created_at: datetime" in output
    assert "updated_at: datetime" in output


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------


def test_save_writes_file(simple_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(simple_folder)).build().save(out)
    assert out.exists()
    content = out.read_text()
    assert "LocationBase" in content
    assert "from sqlmodel import" in content


# ---------------------------------------------------------------------------
# type_map coverage — regression tests for missing / unknown types
# ---------------------------------------------------------------------------


@pytest.fixture()
def any_yearmonth_folder(tmp_path):
    write_schema(
        tmp_path,
        "item",
        """\
        fields:
          - name: id
            type: integer
          - name: payload
            type: any
          - name: period
            type: yearmonth
          - name: link
            type: string
            format: uri
        primaryKey:
          - id
        """,
    )
    return tmp_path


def test_any_type_maps_to_Any(any_yearmonth_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(any_yearmonth_folder)).build().save(out)
    assert "payload: Any" in out.read_text()


def test_yearmonth_type_maps_to_str(any_yearmonth_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(any_yearmonth_folder)).build().save(out)
    assert "period: str" in out.read_text()


def test_string_uri_format_maps_to_AnyUrl(any_yearmonth_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(any_yearmonth_folder)).build().save(out)
    assert "link: AnyUrl" in out.read_text()
