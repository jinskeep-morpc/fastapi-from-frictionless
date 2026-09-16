"""Unit tests for the UI generator and the shared web router."""

import textwrap

import pytest
from sqlmodel import Field, SQLModel

from fastapifromfrictionless.uigen import ui


def write_schema(tmp_path, name, content):
    (tmp_path / f"{name}.schema.yaml").write_text(textwrap.dedent(content))


def folder_str(p):
    return str(p)


@pytest.fixture()
def ui_folder(tmp_path):
    write_schema(
        tmp_path,
        "widget",
        """\
        fields:
          - name: code
            type: string
            constraints: {required: true}
          - name: label
            type: string
          - name: active
            type: boolean
        primaryKey:
          - code
    """,
    )
    write_schema(
        tmp_path,
        "gadget",
        """\
        fields:
          - name: id
            type: integer
            constraints: {required: true}
          - name: widget_code
            type: string
        primaryKey:
          - id
        foreignKeys:
          - fields: [widget_code]
            reference: {resource: widget, fields: [code]}
    """,
    )
    return tmp_path


def test_descriptor_covers_every_resource(ui_folder):
    gen = ui(folder_str(ui_folder)).build()
    assert {r["slug"] for r in gen.resources} == {"widget", "gadget"}


def test_skip_omits_a_resource(ui_folder):
    # A table too large to browse must be excludable; see #145.
    gen = ui(folder_str(ui_folder), skip=["gadget"]).build()
    assert {r["slug"] for r in gen.resources} == {"widget"}


def test_field_metadata_carries_type_required_and_fk(ui_folder):
    gen = ui(folder_str(ui_folder)).build()
    widget = next(r for r in gen.resources if r["slug"] == "widget")
    by_name = {f["name"]: f for f in widget["fields"]}
    assert by_name["code"]["required"] is True
    assert by_name["label"]["required"] is False
    assert by_name["active"]["type"] == "boolean"

    gadget = next(r for r in gen.resources if r["slug"] == "gadget")
    fk = next(f for f in gadget["fields"] if f["name"] == "widget_code")
    assert fk["fk"] == "widget.code"


def test_primary_key_recorded(ui_folder):
    gen = ui(folder_str(ui_folder)).build()
    assert next(r for r in gen.resources if r["slug"] == "widget")["pk"] == ["code"]


def test_generated_ui_is_valid_python(ui_folder, tmp_path):
    import ast

    out = tmp_path / "ui.py"
    ui(folder_str(ui_folder)).build().save(out)
    ast.parse(out.read_text())  # syntax only; imports need a live project


def test_generated_ui_builds_a_sub_app_not_a_router(ui_folder, tmp_path):
    """A router would inherit the API's global verify_api_key dependency, which
    would make the UI's own sign-in page return 403. See #145."""
    out = tmp_path / "ui.py"
    ui(folder_str(ui_folder)).build().save(out)
    text = out.read_text()
    assert "build_ui_app" in text
    assert "build_ui_router" not in text


def test_app_generator_mounts_ui_only_when_asked(ui_folder, tmp_path):
    from fastapifromfrictionless import app

    without = tmp_path / "app_plain.py"
    app(folder_str(ui_folder)).build().save(without)
    assert "ui_app" not in without.read_text()

    with_ui = tmp_path / "app_ui.py"
    app(folder_str(ui_folder), with_ui=True).build().save(with_ui)
    text = with_ui.read_text()
    assert 'app.mount("/ui", ui_app)' in text


# ---------------------------------------------------------------------------
# Shared web layer
# ---------------------------------------------------------------------------


def test_templates_all_parse():
    """Templates ship in the package; a syntax error would only surface in a
    running deployment otherwise."""
    from pathlib import Path

    import jinja2

    import fastapifromfrictionless.web as web

    d = Path(web.__file__).parent / "templates"
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(d)))
    names = sorted(p.name for p in d.glob("*.html"))
    assert names, "no templates found - package data may be missing"
    for name in names:
        env.get_template(name)


@pytest.mark.parametrize(
    "raw,ftype,required,expected",
    [
        ("", "string", False, None),
        ("", "integer", False, None),
        ("7", "integer", False, 7),
        ("1.5", "number", False, 1.5),
        ("on", "boolean", False, True),
        ("", "boolean", False, False),
        ("hello", "string", True, "hello"),
    ],
)
def test_form_value_coercion(raw, ftype, required, expected):
    """Browsers submit everything as text; blanks must become NULL, not ""."""
    from fastapifromfrictionless.web.router import _coerce

    assert _coerce(raw, {"type": ftype, "required": required}) == expected


def test_identify_rejects_a_wrong_key(monkeypatch):
    from fastapifromfrictionless.web import auth

    monkeypatch.setenv("API_KEY", "correct-key")
    monkeypatch.delenv("UI_PROXY_IDENTITY_HEADER", raising=False)

    class Req:
        cookies = {auth.COOKIE_NAME: "wrong-key"}
        headers: dict = {}

    assert auth.identify(Req()) is None


def test_identify_accepts_the_cookie(monkeypatch):
    from fastapifromfrictionless.web import auth

    monkeypatch.setenv("API_KEY", "correct-key")
    monkeypatch.delenv("UI_PROXY_IDENTITY_HEADER", raising=False)

    class Req:
        cookies = {auth.COOKIE_NAME: "correct-key"}
        headers: dict = {}

    assert auth.identify(Req()) == "signed in"


