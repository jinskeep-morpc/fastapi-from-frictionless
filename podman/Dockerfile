# Stage 1 — generate the FastAPI application from schemas
#
# Installs fastapifromfrictionless[generate] from PyPI, copies schemas,
# and runs the CLI to produce /generator/api/. Nothing from this stage
# carries into the final image.
FROM python:3.12-slim AS generator
ARG PACKAGE_VERSION
WORKDIR /generator
RUN if [ -n "$PACKAGE_VERSION" ]; then \
      pip install --no-cache-dir "fastapifromfrictionless[generate]==${PACKAGE_VERSION}"; \
    else \
      pip install --no-cache-dir "fastapifromfrictionless[generate]"; \
    fi
ARG SCHEMA_FOLDER=schemas
COPY ${SCHEMA_FOLDER}/ /schemas/

# WITH_UI adds the browser CRUD interface at /ui; SKIP_UI omits resources from
# it, e.g. a table too large to browse. Both are build-time: changing them
# needs `docker compose build api`, not just a restart.
ARG WITH_UI=
ARG SKIP_UI=
RUN mkdir -p /generator/api && \
    if [ -n "$WITH_UI" ]; then \
      UI_ARGS="--with-ui"; \
      if [ -n "$SKIP_UI" ]; then UI_ARGS="$UI_ARGS --skip-ui $SKIP_UI"; fi; \
    else \
      UI_ARGS=""; \
    fi && \
    python -m fastapifromfrictionless.cli generate /schemas --output /generator/api $UI_ARGS && \
    touch /generator/api/__init__.py

# Stage 2 — lean runtime image
#
# [app] extra adds fastapi_querybuilder (FK query endpoints) and geoalchemy2
# (geo field types). uvicorn and psycopg2-binary are server/DB deps not in
# the package itself.
FROM python:3.12-slim
ARG PACKAGE_VERSION
WORKDIR /app
RUN if [ -n "$PACKAGE_VERSION" ]; then \
      pip install --no-cache-dir \
        "fastapifromfrictionless[app]==${PACKAGE_VERSION}" \
        "uvicorn[standard]" \
        psycopg2-binary; \
    else \
      pip install --no-cache-dir \
        "fastapifromfrictionless[app]" \
        "uvicorn[standard]" \
        psycopg2-binary; \
    fi
COPY --from=generator /generator/api/ /app/api/

EXPOSE 8000
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
