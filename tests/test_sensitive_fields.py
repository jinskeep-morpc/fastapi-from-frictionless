"""Fields marked `sensitive: true` are writable but not readable by ordinary callers.

The protection is structural rather than filtered: a sensitive field is kept out of
the base model, so XPublic -- which every ordinary read route returns -- has no such
attribute to leak. It reappears only on XAdmin, behind the /admin routes.
"""

import textwrap

import pytest

from fastapifromfrictionless import app, models


def write_schema(tmp_path, name, content):
    (tmp_path / f"{name}.schema.yaml").write_text(textwrap.dedent(content))


@pytest.fixture()
def pii_folder(tmp_path):
    write_schema(
        tmp_path,
        "party",
        """\
        fields:
          - name: id
            type: integer
            constraints: {required: true}
          - name: full_name
            type: string
            sensitive: true
          - name: email
            type: string
            sensitive: true
          - name: town
            type: string
        primaryKey: [id]
        """,
    )
    return tmp_path


def _models_text(folder, tmp_path):
    out = tmp_path / "models.py"
    models(str(folder)).build().save(out)
    return out.read_text()


def test_sensitive_fields_are_absent_from_the_public_model(pii_folder, tmp_path):
    text = _models_text(pii_folder, tmp_path)
    public = text.split("class PartyPublic(")[1].split("class ")[0]
    assert "full_name" not in public
    assert "email" not in public


def test_sensitive_fields_remain_writable_and_stored(pii_folder, tmp_path):
    text = _models_text(pii_folder, tmp_path)
    table = text.split("class Party(")[1].split("class ")[0]
    create = text.split("class PartyCreate(")[1].split("class ")[0]
    assert "full_name" in table and "email" in table
    assert "full_name" in create and "email" in create


def test_admin_model_restores_them(pii_folder, tmp_path):
    text = _models_text(pii_folder, tmp_path)
    assert "class PartyAdmin(PartyPublic):" in text
    admin = text.split("class PartyAdmin(")[1].split("class ")[0]
    assert "full_name" in admin and "email" in admin


def test_non_sensitive_fields_are_untouched(pii_folder, tmp_path):
    text = _models_text(pii_folder, tmp_path)
    assert "town" in text.split("class PartyBase(")[1].split("class ")[0]


def test_a_populated_record_cannot_leak_through_the_public_model(pii_folder, tmp_path):
    """The decisive check: validate a full row through XPublic and inspect the dump."""
    import importlib.util
    import sys

    out = tmp_path / "models.py"
    models(str(pii_folder)).build().save(out)
    spec = importlib.util.spec_from_file_location("generated_pii_models", out)
    module = importlib.util.module_from_spec(spec)
    sys.modules["generated_pii_models"] = module
    try:
        spec.loader.exec_module(module)
        row = module.Party(id=1, full_name="Jane Doe", email="jane@example.org", town="Columbus")
        dumped = module.PartyPublic.model_validate(row, from_attributes=True).model_dump()
        assert "Jane Doe" not in str(dumped)
        assert "jane@example.org" not in str(dumped)
        assert dumped["town"] == "Columbus"
        admin = module.PartyAdmin.model_validate(row, from_attributes=True).model_dump()
        assert admin["full_name"] == "Jane Doe"
    finally:
        sys.modules.pop("generated_pii_models", None)


def test_admin_routes_are_generated_and_guarded(pii_folder, tmp_path):
    out = tmp_path / "app.py"
    app(str(pii_folder)).build().save(out)
    text = out.read_text()
    assert "@app.get('/admin/party/all'" in text
    assert "response_model=list[PartyAdmin]" in text
    assert "dependencies=[Depends(require_admin)]" in text
    assert "ADMIN_API_KEY" in text and "ADMIN_EMAILS" in text


def test_no_admin_routes_without_sensitive_fields(tmp_path):
    write_schema(
        tmp_path,
        "plain",
        """\
        fields:
          - name: id
            type: integer
            constraints: {required: true}
        primaryKey: [id]
        """,
    )
    out = tmp_path / "app.py"
    app(str(tmp_path)).build().save(out)
    assert "/admin/" not in out.read_text()


def test_admin_defaults_to_nobody(monkeypatch):
    """With neither mechanism configured, no request is an admin."""
    from fastapifromfrictionless.web.auth import is_admin

    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    monkeypatch.delenv("UI_PROXY_IDENTITY_HEADER", raising=False)

    class Req:
        headers: dict = {}
        cookies: dict = {}

    assert is_admin(Req()) is False


def test_identity_allowlist_grants_admin(monkeypatch):
    from fastapifromfrictionless.web.auth import is_admin

    monkeypatch.setenv("UI_PROXY_IDENTITY_HEADER", "Cf-Access-Authenticated-User-Email")
    monkeypatch.setenv("ADMIN_EMAILS", "boss@morpc.org, other@morpc.org")

    class Req:
        cookies: dict = {}

        def __init__(self, who):
            self.headers = {"Cf-Access-Authenticated-User-Email": who}

    assert is_admin(Req("BOSS@morpc.org")) is True
    assert is_admin(Req("stranger@example.com")) is False


def test_ui_descriptor_marks_sensitive_fields(pii_folder, tmp_path):
    """The generated UI descriptor must carry the flag the router filters on.

    router.py derives display_fields as [f for f in fields if not
    f.get("sensitive")]. The flag used to be computed by uigen and then dropped
    by the template, so the filter matched nothing and every sensitive column
    was rendered to anyone who could sign in.
    """
    from fastapifromfrictionless.uigen import ui

    out = tmp_path / "ui.py"
    ui(str(pii_folder)).build().save(out)
    text = out.read_text()

    assert '{"name": "full_name"' in text
    for line in text.splitlines():
        if '"name": "full_name"' in line:
            assert '"sensitive": True' in line, line
        if '"name": "id"' in line:
            assert "sensitive" not in line, line


def test_ui_hides_sensitive_values_from_an_ordinary_viewer(monkeypatch):
    """End to end: the rendered list must not contain a sensitive value."""
    from fastapifromfrictionless.web.router import build_ui_app

    monkeypatch.setenv("API_KEY", "ordinary")
    monkeypatch.setenv("ADMIN_API_KEY", "administrator")
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    monkeypatch.delenv("UI_PROXY_IDENTITY_HEADER", raising=False)

    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Field, Session, SQLModel, create_engine

    class Party(SQLModel, table=True):
        __tablename__ = "party_uitest"
        id: int = Field(primary_key=True)
        full_name: str = ""

    # StaticPool keeps one connection, so the in-memory database survives
    # between the setup session and the request the TestClient makes.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine, tables=[Party.__table__])
    with Session(engine) as s:
        s.add(Party(id=1, full_name="Jane Resident"))
        s.commit()

    def get_session():
        with Session(engine) as session:
            yield session

    resources = {
        "party": {
            "label": "Party",
            "pk": ["id"],
            "table": Party,
            "create": Party,
            "update": Party,
            "fields": [
                {"name": "id", "type": "integer", "required": True, "fk": None},
                {"name": "full_name", "type": "string", "required": False,
                 "fk": None, "sensitive": True},
            ],
        }
    }

    def page(key):
        client = TestClient(build_ui_app(resources, get_session))
        client.post("/login", data={"api_key": key}, follow_redirects=False)
        return client.get("/party", follow_redirects=False).text

    assert "Jane Resident" not in page("ordinary")
    # The admin key is a valid sign-in in its own right, and reveals the column.
    assert "Jane Resident" in page("administrator")
