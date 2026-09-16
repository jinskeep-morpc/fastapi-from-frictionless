# 2026-09-16 — references show every field

The forward reference cards showed three fields, which meant opening the referenced record
anyway for anything else — the summary saved a click only when you happened to want one of the
three. They now render as a full section, every field as a definition list, with a link through.

That immediately exposed a leak: a referenced location rendered its geometry as raw WKB hex,
`0101000020e610...`, because the coordinate parsing only ran for the record's own fields. Forward
references now get the same treatment and show coordinates. Worth remembering that any value
rendered in a new place needs the same formatting the original place gave it — the binary was
invisible while only three fields showed.

# 2026-09-16 — breadcrumbs and preserved list state (#163)

Only the detail page had any back-navigation, a lone `← Resource` link. The edit and create
forms had none at all, so the only way out was the browser button.

Breadcrumbs now come from the URL on every page. Hierarchy rather than a trail, deliberately:
the browser's back button already covers how you got somewhere, while a trail needs session
state or `?from=` chains that grow unbounded, break on a shared link and loop when a sensor
links to a deployment that links back. URL-derived crumbs stay correct however the page was
reached.

The one piece of state worth keeping is the list you left. Opening a record used to discard the
filter and sort, so after the filtering work every View cost you your place. The View link now
carries the list's query string and the resource crumb returns to exactly that page. One level
deep, survives sharing, and an unfiltered list adds no parameter at all rather than a trailing
`?from=`.

Small thing worth noting about the tests: asserting on rendered breadcrumbs needed a helper that
pulls the labels out of the nav, because asserting on raw HTML would have broken on every markup
tweak. Cheap to write, and it makes the tests read as what a user sees rather than what the
template emits.

# 2026-09-16 — next value for auto-assigned keys (#160)

The create form rendered an empty `id` box for auto-incrementing keys. Whatever was typed was
discarded, because the generator omits such a key from the Create model — the form asked a
question and threw the answer away, while giving no hint what the record would be called.

The signal is the Create model itself: a primary key absent from `model_fields` is one only the
database may set. Those render read-only, pre-filled with `max(id) + 1`, labelled as assigned on
save. A prediction rather than a reservation, which is exactly why it is not editable.

The more serious thing this uncovered is downstream. Bulk loading explicit ids never advances
the sequence backing them, so `nextval` still returned 1 against a table whose max was 72 —
creating a contact failed with a duplicate key through both the UI and the API, and would have
kept failing for 72 attempts. Nothing surfaces this until someone tries to add a record, which
in a migration project is long after the load looked successful. `load_metadata.py` now resyncs
every identity sequence past the loaded data.

Worth generalising: any loader that writes explicit primary keys into a sequence-backed column
leaves this trap behind.

# 2026-09-16 — both link directions on detail pages (#158)

Detail pages treated the two directions inconsistently. Reverse relationships got a section, but
only when non-empty, so a deployment with no notes showed nothing and there was no way to tell
the relationship existed. Forward references were only a hyperlink on the field value, which
tells you a sensor exists but nothing about it.

Now: a card per foreign key summarising the referenced record, and a reverse section that stays
visible when empty with a link to add the first one. Edit and Delete moved onto the title line,
right aligned, where they are visible without scrolling past a long field list.

Also encoded primary keys in links. A location key is a street address, so hrefs carried raw
spaces — browsers cope, but nothing else parsing the markup does, and it made every automated
check of those links fail in a way that looked like a routing bug. `~` stays unreserved, so
composite keys survive encoding.

Worth noting the near-miss: the reference cards looked empty when I first checked them, and I
almost went debugging the template. The fields were rendering — a `sed` range in my own check
had truncated the output. The lesson is the same one as the `isinstance` guard earlier: verify
what the tool is actually showing before believing a negative result.

# 2026-09-16 — detail pages, click-through and maps (#153, #154, #155)

A list row now opens a read-only detail page rather than an edit form. Edit and delete moved
there, foreign keys link through to the record they reference, and a geopoint renders as a map.

Related records needed no generator change: SQLModel already declares the relationships on the
table classes, so the router reads `__mapper__.relationships` at runtime.

Three things went wrong in ways worth keeping:

**`_pk_of` was defined inside `build_ui_app`.** The new module-level helpers called it and the
whole list view 500'd with `NameError`. Every test passed, because the fixture had no foreign
keys and the code path never ran — the bug was only reachable with an FK, which the tests did
not have until I added a second fixture that models one.

**SQLAlchemy returns `Row`, not `tuple`.** An `isinstance(r, tuple)` guard I added defensively
was always False, so every foreign key silently fell back to the filtered list instead of
resolving. It looked like a working feature: links rendered, pages loaded, and only the target
was subtly wrong. A defensive check on an unverified assumption is worse than no check.

**Readonly inputs are submitted.** Rendering geometry readonly meant the browser posted its WKB
hex straight back, and omitting it failed validation because generated Update models make every
field required-but-nullable. Geo fields are now absent from forms entirely and supplied by the
router — None on create, the stored value on update — leaving whatever derives them
authoritative.

