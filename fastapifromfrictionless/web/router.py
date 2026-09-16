"""Routes for the generated CRUD UI."""

import os
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import String, cast, or_
from sqlmodel import Session, func, select

from .auth import COOKIE_NAME, auth_disabled, expected_key, identify, proxy_identity_header

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

PAGE_SIZE = 50


def _coerce(raw: str, field: dict):
    """Turn a form string into something the model will accept.

    Browsers submit everything as text, and an empty box means "not provided"
    rather than empty string for anything that is not a string column.
    """
    # Booleans first: a blank checkbox means False, not "not provided".
    if field["type"] == "boolean":
        return raw in ("on", "true", "True", "1")
    if raw == "" and not field["required"]:
        return None
    if field["type"] == "integer":
        return int(raw) if raw != "" else None
    if field["type"] == "number":
        return float(raw) if raw != "" else None
    return raw


def _form_values(form, fields) -> dict:
    values = {}
    for f in fields:
        if f["type"] == "boolean":
            # An unchecked checkbox submits nothing at all.
            values[f["name"]] = f["name"] in form
        elif f["name"] in form:
            values[f["name"]] = _coerce(form[f["name"]], f)
    return values


def build_ui_app(resources: dict, get_session, prefix: str = "/ui") -> FastAPI:
    """Build the UI as a sub-application from a generator-emitted descriptor.

    A mounted sub-application rather than a router on purpose: the generated API
    applies verify_api_key as a global dependency, which a router would inherit,
    and that would make the sign-in page itself return 403 - unreachable by any
    browser. A sub-app does not inherit the parent's dependencies, so the UI can
    run its own cookie-based check.

    ``resources`` maps a slug to a dict with: label, pk (list of column names),
    table (SQLModel class), create/update (pydantic models) and fields (list of
    {name, type, required, fk}).
    """
    router = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    # A resource's slug and its table name differ (slug "sensor-note" is table
    # "sensornote"), and foreign keys name the table. Map one to the other once.
    slug_of_table = {r["table"].__tablename__: slug for slug, r in resources.items()}

    def ctx(request: Request, **extra):
        base = {
            "request": request,
            "resources": resources,
            "prefix": prefix,
            "user": identify(request),
            "proxy_auth": bool(proxy_identity_header()),
            "map_tile_url": os.getenv(
                "UI_MAP_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            ),
            "map_attribution": os.getenv("UI_MAP_ATTRIBUTION", "&copy; OpenStreetMap contributors"),
        }
        base.update(extra)
        return base

    def guard(request: Request):
        if identify(request) is None:
            raise HTTPException(status_code=307, headers={"Location": f"{prefix}/login"})

    def _resource(slug: str):
        if slug not in resources:
            raise HTTPException(status_code=404, detail=f"No such resource: {slug}")
        return resources[slug]

    def _pk_filter(statement, res, pk_value: str):
        """Match a record by primary key, handling composite keys as pk1~pk2."""
        parts = pk_value.split("~")
        if len(parts) != len(res["pk"]):
            raise HTTPException(status_code=400, detail="primary key mismatch")
        for col, raw in zip(res["pk"], parts):
            field = next(f for f in res["fields"] if f["name"] == col)
            statement = statement.where(getattr(res["table"], col) == _coerce(raw, field))
        return statement

    # ---------------------------------------------------------------- auth

    @router.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        if identify(request) is not None:
            return RedirectResponse(prefix, status_code=303)
        return TEMPLATES.TemplateResponse(request, "login.html", ctx(request, error=None))

    @router.post("/login", response_class=HTMLResponse)
    def login(request: Request, api_key: str = Form("")):
        import hmac

        if expected_key() and hmac.compare_digest(api_key, expected_key()):
            response = RedirectResponse(prefix, status_code=303)
            response.set_cookie(
                COOKIE_NAME,
                api_key,
                httponly=True,
                samesite="lax",
                secure=request.url.scheme == "https",
            )
            return response
        return TEMPLATES.TemplateResponse(
            request, "login.html", ctx(request, error="That key was not accepted."), status_code=401
        )

    @router.post("/logout")
    def logout(request: Request):
        response = RedirectResponse(f"{prefix}/login", status_code=303)
        response.delete_cookie(COOKIE_NAME)
        return response

    # ---------------------------------------------------------------- views

    @router.get("/", response_class=HTMLResponse)
    def index(request: Request, session: Session = Depends(get_session)):
        guard(request)
        counts = {}
        for slug, res in resources.items():
            counts[slug] = session.exec(select(func.count()).select_from(res["table"])).one()
        return TEMPLATES.TemplateResponse(request, "index.html", ctx(request, counts=counts))

    @router.get("/{slug}", response_class=HTMLResponse)
    def list_rows(
        request: Request,
        slug: str,
        page: int = 1,
        q: str = "",
        sort: str = "",
        dir: str = "asc",
        session: Session = Depends(get_session),
    ):
        guard(request)
        res = _resource(slug)
        page = max(page, 1)
        q = q.strip()

        statement = select(res["table"])
        count_statement = select(func.count()).select_from(res["table"])
        if q:
            clause = _search_clause(res, q)
            statement = statement.where(clause)
            count_statement = count_statement.where(clause)

        # Only a column this resource actually declares may be sorted on;
        # anything else is ignored rather than interpolated into the query.
        names = {f["name"] for f in res["fields"]}
        sort = sort if sort in names else ""
        descending = dir == "desc"
        if sort:
            column = getattr(res["table"], sort)
            statement = statement.order_by(column.desc() if descending else column.asc())

        total = session.exec(count_statement).one()
        pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        page = min(page, pages)
        rows = session.exec(statement.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)).all()

        context = ctx(
            request,
            slug=slug,
            res=res,
            rows=rows,
            total=total,
            page=page,
            pages=pages,
            q=q,
            sort=sort,
            dir="desc" if descending else "asc",
            links=_fk_links(rows, res, resources, slug_of_table, session),
            pk_of=_pk_of,
        )
        # htmx asks for the table alone so typing narrows the list in place.
        template = "_table.html" if request.headers.get("HX-Request") else "list.html"
        return TEMPLATES.TemplateResponse(request, template, context)

    @router.get("/{slug}/new", response_class=HTMLResponse)
    def new_form(request: Request, slug: str, session: Session = Depends(get_session)):
        guard(request)
        res = _resource(slug)
        return TEMPLATES.TemplateResponse(
            request,
            "form.html",
            ctx(
                request,
                slug=slug,
                res=res,
                row=None,
                errors=None,
                options=_fk_options(res, resources, session),
            ),
        )

    @router.post("/{slug}/new", response_class=HTMLResponse)
    async def create(request: Request, slug: str, session: Session = Depends(get_session)):
        guard(request)
        res = _resource(slug)
        values = _form_values(await request.form(), res["fields"])
        # Geo fields are not rendered as inputs, so nothing arrives for them.
        # The generated Create models make every field required-but-nullable,
        # so they have to be supplied rather than left out.
        for field in res["fields"]:
            if field["type"] in ("geopoint", "geojson"):
                values.setdefault(field["name"], None)
        try:
            record = res["table"].model_validate(res["create"](**values))
            session.add(record)
            session.commit()
        except Exception as exc:
            session.rollback()
            return TEMPLATES.TemplateResponse(
                request,
                "form.html",
                ctx(
                    request,
                    slug=slug,
                    res=res,
                    row=values,
                    errors=str(exc),
                    options=_fk_options(res, resources, session),
                ),
                status_code=400,
            )
        return RedirectResponse(f"{prefix}/{slug}", status_code=303)

    @router.get("/{slug}/{pk}", response_class=HTMLResponse)
    def detail(request: Request, slug: str, pk: str, session: Session = Depends(get_session)):
        guard(request)
        res = _resource(slug)
        row = session.exec(_pk_filter(select(res["table"]), res, pk)).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Record not found")
        return TEMPLATES.TemplateResponse(
            request,
            "detail.html",
            ctx(
                request,
                slug=slug,
                res=res,
                row=row,
                pk=pk,
                links=_fk_links([row], res, resources, slug_of_table, session),
                related=_related(row, res, resources, slug_of_table, session),
                geo=_geo_points(row, res, session),
                pk_of=_pk_of,
            ),
        )

    @router.get("/{slug}/{pk}/edit", response_class=HTMLResponse)
    def edit_form(request: Request, slug: str, pk: str, session: Session = Depends(get_session)):
        guard(request)
        res = _resource(slug)
        row = session.exec(_pk_filter(select(res["table"]), res, pk)).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Record not found")
        return TEMPLATES.TemplateResponse(
            request,
            "form.html",
            ctx(
                request,
                slug=slug,
                res=res,
                row=row,
                pk=pk,
                errors=None,
                options=_fk_options(res, resources, session),
            ),
        )

    @router.post("/{slug}/{pk}/edit", response_class=HTMLResponse)
    async def update(request: Request, slug: str, pk: str, session: Session = Depends(get_session)):
        guard(request)
        res = _resource(slug)
        row = session.exec(_pk_filter(select(res["table"]), res, pk)).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Record not found")
        values = _form_values(await request.form(), res["fields"])
        # Take primary keys from the URL, not the form. A readonly input is
        # submitted but a disabled <select> is not, so a primary key that is
        # also a foreign key would otherwise arrive missing - and the generated
        # Update models make every field required-but-nullable, so an omitted
        # key fails validation rather than being ignored.
        for col, raw in zip(res["pk"], pk.split("~")):
            field = next(f for f in res["fields"] if f["name"] == col)
            values[col] = _coerce(raw, field)
        # Carry geometry forward untouched: it is not on the form, and any
        # trigger deriving it from other columns will refresh it on write.
        for field in res["fields"]:
            if field["type"] in ("geopoint", "geojson"):
                values[field["name"]] = getattr(row, field["name"])
        try:
            row.sqlmodel_update(res["update"](**values).model_dump(exclude_unset=True))
            session.add(row)
            session.commit()
        except Exception as exc:
            session.rollback()
            return TEMPLATES.TemplateResponse(
                request,
                "form.html",
                ctx(
                    request,
                    slug=slug,
                    res=res,
                    row=values,
                    pk=pk,
                    errors=str(exc),
                    options=_fk_options(res, resources, session),
                ),
                status_code=400,
            )
        return RedirectResponse(f"{prefix}/{slug}", status_code=303)

    @router.delete("/{slug}/{pk}", response_class=HTMLResponse)
    def delete(request: Request, slug: str, pk: str, session: Session = Depends(get_session)):
        guard(request)
        res = _resource(slug)
        row = session.exec(_pk_filter(select(res["table"]), res, pk)).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Record not found")
        try:
            session.delete(row)
            session.commit()
        except Exception as exc:
            session.rollback()
            # Usually a foreign key still pointing here; say so in the row.
            return HTMLResponse(
                f'<p class="err">Could not delete: {exc}</p>',
                status_code=409,
            )
        # Delete is initiated from the detail page, so send the browser to the
        # list rather than swapping an element the page no longer has.
        return HTMLResponse("", status_code=200, headers={"HX-Redirect": f"{prefix}/{slug}"})

    return router


