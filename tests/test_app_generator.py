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


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def test_get_all_has_offset_param(simple_folder):
    out = _output(simple_folder)
    assert "offset: int = 0" in out


def test_get_all_has_limit_param(simple_folder):
    out = _output(simple_folder)
    assert "limit: int = Query" in out


def test_get_all_uses_offset_limit_in_query(simple_folder):
    out = _output(simple_folder)
    assert ".offset(offset).limit(limit)" in out


# ---------------------------------------------------------------------------
# Default query routes
# ---------------------------------------------------------------------------


def test_recent_route_generated(simple_folder):
    out = _output(simple_folder)
    assert "@app.get('/location/recent'" in out


def test_recent_route_orders_by_created_at(simple_folder):
    out = _output(simple_folder)
    assert "order_by(Location.created_at.desc())" in out


def test_recent_route_has_limit_param(simple_folder):
    out = _output(simple_folder)
    assert "recent_locations" in out


# ---------------------------------------------------------------------------
# Excel file endpoints
# ---------------------------------------------------------------------------


def test_excel_export_endpoint_in_saved_file(simple_folder, tmp_path):
    out = tmp_path / "app.py"
    app(str(simple_folder)).build().save(out)
    content = out.read_text()
    assert "@app.get('/excel/export'" in content
    assert "dump_to_excel" in content


def test_excel_import_endpoint_in_saved_file(simple_folder, tmp_path):
    out = tmp_path / "app.py"
    app(str(simple_folder)).build().save(out)
    content = out.read_text()
    assert "@app.post('/excel/import')" in content
    assert "UploadFile" in content
    assert "update_api_from_package" in content


def test_schema_folder_and_api_url_config_in_saved_file(simple_folder, tmp_path):
    out = tmp_path / "app.py"
    app(str(simple_folder)).build().save(out)
    content = out.read_text()
    assert "SCHEMA_FOLDER" in content
    assert "API_URL" in content


# ---------------------------------------------------------------------------
# API key authentication
# ---------------------------------------------------------------------------


def test_api_key_env_var_in_saved_file(simple_folder, tmp_path):
    out = tmp_path / "app.py"
    app(str(simple_folder)).build().save(out)
    content = out.read_text()
    assert "API_KEY" in content
    assert "verify_api_key" in content


def test_api_key_header_in_saved_file(simple_folder, tmp_path):
    out = tmp_path / "app.py"
    app(str(simple_folder)).build().save(out)
    content = out.read_text()
    assert "APIKeyHeader" in content
    assert "X-API-Key" in content


# ---------------------------------------------------------------------------
# CORS and security headers
# ---------------------------------------------------------------------------


def test_cors_middleware_in_saved_file(simple_folder, tmp_path):
    out = tmp_path / "app.py"
    app(str(simple_folder)).build().save(out)
    content = out.read_text()
    assert "CORSMiddleware" in content
    assert "ALLOWED_ORIGINS" in content


def test_security_headers_middleware_in_saved_file(simple_folder, tmp_path):
    out = tmp_path / "app.py"
    app(str(simple_folder)).build().save(out)
    content = out.read_text()
    assert "SecurityHeadersMiddleware" in content
    assert "X-Content-Type-Options" in content
    assert "X-Frame-Options" in content


# ---------------------------------------------------------------------------
# HTTP error response handlers
# ---------------------------------------------------------------------------


def test_http_exception_handler_in_saved_file(simple_folder, tmp_path):
    out = tmp_path / "app.py"
    app(str(simple_folder)).build().save(out)
    content = out.read_text()
    assert "exception_handler(HTTPException)" in content
    assert "JSONResponse" in content


def test_validation_exception_handler_in_saved_file(simple_folder, tmp_path):
    out = tmp_path / "app.py"
    app(str(simple_folder)).build().save(out)
    content = out.read_text()
    assert "exception_handler(RequestValidationError)" in content
    assert "exc.errors()" in content