Tiles default to public OpenStreetMap with `UI_MAP_TILE_URL` to override. Leaflet loads only on
pages that actually have a point.

# 2026-09-16 — filtering and ordering in UI lists (#151)

List views showed rows in whatever order the database returned, 50 at a time, with no search.
Now: a case-insensitive search box matching every column cast to text, sortable headers, and
both surviving pagination. HTMX swaps the table alone, which meant splitting it into
`_table.html` and picking the template by the `HX-Request` header.

The sort column is interpolated into the query, so it is checked against the resource's declared
fields and ignored otherwise. Tested with `rank; DROP TABLE thing` and `__class__` alongside a
plain unknown name.

Page clamping matters more than it looks: filtering while on page 5 would otherwise land on an
empty page, which reads as "no results" for a filter that matched three rows.

Two test-harness traps cost more time than the feature:

`create_engine("sqlite://")` gives each connection its own empty database, so the fixture's rows
were invisible to the app's sessions — `StaticPool` is required to share one.

Defining the SQLModel table inside the fixture re-registers the class on every test, and
SQLModel's registry is global: the file passed alone and the full suite raised
`InvalidRequestError`. The table class now lives at module scope with a distinctive name, since
other tests exec generated modules that define their own. Same global-registry problem as the
table-name collision in the #138 tests; worth assuming any new exec- or model-based test will hit
it.

# 2026-09-16 — container build could not produce the UI (#148)

The UI shipped in 0.5.0 was unreachable through the one path most people deploy with: the
Dockerfile called `cli generate` with no `--with-ui`, so an image built from the published
package contained no `ui.py`. The only way to run it in a container was to mount locally
generated files over the image, which defeats a build that generates from schemas.

Added `WITH_UI` and `SKIP_UI` build args, plumbed through compose, and passed
`UI_PROXY_IDENTITY_HEADER` into the api service so the proxy-identity option is configurable on
a deployed stack rather than only in a local process.

The catch worth remembering is that generation happens in stage 1 of the build, so these are
build-time, not runtime: setting `WITH_UI` and restarting does nothing, it needs
`docker compose build api`. Same shape as a schema change, and now stated next to that note in
the README.

Verified both directions, since an opt-in that is not actually opt-in is its own bug: with
`WITH_UI=true` the image contains `ui.py`, serves `/ui` with no mounts, honours
`SKIP_UI=reading`, and leaves the API's 403 intact; with it unset the image is byte-for-byte the
old shape - no `ui.py`, no mount in `app.py`.

# 2026-09-16 — generated HTMX CRUD UI (#145)

Generated apps were JSON-only, so editing a record meant curl, Swagger, or an Excel round trip.
`--with-ui` now emits `ui.py` alongside the API: index, paginated list, create/edit/delete
forms, with foreign keys rendered as a select of existing values.

The generated file is deliberately thin — a resource descriptor plus a call to
`build_ui_app`. Views and templates live in `fastapifromfrictionless/web/`, so a template bug is
fixed by upgrading the package rather than regenerating every downstream project. The Excel
endpoints already imported package helpers at runtime, so this follows existing precedent.

Three things only surfaced by running it against a real database:

**A router cannot work.** The generated app sets `dependencies=[Depends(verify_api_key)]` on
`FastAPI(...)`, and an included router inherits it — so the UI's own sign-in page returned 403
and no browser could ever authenticate. It has to be a mounted sub-application, which does not
inherit parent dependencies. Everything returned 403 until that changed.

**Starlette's TemplateResponse signature moved.** `TemplateResponse(name, context)` is now
`(request, name, context)`, and the old form fails deep inside Jinja's cache with
`TypeError: unhashable type: 'dict'` — the context dict lands where the template name belongs.
Nothing about the message points at the call site.

**Disabled controls are not submitted.** A readonly text input is, so editing worked for
ordinary primary keys; a primary key that is also a foreign key renders as a disabled select and
would have arrived missing. Since the generated Update models make every field
required-but-nullable, an omitted key fails validation rather than being ignored. Primary keys
now come from the URL, which is where they are authoritative anyway.

Auth is a shared key in an HttpOnly cookie, so the UI is never unauthenticated by default, with
`UI_PROXY_IDENTITY_HEADER` to trust an identity-aware proxy instead. A missing proxy header
falls back to the cookie rather than locking everyone out of a misconfigured deployment. No
per-user accounts or audit trail; that needs real identity, and the `author` columns on note
tables will keep being filled in by hand until then.

# 2026-09-16 — compose bound everything to 0.0.0.0 (#142)

`podman/compose.yaml` published ports as bare `HOST:CONTAINER`, which Docker and Podman read as
`0.0.0.0:HOST`. On a laptop that is untidy; on a VPS it puts PostgreSQL and a pgAdmin console on
the public internet behind nothing but the `.env` passwords.

Now `${BIND_ADDRESS:-127.0.0.1}:...`, so the safe configuration is what you get by doing
nothing and exposure is an explicit, greppable opt-in.