def _pk_of(row, res: dict) -> str:
    """Composite keys are joined with ~ so they survive a single path segment."""
    return "~".join(str(getattr(row, c)) for c in res["pk"])


def _fk_links(rows, res: dict, resources: dict, slug_of_table: dict, session: Session) -> dict:
    """Map (row primary key, field name) -> URL for every resolvable foreign key.

    Foreign keys usually do not point at the target's primary key -
    deployment.sensor_name references sensor.name while sensor's key is macaddr -
    so a link cannot be built from the value alone. Values are resolved in one
    query per target table rather than one per cell, and anything that does not
    resolve falls back to the filtered list, which always works.
    """
    links: dict = {}
    if not rows:
        return links

    fk_fields = [f for f in res["fields"] if f.get("fk")]
    for field in fk_fields:
        table_name, column = field["fk"].split(".")
        target_slug = slug_of_table.get(table_name)
        if target_slug is None:
            continue  # excluded by --skip-ui; render as plain text
        target = resources[target_slug]

        values = {getattr(row, field["name"]) for row in rows}
        values.discard(None)
        if not values:
            continue

        target_column = getattr(target["table"], column)
        pk_columns = [getattr(target["table"], c) for c in target["pk"]]
        found = session.exec(
            select(target_column, *pk_columns).where(target_column.in_(values))
        ).all()
        # Each result is (value, *primary key parts). These are SQLAlchemy Row
        # objects, not tuples, so convert before slicing.
        resolved = {}
        for result in found:
            parts = tuple(result)
            resolved[parts[0]] = "~".join(str(part) for part in parts[1:])

        for row in rows:
            value = getattr(row, field["name"])
            if value is None:
                continue
            key = (_pk_of(row, res), field["name"])
            if value in resolved:
                links[key] = f"{target_slug}/{resolved[value]}"
            else:
                links[key] = f"{target_slug}?q={value}"
    return links


