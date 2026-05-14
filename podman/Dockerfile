FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapifromfrictionless \
    "uvicorn[standard]" \
    psycopg2-binary

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