Verifying this needed care. The first runtime check looked like it proved the fix wrong —
`ss` showed `0.0.0.0:5432`. The test stack had actually failed to start on a subnet collision
with another running project, so what I measured was a different container from an earlier test
still holding the port. Re-run on its own subnet and port it binds `127.0.0.1:5439`, loopback
connects, and the external interface refuses. `docker compose config` alone would not have
caught that either, since it only renders intent.

Worth remembering: Docker's port rules bypass host firewall policy, so an operator who closed
5432 in ufw would have seen a closed port and still been exposed. That is the part that makes
the insecure default genuinely dangerous rather than merely untidy.

Breaking for anyone relying on the old behaviour to reach a stack from another machine;
`BIND_ADDRESS=0.0.0.0` restores it.

# 2026-09-16 — relationship cardinality (#138)

Every relationship was emitted as a list on both sides. The side that *owns* the foreign key is
many-to-one, so SQLAlchemy handed back a single object where the response model declared a list.
Pydantic then iterated it, and iterating a SQLModel instance yields `(key, value)` tuples, so
`/deployment/all` died with `ResponseValidationError: ... Input should be a valid dictionary`,
listing inputs like `('created_at', datetime(...))`.

The fix is in the template, not the generator logic: `fk_models` (this schema owns the FK) now
emits `Optional['X']` with a singular attribute name, while `relationships` (other schemas point
here) keeps the list. The `back_populates` on the list side loses its trailing `s` to name the
new scalar attribute.

Two things worth remembering. First, it hid because an empty relationship serializes fine as an
empty list — a smoke test against a fresh database passes, and it only breaks once a related row
exists. Second, the whole suite stayed green when I made the change, because nothing asserted
cardinality at all; the tests covered names and presence, never shape.

The new mapper test calls `configure_mappers()`, which is the only thing that validates
`back_populates` pairs — a mismatched pair is silent until SQLAlchemy configures. It needed
distinct table names (`station`/`install`) because SQLModel's metadata registry is global and the
other exec-based tests already claim `sensor`/`deployment`; a repeat collides with
"Table is already defined".

Breaking change: response field names on the many-to-one side lose their plural (`sensors` ->
`sensor`).

# 2026-09-16 — unique constraint support (#135)

