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


@pytest.fixture()
def id_only_folder(tmp_path):
    write_schema(
        tmp_path,
        "respondent",
        """\
        fields:
          - name: id
            type: integer
            constraints:
              required: true
        primaryKey:
          - id
        """,
    )
    return tmp_path


def test_id_only_schema_generates_valid_python(id_only_folder, tmp_path):
    import ast

    out = tmp_path / "models.py"
    models(folder_str(id_only_folder)).build().save(out)
    ast.parse(out.read_text())  # raises SyntaxError if invalid


def test_id_only_base_has_pass(id_only_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(id_only_folder)).build().save(out)
    content = out.read_text()
    # RespondentBase and RespondentUpdate must both have a body
    assert "class RespondentBase(SQLModel):\n    pass" in content
    assert "class RespondentUpdate(RespondentBase):\n    pass" in content


def test_any_type_maps_to_str(any_yearmonth_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(any_yearmonth_folder)).build().save(out)
    assert "payload: str" in out.read_text()


def test_header_imports_Any(simple_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(simple_folder)).build().save(out)
    assert "from typing import Any" in out.read_text()


def test_yearmonth_type_maps_to_str(any_yearmonth_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(any_yearmonth_folder)).build().save(out)
    assert "period: str" in out.read_text()


def test_string_uri_format_maps_to_AnyUrl(any_yearmonth_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(any_yearmonth_folder)).build().save(out)
    assert "link: AnyUrl" in out.read_text()


# ---------------------------------------------------------------------------
# geoalchemy2 conditional import
# ---------------------------------------------------------------------------


@pytest.fixture()
def geo_folder(tmp_path):
    write_schema(
        tmp_path,
        "site",
        """\
        fields:
          - name: id
            type: integer
          - name: location
            type: geopoint
          - name: footprint
            type: geojson
            constraints:
              required: true
        primaryKey:
          - id
        """,
    )
    return tmp_path


def test_geo_schema_includes_geoalchemy2_import(geo_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(geo_folder)).build().save(out)
    assert "from geoalchemy2.types import Geometry" in out.read_text()


def test_non_geo_schema_omits_geoalchemy2_import(simple_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(simple_folder)).build().save(out)
    assert "geoalchemy2" not in out.read_text()


def test_geo_field_uses_sa_column_not_bare_geometry_annotation(geo_folder, tmp_path):
    # Regression (#132): the geo types were emitted straight into the annotation slot as
    # `location: Geometry('POINT') | None`, which raises TypeError at class creation.
    out = tmp_path / "models.py"
    models(folder_str(geo_folder)).build().save(out)
    text = out.read_text()
    assert "Geometry('POINT') | None" not in text
    assert "location: Any | None = Field(default=None, sa_column=Column(Geometry('POINT')))" in text


def test_required_geo_field_is_non_nullable(geo_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(geo_folder)).build().save(out)
    assert (
        "footprint: Any = Field(sa_column=Column(Geometry('GEOMETRY'), nullable=False))"
        in out.read_text()
    )


def test_geo_schema_imports_Column(geo_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(geo_folder)).build().save(out)
    assert "from sqlalchemy import Column, DateTime" in out.read_text()


def test_non_geo_schema_omits_Column_import(simple_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(simple_folder)).build().save(out)
    assert "from sqlalchemy import DateTime" in out.read_text()
    assert "Column" not in out.read_text()


def test_generated_geo_models_are_importable(geo_folder, tmp_path):
    """The bug in #132 was invisible to text assertions: import the module and check it."""
    import importlib.util
    import sys

    out = tmp_path / "models.py"
    models(folder_str(geo_folder)).build().save(out)

    spec = importlib.util.spec_from_file_location("generated_geo_models", out)
    module = importlib.util.module_from_spec(spec)
    sys.modules["generated_geo_models"] = module
    try:
        spec.loader.exec_module(module)  # raised TypeError before the fix
        assert module.Site.__tablename__ == "site"
    finally:
        sys.modules.pop("generated_geo_models", None)


# ---------------------------------------------------------------------------
# Unique constraints (#135)
# ---------------------------------------------------------------------------


@pytest.fixture()
def unique_folder(tmp_path):
    write_schema(
        tmp_path,
        "sensor",
        """\
        fields:
          - name: macaddr
            type: string
            constraints: {required: true, unique: true}
          - name: name
            type: string
            constraints: {required: true, unique: true}
          - name: label
            type: string
            constraints: {unique: true}
          - name: status
            type: string
        primaryKey:
          - macaddr
    """,
    )
    write_schema(
        tmp_path,
        "deployment",
        """\
        fields:
          - name: id
            type: integer
          - name: sensor_name
            type: string
            constraints: {unique: true}
        primaryKey:
          - id
        foreignKeys:
          - fields: [sensor_name]
            reference: {resource: sensor, fields: [name]}
    """,
    )
    return tmp_path


