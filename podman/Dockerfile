# Stage 1 — generate the FastAPI application from schemas
#
# Installs the full [generate] extras (includes frictionless + jinja2) and
# runs the CLI against the schemas/ folder.  Nothing from this stage carries
# into the final image.
FROM python:3.12-slim AS generator
ARG SCHEMA_FOLDER=schemas
WORKDIR /generator
RUN pip install --no-cache-dir "fastapifromfrictionless[generate]"
COPY ${SCHEMA_FOLDER}/ /schemas/
RUN mkdir -p /generator/api && \
    python -m fastapifromfrictionless.cli generate /schemas --output /generator/api && \
    touch /generator/api/__init__.py

# Stage 2 — lean runtime image
#
# Installs only the packages the generated app needs at runtime.
# frictionless and jinja2 are intentionally excluded — they are only
# required for code generation, which already happened in Stage 1.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir \
    fastapifromfrictionless \
    "uvicorn[standard]" \
    psycopg2-binary

# Copy the pre-generated app from the generator stage
COPY --from=generator /generator/api/ /app/api/

EXPOSE 8000
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
