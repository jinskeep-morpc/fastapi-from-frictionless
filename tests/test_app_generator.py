"""Unit tests for the app (FastAPI endpoint) code generator."""

import textwrap

import pytest

from fastapifromfrictionless import app


def write_schema(tmp_path, name, content):
    (tmp_path / f"{name}.schema.yaml").write_text(textwrap.dedent(content))


@pytest.fixture()
def simple_folder(tmp_path):
    write_schema(
        tmp_path,
        "location",
        """\
        fields:
          - name: id
            type: integer
          - name: address
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


def _output(folder):
    a = app(str(folder)).build()
    return "".join(a.endpoints)


# ---------------------------------------------------------------------------
# CRUD routes present
# ---------------------------------------------------------------------------


def test_post_route_generated(simple_folder):
    out = _output(simple_folder)
    assert "@app.post('/location'" in out


def test_get_all_route_generated(simple_folder):
    out = _output(simple_folder)
    assert "@app.get('/location/all'" in out


def test_get_single_route_generated(simple_folder):
    out = _output(simple_folder)
    assert "@app.get('/location/{location_id}'" in out


def test_patch_route_generated(simple_folder):
    out = _output(simple_folder)
    assert "@app.patch('/location/{location_id}'" in out


def test_delete_route_generated(simple_folder):
    out = _output(simple_folder)
    assert "@app.delete('/location/{location_id}'" in out


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


def test_create_uses_public_response_model(simple_folder):
    out = _output(simple_folder)
    assert "response_model=LocationPublic" in out


def test_get_all_uses_list_response_model(simple_folder):
    out = _output(simple_folder)
    assert "response_model=list[LocationPublic]" in out


# ---------------------------------------------------------------------------
# Query route only when FK present
# ---------------------------------------------------------------------------


def test_no_query_route_without_fk(simple_folder):
    out = _output(simple_folder)
    assert "query_location" not in out


def test_query_route_generated_with_fk(fk_folder):
    out = _output(fk_folder)
    assert "query_deployment" in out


# ---------------------------------------------------------------------------
# Multiple schemas
# ---------------------------------------------------------------------------


def test_all_schemas_get_endpoints(fk_folder):
    out = _output(fk_folder)
    assert "/sensor" in out
    assert "/deployment" in out


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------


def test_save_writes_file(simple_folder, tmp_path):
    out = tmp_path / "app.py"
    app(str(simple_folder)).build().save(out)
    assert out.exists()
    content = out.read_text()
    assert "FastAPI" in content
    assert "create_location" in content