def test_unique_constraint_on_plain_field(unique_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(unique_folder)).build().save(out)
    assert "name: str = Field(unique=True)" in out.read_text()


def test_unique_constraint_on_optional_field(unique_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(unique_folder)).build().save(out)
    assert "label: str | None = Field(unique=True)" in out.read_text()


def test_unique_merged_into_existing_foreign_key_field(unique_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(unique_folder)).build().save(out)
    assert (
        "sensor_name: str | None = Field(foreign_key='sensor.name', index=True, unique=True)"
        in out.read_text()
    )


def test_primary_key_does_not_get_redundant_unique(unique_folder, tmp_path):
    # A PK is already unique; a second constraint would create a duplicate index.
    out = tmp_path / "models.py"
    models(folder_str(unique_folder)).build().save(out)
    assert "macaddr: str = Field(primary_key = True)" in out.read_text()
    assert "primary_key = True, unique=True" not in out.read_text()


def test_field_without_unique_is_unchanged(unique_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(unique_folder)).build().save(out)
    assert "status: str | None\n" in out.read_text()


def test_unique_geo_field_sets_flag_on_column(tmp_path):
    write_schema(
        tmp_path,
        "site",
        """\
        fields:
          - name: id
            type: integer
          - name: footprint
            type: geopoint
            constraints: {unique: true}
        primaryKey:
          - id
    """,
    )
    out = tmp_path / "models.py"
    models(folder_str(tmp_path)).build().save(out)
    assert (
        "footprint: Any | None = Field(default=None, "
        "sa_column=Column(Geometry('POINT'), unique=True))" in out.read_text()
    )


def test_unique_models_are_importable(unique_folder, tmp_path):
    import importlib.util
    import sys

    out = tmp_path / "models.py"
    models(folder_str(unique_folder)).build().save(out)

    spec = importlib.util.spec_from_file_location("generated_unique_models", out)
    module = importlib.util.module_from_spec(spec)
    sys.modules["generated_unique_models"] = module
    try:
        spec.loader.exec_module(module)
        assert module.Sensor.__table__.columns["name"].unique is True
        assert module.Sensor.__table__.columns["status"].unique in (None, False)
    finally:
        sys.modules.pop("generated_unique_models", None)


# ---------------------------------------------------------------------------
# Relationship cardinality (#138)
# ---------------------------------------------------------------------------


@pytest.fixture()
def cardinality_folder(tmp_path):
    """station <- install: install owns the FK, so it is the many side."""
    write_schema(
        tmp_path,
        "station",
        """\
        fields:
          - name: macaddr
            type: string
            constraints: {required: true}
          - name: name
            type: string
            constraints: {required: true, unique: true}
        primaryKey:
          - macaddr
    """,
    )
    write_schema(
        tmp_path,
        "install",
        """\
        fields:
          - name: name
            type: string
            constraints: {required: true}
          - name: station_name
            type: string
            constraints: {required: true}
        primaryKey:
          - name
        foreignKeys:
          - fields: [station_name]
            reference: {resource: station, fields: [name]}
    """,
    )
    return tmp_path


def test_fk_owning_side_is_scalar(cardinality_folder, tmp_path):
    # Regression (#138): the FK side was emitted as list['Station'], so serializing a
    # populated relationship raised ResponseValidationError.
    out = tmp_path / "models.py"
    models(folder_str(cardinality_folder)).build().save(out)
    text = out.read_text()
    assert "station: Optional['Station'] = Relationship(back_populates='installs')" in text
    assert "stations: list['Station']" not in text


def test_referenced_side_stays_a_list(cardinality_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(cardinality_folder)).build().save(out)
    assert (
        "installs: list['Install'] | None = Relationship(back_populates='station')"
        in out.read_text()
    )


def test_public_with_all_fk_side_is_scalar(cardinality_folder, tmp_path):
    out = tmp_path / "models.py"
    models(folder_str(cardinality_folder)).build().save(out)
    text = out.read_text()
    assert "station: Optional['StationPublic'] = None" in text
    assert "stations: List['StationPublic']" not in text


def test_relationship_cardinality_configures_and_matches(cardinality_folder, tmp_path):
    """back_populates mismatches only surface when SQLAlchemy configures mappers."""
    import importlib.util
    import sys

    from sqlalchemy.orm import configure_mappers

    out = tmp_path / "models.py"
    models(folder_str(cardinality_folder)).build().save(out)

    spec = importlib.util.spec_from_file_location("generated_cardinality_models", out)
    module = importlib.util.module_from_spec(spec)
    sys.modules["generated_cardinality_models"] = module
    try:
        spec.loader.exec_module(module)
        configure_mappers()
        assert module.Install.__mapper__.relationships["station"].uselist is False
        assert module.Station.__mapper__.relationships["installs"].uselist is True
    finally:
        sys.modules.pop("generated_cardinality_models", None)
