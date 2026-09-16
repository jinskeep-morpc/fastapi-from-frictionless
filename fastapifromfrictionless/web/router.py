"""Routes for the generated CRUD UI."""

from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
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

    def ctx(request: Request, **extra):
        base = {
            "request": request,
            "resources": resources,
            "prefix": prefix,
            "user": identify(request),
            "proxy_auth": bool(proxy_identity_header()),
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

    def _pk_of(row, res) -> str:
        return "~".join(str(getattr(row, c)) for c in res["pk"])

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
        request: Request, slug: str, page: int = 1, session: Session = Depends(get_session)
    ):
        guard(request)
        res = _resource(slug)
        page = max(page, 1)
        total = session.exec(select(func.count()).select_from(res["table"])).one()
        rows = session.exec(
            select(res["table"]).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
        ).all()
        return TEMPLATES.TemplateResponse(
            request,
            "list.html",
            ctx(
                request,
                slug=slug,
                res=res,
                rows=rows,
                total=total,
                page=page,
                pages=max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1),
                pk_of=_pk_of,
            ),
        )

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
                f'<tr><td colspan="99" class="err">Could not delete: {exc}</td></tr>',
                status_code=409,
            )
        return HTMLResponse("")  # htmx swaps the row away

    return router


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
