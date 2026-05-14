# Stage 1 — generate the FastAPI application from schemas
#
# Uses the pre-built generator image (deps already installed).
# Copies schemas into /schemas and runs the CLI to produce /generator/api/.
# Nothing from this stage carries into the final image.
FROM ghcr.io/jinskeep-morpc/fastapi-from-frictionless-generator:latest AS generator
ARG SCHEMA_FOLDER=schemas
COPY ${SCHEMA_FOLDER}/ /schemas/
RUN mkdir -p /generator/api && \
    python -m fastapifromfrictionless.cli generate /schemas --output /generator/api && \
    touch /generator/api/__init__.py

# Stage 2 — lean runtime image
#
# Uses the pre-built runtime image (deps already installed).
# frictionless and jinja2 are intentionally excluded — code generation
# already happened in Stage 1.
FROM ghcr.io/jinskeep-morpc/fastapi-from-frictionless-runtime:latest
COPY --from=generator /generator/api/ /app/api/

EXPOSE 8000
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
