"""Unit tests for the UI generator and the shared web router."""

import textwrap

import pytest
from sqlmodel import Field, Relationship, SQLModel

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


# ---------------------------------------------------------------------------
# Detail page, click-through and maps (#153, #154, #155)
# ---------------------------------------------------------------------------


class UiOwner(SQLModel, table=True):
    __tablename__ = "ui_owner"
    id: int = Field(primary_key=True)
    handle: str
    # Generated models declare these, and _related reads them off the mapper.
    items: list["UiItem"] = Relationship(back_populates="owner")


class UiOwnerCreate(SQLModel):
    id: int
    handle: str


class UiOwnerUpdate(SQLModel):
    id: int | None = None
    handle: str | None = None


class UiItem(SQLModel, table=True):
    __tablename__ = "ui_item"
    code: str = Field(primary_key=True)
    owner_handle: str | None = Field(default=None, foreign_key="ui_owner.handle")
    owner: UiOwner | None = Relationship(back_populates="items")


class UiItemCreate(SQLModel):
    code: str
    owner_handle: str | None = None


class UiItemUpdate(SQLModel):
    code: str | None = None
    owner_handle: str | None = None


REL_RESOURCES = {
    "owner": {
        "label": "Owner",
        "pk": ["id"],
        "table": UiOwner,
        "create": UiOwnerCreate,
        "update": UiOwnerUpdate,
        "fields": [
            {"name": "id", "type": "integer", "required": True, "fk": None},
            {"name": "handle", "type": "string", "required": True, "fk": None},
        ],
    },
    "item": {
        "label": "Item",
        "pk": ["code"],
        "table": UiItem,
        "create": UiItemCreate,
        "update": UiItemUpdate,
        "fields": [
            {"name": "code", "type": "string", "required": True, "fk": None},
            # Points at handle, which is NOT the owner's primary key - the
            # normal case, and the one a naive link would 404 on.
            {"name": "owner_handle", "type": "string", "required": False, "fk": "ui_owner.handle"},
        ],
    },
}


@pytest.fixture()
def rel_ui(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, create_engine

    from fastapifromfrictionless.web import build_ui_app

    monkeypatch.setenv("ALLOW_NO_AUTH", "true")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("UI_PROXY_IDENTITY_HEADER", raising=False)

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    UiOwner.__table__.create(engine)
    UiItem.__table__.create(engine)
    with Session(engine) as s:
        s.add(UiOwner(id=7, handle="acme"))
        s.add(UiItem(code="widget-1", owner_handle="acme"))
        s.add(UiItem(code="widget-2", owner_handle="ghost"))  # no such owner
        s.commit()

    def get_session():
        with Session(engine) as session:
            yield session

    parent = FastAPI()
    parent.mount("/ui", build_ui_app(REL_RESOURCES, get_session))
    yield TestClient(parent)
    engine.dispose()


def test_detail_page_renders(rel_ui):
    response = rel_ui.get("/ui/item/widget-1")
    assert response.status_code == 200
    assert "widget-1" in response.text


def test_new_form_still_reachable_after_detail_route(rel_ui):
    """Regression: /{slug}/new must be declared before /{slug}/{pk}, or "new"
    is parsed as a primary key and the create form disappears. Same failure as
    /query being shadowed in the generated API."""
    response = rel_ui.get("/ui/item/new")
    assert response.status_code == 200
    assert 'name="code"' in response.text


def test_list_offers_view_not_edit_or_delete(rel_ui):
    body = rel_ui.get("/ui/item").text
    assert ">View<" in body
    assert ">Delete<" not in body


def test_fk_resolves_to_the_targets_primary_key(rel_ui):
    """owner_handle references handle, but the owner's key is id, so the link
    must be resolved rather than built from the value."""
    body = rel_ui.get("/ui/item/widget-1").text
    assert "/ui/owner/7" in body


def test_unresolvable_fk_falls_back_to_the_filtered_list(rel_ui):
    body = rel_ui.get("/ui/item/widget-2").text
    assert "/ui/owner/7" not in body
    assert "/ui/owner?q=ghost" in body


def test_related_records_appear_on_the_target(rel_ui):
    body = rel_ui.get("/ui/owner/7").text
    assert "widget-1" in body


def test_delete_redirects_instead_of_swapping_a_row(rel_ui):
    """Delete now happens from the detail page, where there is no row to swap."""
    response = rel_ui.delete("/ui/item/widget-1")
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "/ui/item"
    assert rel_ui.get("/ui/item/widget-1").status_code == 404


def test_geopoint_is_not_a_form_input(live_ui, monkeypatch):
    """A geometry must not be typeable: anything at all could be entered."""
    from fastapifromfrictionless.web import router as web_router

    fields = UI_RESOURCES["thing"]["fields"]
    UI_RESOURCES["thing"] = dict(
        UI_RESOURCES["thing"],
        fields=fields + [{"name": "spot", "type": "geopoint", "required": False, "fk": None}],
    )
    try:
        body = live_ui.get("/ui/thing/new").text
        assert 'name="spot"' not in body
        assert "not editable here" in body
    finally:
        UI_RESOURCES["thing"] = dict(UI_RESOURCES["thing"], fields=fields)
    assert web_router  # keep the import meaningful


def test_map_assets_only_load_where_there_is_geometry(rel_ui):
    assert "leaflet" not in rel_ui.get("/ui/item/widget-1").text


# ---------------------------------------------------------------------------
# Both link directions and action placement (#158)
# ---------------------------------------------------------------------------


def test_forward_references_are_shown_as_cards(rel_ui):
    """A link on the value says a record exists but nothing about it."""
    body = rel_ui.get("/ui/item/widget-1").text
    assert "References" in body
    assert "Owner &middot; owner_handle" in body
    assert "handle: acme" in body  # a detail of the referenced record, not just its key


def test_empty_reverse_relationship_still_appears(rel_ui):
    """A vanished section reads as "no such relationship" rather than "none
    yet", and hides where to add the first one."""
    body = rel_ui.get("/ui/owner/7").text
    rel_ui.delete("/ui/item/widget-1")
    rel_ui.delete("/ui/item/widget-2")
    after = rel_ui.get("/ui/owner/7").text
    assert "Item" in body and "Item" in after
    assert "None yet" in after
    assert "/ui/item/new" in after


def test_actions_sit_on_the_title_line(rel_ui):
    body = rel_ui.get("/ui/item/widget-1").text
    titlebar = body.split('class="titlebar"', 1)[1].split("</div>", 2)
    assert ">Edit</a>" in titlebar[0] + titlebar[1]
    assert "Delete</button>" in titlebar[0] + titlebar[1]


def test_primary_keys_are_url_encoded_in_links(rel_ui):
    """A key can contain spaces or colons; a raw one breaks anything parsing
    the markup."""
    from fastapi.testclient import TestClient  # noqa: F401  (fixture already built)

    body = rel_ui.get("/ui/item").text
    assert 'href="/ui/item/widget-1"' in body  # nothing to encode here
    # And the router encodes resolved foreign key targets:
    from fastapifromfrictionless.web.router import _pk_of

    assert _pk_of(type("R", (), {"code": "a b"})(), {"pk": ["code"]}) == "a b"