def test_proxy_header_supplies_identity(monkeypatch):
    from fastapifromfrictionless.web import auth

    monkeypatch.setenv("API_KEY", "correct-key")
    monkeypatch.setenv("UI_PROXY_IDENTITY_HEADER", "Cf-Access-Authenticated-User-Email")

    class Req:
        cookies: dict = {}
        headers = {"Cf-Access-Authenticated-User-Email": "someone@example.org"}

    assert auth.identify(Req()) == "someone@example.org"


def test_missing_proxy_header_falls_back_to_cookie(monkeypatch):
    """A misconfigured proxy should not lock everyone out."""
    from fastapifromfrictionless.web import auth

    monkeypatch.setenv("API_KEY", "correct-key")
    monkeypatch.setenv("UI_PROXY_IDENTITY_HEADER", "Cf-Access-Authenticated-User-Email")

    class Req:
        cookies = {auth.COOKIE_NAME: "correct-key"}
        headers: dict = {}

    assert auth.identify(Req()) == "signed in"


# ---------------------------------------------------------------------------
# List filtering and ordering (#151)
# ---------------------------------------------------------------------------


# Declared at module scope, not inside the fixture: SQLModel's registry is
# global, so a class defined per-test is re-registered on every run and
# eventually raises InvalidRequestError. The table name is distinctive to avoid
# colliding with the generated modules other tests exec.
class UiThing(SQLModel, table=True):
    __tablename__ = "ui_thing"
    code: str = Field(primary_key=True)
    label: str
    rank: int


class UiThingCreate(SQLModel):
    code: str
    label: str
    rank: int


class UiThingUpdate(SQLModel):
    code: str | None = None
    label: str | None = None
    rank: int | None = None


UI_RESOURCES = {
    "thing": {
        "label": "Thing",
        "pk": ["code"],
        "table": UiThing,
        "create": UiThingCreate,
        "update": UiThingUpdate,
        "fields": [
            {"name": "code", "type": "string", "required": True, "fk": None},
            {"name": "label", "type": "string", "required": True, "fk": None},
            {"name": "rank", "type": "integer", "required": True, "fk": None},
        ],
    }
}


@pytest.fixture()
def live_ui(monkeypatch):
    """A running UI over an in-memory SQLite database with a few rows."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, create_engine

    from fastapifromfrictionless.web import build_ui_app

    monkeypatch.setenv("ALLOW_NO_AUTH", "true")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("UI_PROXY_IDENTITY_HEADER", raising=False)

    # StaticPool: an in-memory SQLite database is per-connection, so without it
    # the app's sessions would each open an empty one and see no tables.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    UiThing.__table__.create(engine)
    with Session(engine) as s:
        for code, label, rank in [
            ("alpha", "First thing", 3),
            ("beta", "Second thing", 1),
            ("gamma", "Third thing", 2),
        ]:
            s.add(UiThing(code=code, label=label, rank=rank))
        s.commit()

    def get_session():
        with Session(engine) as session:
            yield session

    parent = FastAPI()
    parent.mount("/ui", build_ui_app(UI_RESOURCES, get_session))
    yield TestClient(parent)
    engine.dispose()


def _codes(html):
    """Order-preserving list of the codes appearing in table cells."""
    import re

    return re.findall(r"<td[^>]*>(alpha|beta|gamma)</td>", html)


def test_list_unfiltered_shows_everything(live_ui):
    body = live_ui.get("/ui/thing").text
    assert set(_codes(body)) == {"alpha", "beta", "gamma"}


def test_filter_narrows_rows(live_ui):
    assert _codes(live_ui.get("/ui/thing?q=alph").text) == ["alpha"]


def test_filter_matches_non_text_columns(live_ui):
    """Columns are cast to text so a search hits numbers and dates too."""
    assert _codes(live_ui.get("/ui/thing?q=2").text) == ["gamma"]


def test_sort_ascending_and_descending(live_ui):
    assert _codes(live_ui.get("/ui/thing?sort=rank&dir=asc").text) == ["beta", "gamma", "alpha"]
    assert _codes(live_ui.get("/ui/thing?sort=rank&dir=desc").text) == ["alpha", "gamma", "beta"]


def test_filter_and_sort_compose(live_ui):
    body = live_ui.get("/ui/thing?q=thing&sort=rank&dir=desc").text
    assert _codes(body) == ["alpha", "gamma", "beta"]


def test_unknown_sort_column_is_ignored(live_ui):
    """A sort column is interpolated into the query, so it must be validated
    against the resource's own fields rather than trusted."""
    for attempt in ("nonexistent", "rank; DROP TABLE thing", "__class__"):
        response = live_ui.get("/ui/thing", params={"sort": attempt})
        assert response.status_code == 200
        assert set(_codes(response.text)) == {"alpha", "beta", "gamma"}


def test_htmx_request_returns_the_table_only(live_ui):
    full = live_ui.get("/ui/thing").text
    partial = live_ui.get("/ui/thing", headers={"HX-Request": "true"}).text
    assert "<html" in full
    assert "<html" not in partial
    assert 'id="table-wrap"' in partial


def test_page_is_clamped_when_a_filter_shrinks_the_result(live_ui):
    """Filtering from a high page must not land on an empty page."""
    assert _codes(live_ui.get("/ui/thing?page=99&q=alpha").text) == ["alpha"]


def test_no_match_says_so(live_ui):
    body = live_ui.get("/ui/thing?q=zzzznothing").text
    assert _codes(body) == []
    assert "No records match" in body
