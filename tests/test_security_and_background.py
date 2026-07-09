"""Tests for the security + background-task changes in the app_header template.

Covers issues #110 (fail-closed auth), #115 (tempfile cleanup), and #111
(background-task offloading of excel endpoints).
"""

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


def _saved(simple_folder, tmp_path):
    out = tmp_path / "app.py"
    app(str(simple_folder)).build().save(out)
    return out.read_text()


# ---------------------------------------------------------------------------
# Issue #110 — fail-closed auth via lifespan
# ---------------------------------------------------------------------------


def test_lifespan_context_manager_defined(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "@asynccontextmanager" in content
    assert "async def lifespan(app: FastAPI):" in content


def test_lifespan_imports_present(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "from contextlib import asynccontextmanager" in content
    assert "import logging" in content


def test_lifespan_wired_into_app(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "FastAPI(lifespan=lifespan" in content


def test_lifespan_raises_when_api_key_missing(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "raise RuntimeError" in content
    assert "API_KEY env var is not set" in content


def test_allow_no_auth_env_var_consulted(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "_ALLOW_NO_AUTH" in content
    assert 'os.getenv("ALLOW_NO_AUTH"' in content


def test_allow_no_auth_logs_warning(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "logger.warning" in content
    assert "ALLOW_NO_AUTH=true" in content


def test_deprecated_on_event_startup_removed(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "@app.on_event('startup')" not in content
    assert '@app.on_event("startup")' not in content


def test_create_db_and_tables_called_in_lifespan(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    # create_db_and_tables() should still run — now from inside lifespan
    assert "create_db_and_tables()" in content


# ---------------------------------------------------------------------------
# Issue #115 — temp file handling
# ---------------------------------------------------------------------------


def test_deprecated_mktemp_removed(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "tempfile.mktemp" not in content


def test_export_uses_named_temporary_file(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "tempfile.NamedTemporaryFile(suffix='.xlsx'" in content


def test_export_schedules_temp_file_cleanup(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "background_tasks.add_task(os.unlink" in content


def test_import_does_not_write_to_schema_folder(simple_folder, tmp_path):
    """The upload should land in the system temp dir, not SCHEMA_FOLDER."""
    content = _saved(simple_folder, tmp_path)
    # The NamedTemporaryFile for the upload must not pin dir=SCHEMA_FOLDER
    assert "NamedTemporaryFile(suffix='.xlsx', delete=False, dir=SCHEMA_FOLDER)" not in content


def test_import_cleans_up_excel_in_finally(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "finally:" in content
    assert "os.unlink(excel_path)" in content


def test_import_cleans_up_generated_package_yaml(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert ".package.yaml" in content
    assert "package_yaml.unlink()" in content


# ---------------------------------------------------------------------------
# Issue #111 — background tasks / asyncio.to_thread
# ---------------------------------------------------------------------------


def test_asyncio_imported(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "import asyncio" in content


def test_background_tasks_imported(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "BackgroundTasks" in content


def test_export_handler_is_async(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "async def export_excel" in content


def test_export_offloads_to_thread(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "asyncio.to_thread(" in content
    assert "dump_to_excel" in content


def test_import_handler_is_async(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    assert "async def import_excel" in content


def test_import_offloads_update_api_to_thread(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    # update_api_from_package must run on a worker thread, not the event loop
    assert "asyncio.to_thread(" in content
    assert "update_api_from_package" in content


def test_import_reads_upload_with_await(simple_folder, tmp_path):
    content = _saved(simple_folder, tmp_path)
    # Async handler should `await file.read()` rather than block on file.file.read()
    assert "await file.read()" in content