`constraints.unique` was read by nobody: the field loop looked at `required` and the primary
key, never `unique`, so the constraint silently vanished. Same failure shape as the geo bug in
[#132] — a schema says something and the generator quietly drops it.

It surfaced deploying morpc-purpleair-model to the PostGIS stack. Postgres requires a FK target
to carry a unique or PK constraint, and four FKs there point at non-PK columns (`sensor.name`
three times, `deployment.index` once), so `create_db_and_tables()` died with
`InvalidForeignKey: there is no unique constraint matching given keys`. SQLite never complains
about this, which is why the schemas looked fine locally — worth remembering that the SQLite
default hides a whole class of schema error that only a real deployment catches.

Implementation is a single `unique` flag computed before the geo branch, then merged three ways:
folded into `Column(...)` for geo fields, appended to an existing `Field(...)` for FK fields,
and given a fresh `Field(unique=True)` otherwise. Primary keys are excluded — already unique,
and a second constraint just creates a duplicate index.

Tested each of those paths plus one that execs the generated module and inspects
`__table__.columns[...].unique`, since string assertions alone were exactly what let #132 through.

# 2026-09-15 — geo fields generated non-importable models (#132)

`type_map` mapped `geopoint`/`geojson` to the expression `Geometry('POINT')`, which landed in
the annotation slot and got ` | None` appended for optional fields. `location: Geometry('POINT') | None`
raises `TypeError` at class creation, so a single geo field made the whole generated `models.py`
unimportable — not just that model.

Fixed by splitting the geo types into `geo_type_map` and emitting `Any` plus an `sa_column`:
`Field(default=None, sa_column=Column(Geometry('POINT')))`, or `nullable=False` when required.
The header template now imports `Column` when a geo field is present.

The reason this survived: the only geopoint test asserted that the `geoalchemy2` import line
appeared in the output *text*. Text assertions cannot see invalid Python. Added a test that
execs the generated module, plus assertions for both the optional and required forms.

Caveat worth knowing: even with valid annotations, geo columns cannot be created on plain
SQLite — geoalchemy2 emits `RecoverGeometryColumn`, a SpatiaLite function, and
`create_db_and_tables()` fails. The generated `database.py` defaults to SQLite, so any schema
with a geo field needs PostGIS (as in the podman stack) or SpatiaLite loaded. Not addressed
here; flagged in the PR.

## v0.2.19 — Dependency audit: remove redundant/misclassified packages (2026-06-05)

- Remove `sqlalchemy` from core (redundant — SQLModel already requires it)
- Remove `geoalchemy2` from core → add to new `[app]` optional extra (never imported by the package itself; requires GDAL on Windows which blocked clean install)
- Remove `fastapi_querybuilder` from core → add to `[app]` extra (never imported by the package itself, only emitted into generated app.py)
- Remove duplicate `frictionless` from `[generate]` and `[dev]` extras (already in core as `frictionless[excel]`)
- `podman/Dockerfile` Stage 2 now installs `fastapifromfrictionless[app]` instead of listing packages individually
- Pin `engine="xlsxwriter"` on both `pd.ExcelWriter` calls in `runtime/excel.py` to prevent silent openpyxl fallback and `AttributeError` on `.autofit()`
- Add Windows installation section to README with GDAL guidance and link

## v0.2.18 — Fix NameError in generated app (2026-06-03)

Remove `background_tasks: BackgroundTasks = None` from `import_excel` signature — `BackgroundTasks` was dropped from imports in v0.2.17 but left in the function signature, causing `NameError` at startup in all generated apps. Also removes dead imports `from sqlalchemy import text` and `from sqlalchemy.ext.asyncio import AsyncSession` from the generated `app.py`.

## v0.2.17 — Deployment simplification + Windows support (2026-06-03)

- Removed `setup.sh`, `teardown.sh`, `nginx`, and pre-built GHCR base images from the Podman deployment
- Replaced loopback-IP hostname routing with port-based access (`API_PORT`, `PGADMIN_PORT`, `DB_PORT`)
- Self-contained `Dockerfile` (two stages from `python:3.12-slim`; no external base image dependency)
- Removed `:Z` SELinux volume flags for Docker Desktop / Windows compatibility
- Fixed export endpoint temp-file pattern to avoid Windows `PermissionError` on `os.unlink`
- Bumped `requires-python` to `>=3.11` to align with `contextlib.chdir` usage

## #127 — Remove pre-built base images, self-contained Dockerfile (2026-06-03)

Deleted `Dockerfile.generator-base`, `Dockerfile.runtime-base`, and `.github/workflows/build-images.yml`. Rewrote `podman/Dockerfile` as a self-contained two-stage build starting from `python:3.12-slim` — no more `FROM ghcr.io/...` references. Stage 1 installs `fastapifromfrictionless[generate]` and runs the code-gen CLI; Stage 2 installs runtime deps only. Optional `PACKAGE_VERSION` build arg pins a PyPI release; defaults to latest. pip install precedes COPY schemas/ for optimal layer caching. Updated `podman/README.md`, `dev/podman-deployment.md`, `dev/architecture.md`, and root `README.md`.

## #125 — Simplify deployment: port-based access, Windows support (2026-06-03)

Removed `setup.sh`, `teardown.sh`, `nginx.conf.template`, and `entrypoint.sh`. Replaced NGINX_IP loopback routing and nginx reverse proxy with direct host port bindings (`API_PORT`, `PGADMIN_PORT`, `DB_PORT`) that work on Linux, macOS, and Windows. Removed `:Z` SELinux volume flags from `compose.yaml` (errors on Docker Desktop). Bumped `requires-python` to `>=3.11` to align with `contextlib.chdir` usage. Fixed the Excel export endpoint to read the temp file into memory before `os.unlink` — avoids Windows `PermissionError` when `FileResponse` holds an open handle. Updated `podman/README.md`, `dev/podman-deployment.md`, and root `README.md`.

## #114 — Split load.py into runtime/ and scaffolding.py

Broke the god module `load.py` (360 lines, six unrelated responsibilities) into focused modules:
- `scaffolding.py` — `build_database()` façade over the three generators
- `runtime/excel.py` — `empty_excel`, `create_package`, `dump_to_excel`
- `runtime/http.py` — `requests_post`, `requests_bulk_post`, `requests_get_all`, `requests_update`
- `runtime/sync.py` — `update_api_from_package`, `get_model` (now accepts `models_module` arg to avoid `sys.path` assumption)
- `runtime/__init__.py` — re-exports everything for clean `from fastapifromfrictionless.runtime import ...`
- `load.py` replaced with a backward-compat shim re-exporting from the new locations
All imports moved to module top level. Generated `app.py` template updated to import from `fastapifromfrictionless.runtime` instead of `fastapifromfrictionless.load`. Test patch targets updated to `fastapifromfrictionless.runtime.excel.requests_get_all`.

---

## #113 — Extract SchemaContext and shared Jinja2 env

Extracted `SchemaContext` (loads each `*.schema.yaml` once, exposes `name_of`, `foreign_keys_of`, `relationships_of`, `is_link_table`, `primary_key_of`) and moved the Jinja2 environment into `_templates.py`. All three generators (`models`, `app`, `database`) now import `_env` from `_templates.py`; `models` and `app` accept a `SchemaContext` or a folder path and no longer re-parse schemas on each iteration. Eliminates O(N²) disk reads and three verbatim copies of the Jinja2 `Environment` constructor. 14 new unit tests added in `tests/test_schema_context.py`.

---

## feat(#119): nginx reverse proxy with per-deployment loopback IP routing

Added nginx reverse proxy to the podman deployment stack so multiple deployments can run simultaneously without port conflicts. Each deployment is assigned a unique loopback IP (`NGINX_IP`, e.g. `127.0.1.1`) that nginx and postgres both bind to on the host. The nginx config is generated at container start via `envsubst` from `nginx.conf.template`, substituting only `$PROJECT_NAME` so nginx variables like `$host` are preserved. `setup.sh` adds two `/etc/hosts` entries (`{NGINX_IP} {PROJECT_NAME}.api` and `{NGINX_IP} {PROJECT_NAME}.pgadmin`) with one `sudo` prompt, then builds and starts the stack. `teardown.sh` reverses this. Host port mappings for `api` (8000) and `pgadmin` (8080) were removed — all HTTP access now goes through nginx on port 80.

---

## fix/security-and-background-tasks-110-111-115

Three template-level fixes to the generated FastAPI app, all in `app_header.py.jinja2`:

- #110: fail-closed API key auth. Replaced the deprecated `@app.on_event('startup')` handler with an `@asynccontextmanager` `lifespan` wired into `FastAPI(lifespan=lifespan, ...)`. The lifespan raises `RuntimeError` at startup when `API_KEY` is unset; set `ALLOW_NO_AUTH=true` to explicitly run without auth (logs a warning). Prevents new deployments from silently coming up wide open.
- #115: safer temp file handling for `/excel/export` and `/excel/import`. Replaced `tempfile.mktemp()` (TOCTOU race, never deleted) with `NamedTemporaryFile(delete=False)` plus a `background_tasks.add_task(os.unlink, tmp_path)` cleanup. The import handler no longer writes uploads into `SCHEMA_FOLDER`; it uses the system temp dir and cleans up both the upload and the generated `.package.yaml` in a `finally` block.
- #111: `/excel/export` and `/excel/import` are now `async def` and offload the blocking `dump_to_excel`, `create_package`, and `update_api_from_package` calls via `asyncio.to_thread(...)` so the event loop is not stalled during long Excel I/O.

Added `tests/test_security_and_background.py` (21 tests) that assert the generated app contains the new lifespan/imports/async patterns and does not contain the deprecated `on_event('startup')`, `tempfile.mktemp`, or `dir=SCHEMA_FOLDER` patterns.

## feat/bulk-post-112

Added a bulk POST endpoint to eliminate N round-trips on Excel ingest (#112).

- `fastapifromfrictionless/templates/endpoint_block.py.jinja2` — new `POST /{name}s/bulk` route accepting `list[{Name}Create]`, returning `list[{Name}Public]`. Uses `session.add_all(...)`, a single `session.commit()`, then refresh each row.
- `fastapifromfrictionless/load.py` — added `requests_bulk_post(...)` helper that POSTs a JSON list to `/{endpoint}s/bulk` with optional `X-API-Key` header. Updated `update_api_from_package` to queue new rows per sheet into `new_payloads` and dispatch them in one bulk POST after the row loop. Changed rows still PATCH individually (no bulk update).
- `tests/test_bulk_endpoint.py` — 11 new tests: template rendering checks, helper behavior with mocked session, API key header, trailing slash handling, and error propagation. Suite: 101 tests, all green.

Why bulk POST only: there is no `model_validate` semantics for bulk update, and PATCH semantics differ per row (`exclude_unset=True`); a bulk-update path would need its own design.

## fix/quick-wins-105-109

Fixed 5 code-review quick wins in parallel via feature-team:
- #105: change detection loop in update_api_from_package — now uses a single any() over row.items() so any field difference triggers an update (previous loop reset changed=False each iteration and only reflected the last field).
- #106: generated FK SQLModel Fields now include index=True for query performance on JOINs and FK filters.
- #107: API key check now uses secrets.compare_digest(api_key or "", _API_KEY) and the template imports secrets — eliminates timing side channel.
- #108: requests_post/requests_get_all/requests_update build URLs with f-strings ({server_url.rstrip('/')}/{endpoint}/...) instead of os.path.join, which corrupted https:// schemes on POSIX.
- #109: requests_get_all initializes r = None before the try and guards r.close() with if r is not None — prevents UnboundLocalError when the session.get(...) itself raises.

## 2026-05-14 — Fix create_package absolute path rejected as unsafe by frictionless (#103)

frictionless rejects absolute paths during package.validate(). Changed create_package to chdir to the Excel file's directory and reference it by relative basename. Schema files and output YAML accessed via absolute paths resolved from the schema folder.
## 2026-05-14 — Fix create_package FK error during standalone resource.infer() (#101)

frictionless raises 'package is required for foreign keys' when infer() is called on a standalone TableResource with FK constraints. Strip foreignKeys from schema descriptor before infer; FK validation still happens at package level when validate=True.
## 2026-05-14 — Fix frictionless[excel] missing openpyxl for Excel import (#99)

frictionless base install does not include openpyxl (needed to read .xlsx files). Changed from frictionless to frictionless[excel] in pyproject.toml and Dockerfile.runtime-base.
## 2026-05-14 — Fix frictionless missing from runtime dependencies (#97)

The Excel export/import endpoints use frictionless to read schema files for column headers and data loading. frictionless was only in the [generate] optional extra but is also needed at runtime. Added to pyproject.toml base deps and Dockerfile.runtime-base.
## 2026-05-14 — Fix generator imports crashing runtime via __init__.py (#95)

Generator classes (app, database, model, validate) all require jinja2/frictionless from the [generate] extra. But __init__.py imported them unconditionally, so import fastapifromfrictionless failed in runtime environments. Wrapped generator imports in try/except ImportError so the base package is importable without the extra. 90 tests passing.
## 2026-05-14 — Fix python-multipart missing from runtime dependencies (#93)

The Excel import endpoint uses FastAPI UploadFile which requires python-multipart at import time. Without it the app crashed at startup with RuntimeError. Added to pyproject.toml base deps and Dockerfile.runtime-base.
## 2026-05-14 — Pin package version in base image builds to avoid PyPI CDN lag (#91)

The Dockerfiles for base images installed fastapifromfrictionless without a version pin. When build-images.yml fired right after the PyPI publish, pip sometimes got the previous cached version. Added ARG PACKAGE_VERSION to both Dockerfiles and a PyPI polling step in the workflow that retries up to 12 minutes before starting the Docker builds. The workflow also now passes build-args: PACKAGE_VERSION=... to both builds.
## 2026-05-14 — Fix Frictionless 'any' type → typing.Any has no SQLAlchemy mapping (#89)

Frictionless 'any' type was mapped to typing.Any in the type_map, but typing.Any has no SQLAlchemy column type, causing ValueError at startup for any schema with an 'any' field. Changed mapping to 'str' (stored as text). Updated the corresponding test. 90 tests passing.
## 2026-05-14 — Fix NameError: Any not imported in generated models header (#85)

The models_header.py.jinja2 template imported Optional and List from typing but not Any, causing NameError at startup for schemas with field types 'any', 'object', or 'array'. Added Any to the import. 90 tests passing.
## 2026-05-14 — Fix geoalchemy2 missing dependency (#81)

Schemas without geo field types raised ModuleNotFoundError because models_header.py.jinja2 unconditionally imported from geoalchemy2. Added has_geo tracking in model.build() and made the import conditional in the template. Also added geoalchemy2 to pyproject.toml base dependencies and podman/Dockerfile.runtime-base so the runtime image includes it. 89 tests passing.
## Issue #66 — Update README and quickstart notebook

Fixed docs that became stale after the multi-stage Dockerfile (#60) and pre-built base images (#63):
- README Deployment section: three containers not two, explicit build step, pre-built image callout
- Notebook Step 1: updated folder listing, pre-built image explanation
- Notebook Step 3: added SCHEMA_FOLDER to .env example
- Notebook Step 4: rewritten — generation is at build time, not startup
- Notebook Step 8: rewritten — schema changes require rebuild not restart

---

## Issue #63 — Pre-built base images for faster Podman deployment

Added two base images published to ghcr.io on each release via `.github/workflows/build-images.yml`:
- `ghcr.io/jinskeep-morpc/fastapi-from-frictionless-generator` — python:3.12-slim + [generate] extras
- `ghcr.io/jinskeep-morpc/fastapi-from-frictionless-runtime` — python:3.12-slim + runtime deps

`podman/Dockerfile` now pulls these instead of re-running pip from scratch. Build time drops from ~3 min to ~20 s. Released as v0.2.1.

---

## Issue #60 — SCHEMA_FOLDER env variable

Made the schema folder name configurable via `SCHEMA_FOLDER` (default: `schemas`). The variable threads through the Dockerfile `ARG`, the compose `build.args`, and the runtime volume mount (`./${SCHEMA_FOLDER:-schemas}:/schemas:Z`). Updated `.env.example` and `podman/README.md` to document it.

---

## 2026-05-14 — Issue #60: Multi-stage Dockerfile

Moved `frictionless` and `jinja2` to an optional `[generate]` extra in `pyproject.toml` (also added both to `[dev]` so CI tests still pass). Made `validate.py` frictionless import lazy (moved inside functions). Removed dead top-level frictionless imports from `load.py`. Two-stage `podman/Dockerfile`: Stage 1 installs `fastapifromfrictionless[generate]`, copies `schemas/`, and generates the app code; Stage 2 installs the slim base (no frictionless/jinja2) and runs uvicorn against the pre-built code. Simplified `entrypoint.sh` (no generation step). Updated `podman/README.md` to document the new build-time generation workflow.

---

## 2026-05-14 — Issue #58: Replace doc/ with quickstart notebook

Removed all legacy content from `doc/` (two devlog notebooks, stale generated Python files pre-dating the Jinja2 templates, `__pycache__`, `.log`, `.db`). Created `doc/quickstart.ipynb`: a 9-step narrative walkthrough of the podman deployment workflow — define schemas (Python cells writing YAML), configure `.env`, start the stack (`podman-compose up -d`), explore the API (requests cells that work against a live stack), browse with pgAdmin, Excel import/export, schema updates, and cleanup. Shell commands shown inline in markdown; no attempt to run podman from within the notebook.

---

## 2026-05-14 — Issue #54: Podman deployment

Added `podman/` folder with six files: `compose.yaml` (two services — `postgres` using `docker.io/postgis/postgis` and `api` built from the local Dockerfile; shared bridge network `10.91.0.0/16` with static IPs following the podgis pattern), `Dockerfile` (Python 3.12-slim, installs `fastapifromfrictionless`, `uvicorn[standard]`, `psycopg2-binary`), `entrypoint.sh` (generates app files from mounted `/schemas` volume into `/app/api/` package at startup, then runs `uvicorn api.app:app`), `.env.example` (documents all env vars), `.gitignore` (ignores `.env` and `postgres/`), and `README.md` (setup instructions). The generated code uses relative imports so the entrypoint creates `api/__init__.py` to make the output directory a proper Python package before uvicorn starts.

---

## 2026-05-13 — Issue #52: Expand documentation

Rewrote README Quick Start with six numbered sections: CLI usage, starting the app, endpoint table per resource (POST, GET/all, GET/recent, GET/{pk}, PATCH, DELETE, GET/query, GET/excel/export, POST/excel/import), env var configuration table (DATABASE_URL, ALLOWED_ORIGINS, API_KEY, SCHEMA_FOLDER, API_URL), Excel workflow code examples, and CLI reference. Added jinja2 to Requirements list. Updated Core capabilities. No code changes.

---

## 2026-05-13 — Issue #50: Default query routes

Added `GET /{resource}/recent` endpoint to all generated schemas. Returns the N most recently created records ordered by `created_at.desc()`. Accepts `limit` param (default 10, max 100). Uses `TimestampMixin` which all table models already have. 3 tests added; all 82 pass.

---

## 2026-05-13 — Issue #48: GET/POST Excel file endpoints

Added `GET /excel/export` and `POST /excel/import` routes to the generated `app_header.py.jinja2`. Export calls `dump_to_excel()` using `API_URL` and `SCHEMA_FOLDER` env vars and returns an xlsx `FileResponse`. Import accepts an `UploadFile`, saves to a temp file, runs `create_package` + `update_api_from_package` to sync rows into the database. Added `File`, `UploadFile`, `FileResponse`, `tempfile`, and `Path` imports. 3 tests added; all 79 pass.

---

## 2026-05-13 — Issue #46: Package versioning and automated releases

Updated `.github/workflows/python-publish.yml`: now uses `ubuntu-latest`, `fetch-depth: 0` (so setuptools-scm can read git tags), Python 3.12 consistent with CI, and correct PyPI URL (`fastapifromfrictionless`). Added `[tool.setuptools_scm]` section to `pyproject.toml` documenting the path to full scm-based versioning. Release is triggered by creating a GitHub Release (publishing a `v*` tag).

---

## 2026-05-13 — Issue #44: Configurable output

Added `--no-models`, `--no-app`, `--no-db` flags to the CLI `generate` subcommand. Each defaults to False (all files generated). Useful when iterating on schemas after initial setup to regenerate only the changed file. 3 tests added; all 76 pass.

---

## 2026-05-13 — Issue #42: Dry-run / preview mode

Added `--dry-run` flag to the CLI `generate` subcommand. When set, generated file contents are printed to stdout (with `===` separators per file) instead of written to disk. Reuses the same Jinja2 environment and generator objects, just routes output to print instead of file.write. 4 tests added; all 73 pass.

---

## 2026-05-13 — Issue #40: API key authentication

Added `X-API-Key` header authentication to the generated `app_header.py.jinja2` template using FastAPI's `APIKeyHeader` and `Security`. If `API_KEY` env var is set, all requests must include a matching header (returns 403 otherwise). If unset, auth is disabled (dev-friendly default). Applied globally via `FastAPI(dependencies=[Depends(verify_api_key)])`. 2 tests added; all 69 pass.

---

## 2026-05-13 — Issue #38: CLI entry point

Added `fastapifromfrictionless/cli.py` with a `generate` subcommand. Accepts `schema_folder` positional arg, `--output` (default `.`), and `--db` (default `database.db`). Calls the three generators directly and writes files to the output directory. Wired via `[project.scripts]` in `pyproject.toml` so `pip install -e .` makes `fastapifromfrictionless generate <schema-folder>` available. 6 tests added; all 67 pass.

---

## 2026-05-13 — Issue #36: Configuration management

Generated `database.py` now reads `DATABASE_URL` from the environment, falling back to the default SQLite file. `connect_args` is set conditionally (`{"check_same_thread": False}` for SQLite, `{}` otherwise) to enable PostgreSQL or other backends in production. `ALLOWED_ORIGINS` was already in `app.py`. 1 test added; all 61 pass.

---

## 2026-05-13 — Issue #34: CORS and security headers

Added `CORSMiddleware` (origins from `ALLOWED_ORIGINS` env var, comma-separated, default `*` for development) and `SecurityHeadersMiddleware` (sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`) to the generated `app_header.py.jinja2` template. 2 tests added; all 60 pass.

---

## 2026-05-13 — Issue #32: Pagination

Added `offset: int = 0` and `limit: int = Query(default=100, le=1000)` parameters to all generated `GET /all` endpoints. Uses SQLModel's `.offset().limit()` chaining on the select statement. 3 tests added; all 58 pass.

---

## 2026-05-13 — Issue #30: HTTP error responses

Added custom `HTTPException` and `RequestValidationError` handlers to the generated `app_header.py.jinja2` template. Both return consistent JSON bodies: `{"error": ..., "status_code": ...}` for HTTP errors and `{"error": "Validation error", "detail": [...]}` for validation failures. 2 tests added; all 55 pass.

---

## 2026-05-13 — Issue #28: Structured logging

Added `fastapifromfrictionless/logging_config.py` with `configure_logging(level, fmt, datefmt)`. Sets level on the `fastapifromfrictionless` package root logger, clears existing handlers on repeated calls, attaches `StreamHandler(sys.stderr)` with a default format `%(asctime)s %(levelname)-8s %(name)s — %(message)s`, and sets `propagate=False`. Accepts both string level names (case-insensitive) and integer levels; raises `ValueError` for unknown strings. Exported from `__init__.py`. 9 tests added; all 53 pass.

---

## 2026-05-13 — Issue #26: Jinja2 templating

Replaced raw f-string generation in `model.py`, `app.py`, and `database.py` with Jinja2 templates in `fastapifromfrictionless/templates/`. Used custom delimiters (`<< >>` for variables, `<% %>` for blocks) to avoid conflicts with Python's `{}` syntax in generated code. All logic (FK detection, type mapping, relationship building) stays in Python; templates handle layout only. Added `jinja2` to runtime dependencies and `templates/*.jinja2` to package-data. Added `jinja2` to `pyproject.toml` runtime dependencies. All 44 tests pass; ruff and mypy clean.

---

## 2026-05-13 — Issue #22: Type hints and mypy

Fixed 19 mypy errors across the package: (1) renamed loop variable `field` to `field_name` in `model.py` to avoid shadowing between `str` and `frictionless.Field` types; (2) annotated `basemodel_fields: list[str]` explicitly; (3) cast `PathLike` to `str` in `logging.getChild()` calls in `model.py` and `app.py`; (4) stored `self.folder` as `str` in both generators; (5) replaced `filename.split(".")` with `pathlib.Path(filename).stem` in `load.py`. Added `[tool.mypy]` config to `pyproject.toml`, `mypy` to `[dev]` extras, and a mypy step to the CI workflow. Also fixed 51 ruff issues and reformatted all source files. mypy and all 44 tests clean.

---

## 2026-05-13 — Issue #20: CI pipeline

Added `.github/workflows/ci.yml` — runs `ruff check`, `ruff format --check`, and `pytest` on every push/PR. Added `[dev]` optional dependencies to `pyproject.toml` (`pip install -e ".[dev]"`). Configured ruff with `target-version = "py312"` (codebase uses 3.12 f-string syntax), `line-length = 100`, and ignores for E501/E402/F403/F401. Fixed 61 lint issues across the package and formatted all source files. All 44 tests still passing.

---
## 2026-05-13 — Issue #18: CLAUDE.md workflow refinement

User updated the development workflow: removed the "ask about branch" and "ask before PR" interactive steps to support fully autonomous operation. Added a "update README roadmap" step (step 6) after writing tests. No code changes.

---

## 2026-05-13 — Issue #16: Generator unit tests

Added 30 pytest tests across three files covering the models, app, and database generators. Tests operate on generated source strings (no code execution) using minimal inline `tmp_path` fixtures. Discovered and worked around a PosixPath vs str bug in the generators' logger initialization — generators must be passed `str` paths, not `pathlib.Path`. All 30 tests pass.
## 2026-05-13 — Issue #14: Schema validation before code generation

Added `fastapifromfrictionless/validate.py` with `validate_schemas(folder)` and `assert_schemas_valid(folder)`. Validation checks: folder exists and contains schemas, each schema loads cleanly via frictionless (which catches bad types and PK mismatches), and FK references point to known schemas in the same folder. `assert_schemas_valid` is called in `models.__init__` so bad schemas raise `ValueError` with a full error list before any code is generated. Exported both functions from `__init__.py`. 10 pytest tests all passing.
## 2026-05-13 — Issue #12: dump_to_excel

Added `dump_to_excel(api_url, schema_folder, output_filepath)` to `load.py`. Fetches all records from each endpoint, reorders columns to match schema field order, handles endpoint errors gracefully (writes empty sheet instead of aborting), and autofits columns. Also created `tests/` with 4 pytest tests covering data rows, empty API, error resilience, and column ordering.

---

## 2026-05-13 — Issue #10: README rewrite

Rewrote README to replace the rough WIP checklist with a proper package overview, requirements list, Quick Start, and a structured production roadmap (Foundation → Code Quality → Production Readiness → Developer Experience → Optional). Also added CLAUDE.md with the 9-step development workflow and coding guidelines. No code changes.

---