def _related(row, res: dict, resources: dict, slug_of_table: dict, session: Session) -> list:
    """Records pointing at this one, read from the mapper's relationships.

    SQLModel already declares these on the table classes, so nothing extra has
    to be generated. Only the list side is shown - the scalar side is the
    foreign key, which the field list already displays as a link.
    """
    CAP = 10
    out = []
    for name, relationship in res["table"].__mapper__.relationships.items():
        if not relationship.uselist:
            continue
        target_table = relationship.mapper.class_.__tablename__
        target_slug = slug_of_table.get(target_table)
        if target_slug is None:
            continue
        items = list(getattr(row, name) or [])
        out.append(
            {
                "name": name,
                "slug": target_slug,
                "label": resources[target_slug]["label"],
                "res": resources[target_slug],
                "rows": items[:CAP],
                "total": len(items),
                "more": max(len(items) - CAP, 0),
            }
        )
    return out


def _geo_points(row, res: dict, session: Session) -> dict:
    """Longitude/latitude for each geopoint field, for the map.

    Reading coordinates out of a geometry is PostGIS-specific. SQLite cannot
    hold a geometry at all, so anywhere the functions are missing this returns
    nothing and the template falls back to the raw value.
    """
    from sqlalchemy import func as sa_func

    points: dict = {}
    geo_fields = [f for f in res["fields"] if f["type"] in ("geopoint", "geojson")]
    if not geo_fields:
        return points
    for field in geo_fields:
        column = getattr(res["table"], field["name"])
        statement = select(sa_func.ST_X(column), sa_func.ST_Y(column))
        for key in res["pk"]:
            statement = statement.where(getattr(res["table"], key) == getattr(row, key))
        try:
            result = session.exec(statement).first()
        except Exception:  # noqa: BLE001 - any dialect without the function
            continue
        if result and result[0] is not None and result[1] is not None:
            points[field["name"]] = {"lon": float(result[0]), "lat": float(result[1])}
    return points


def _search_clause(res: dict, q: str):
    """Case-insensitive match of ``q`` against every column, as text.

    Columns are cast so a search hits numbers and dates too. ``ilike`` is native
    on PostgreSQL and compiles to ``lower(x) LIKE lower(y)`` on SQLite, so this
    behaves the same on both.
    """
    pattern = f"%{q}%"
    return or_(
        *[cast(getattr(res["table"], f["name"]), String).ilike(pattern) for f in res["fields"]]
    )


def _fk_options(res: dict, resources: dict, session: Session) -> dict:
    """Existing values for each foreign key field, so forms offer a select.

    Capped: a select of 30M options helps nobody, and the field falls back to a
    free-text box when there are more than the cap.
    """
    CAP = 500
    options: dict = {}
    for field in res["fields"]:
        target = field.get("fk")
        if not target:
            continue
        table_name, column = target.split(".")
        target_res = next(
            (r for r in resources.values() if r["table"].__tablename__ == table_name), None
        )
        if target_res is None:
            continue
        col = getattr(target_res["table"], column)
        values = session.exec(select(col).distinct().limit(CAP + 1)).all()
        if len(values) <= CAP:
            options[field["name"]] = sorted(v for v in values if v is not None)
    return options
