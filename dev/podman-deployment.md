# Podman Deployment Architecture

This document explains how the API is packaged and deployed using containers, why certain decisions were made, and what security measures are in place.

---

## Why containers?

Without containers, deploying an application means installing the right version of Python, the right packages, and the right database software on each machine — and hoping they don't conflict with other software already installed. This is fragile and hard to reproduce.

A **container** solves this by bundling the application together with its exact dependencies into a single, self-contained unit. The container runs identically on any machine that has a container runtime installed, whether that is a developer laptop or a production server.

**Why Podman instead of Docker?**

Podman and Docker are largely compatible — they use the same image format and very similar commands. The key difference is that Podman runs **rootless** by default: containers run as your regular user account rather than as the system administrator (`root`). This is a security improvement because a bug inside a container cannot easily escalate to full system access. Docker traditionally requires a background daemon running as root.

---

## The three-container system

The deployment runs three containers that work together:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                  app_network  ({SUBNET_BASE}.0/16)                       │
│                                                                          │
│   ┌──────────────────┐    SQL     ┌──────────────────────────────────┐   │
│   │   postgres        │◄──────────│   api                            │   │
│   │   {subnet}.5      │           │   {subnet}.7                     │   │
│   │   PostGIS image   │           │   generated FastAPI app          │   │
│   │   port 5432       │           │   port 8000                      │   │
│   └──────────────────┘           └──────────────────────────────────┘   │
│            ▲                                                             │
│            │  SQL                                                        │
│   ┌──────────────────┐                                                   │
│   │   pgadmin         │                                                  │
│   │   {subnet}.6      │                                                  │
│   │   pgAdmin 4 image │                                                  │
│   │   port 80         │                                                  │
│   └──────────────────┘                                                   │
└──────────────────────────────────────────────────────────────────────────┘
          │                    │                    │
    localhost:DB_PORT   localhost:PGADMIN_PORT  localhost:API_PORT
```

`{subnet}` is set by `SUBNET_BASE` in `.env` (e.g. `10.91`). The internal IPs are only relevant for container-to-container communication and do not need to be unique across deployments — each compose stack gets its own isolated bridge network.

| Container | Image | Purpose |
|-----------|-------|---------|
| `postgres` | `docker.io/postgis/postgis` | The database. PostGIS extends standard PostgreSQL with support for geographic data types (points, polygons, etc.) |
| `pgadmin` | `docker.io/dpage/pgadmin4` | A web-based graphical interface for browsing and editing the database directly |
| `api` | Built locally from `Dockerfile` | The generated FastAPI application |

### Why a private network?

All three containers are placed on a private bridge network (`app_network`). This means:

- Containers talk to each other using their **service names** as hostnames (e.g. `postgres`). The `DATABASE_URL` in the API container uses `@postgres:5432` because the internal DNS resolves `postgres` to the postgres container's IP.
- Traffic between containers **never leaves the host machine** — it stays on the virtual network.
- Each service also has a direct host port binding (`API_PORT`, `PGADMIN_PORT`, `DB_PORT`) so the user can reach it at `localhost:PORT`.

### Running multiple stacks without port conflicts

Each deployment must use a different `SUBNET_BASE` (for the internal network) and a different set of host ports. Port conflicts between stacks are prevented by choosing non-overlapping port numbers:

| | Stack A | Stack B |
|---|---------|---------|
| `SUBNET_BASE` | `10.91` | `10.92` |
| `API_PORT` | `8000` | `8100` |
| `PGADMIN_PORT` | `5050` | `5150` |
| `DB_PORT` | `5432` | `5532` |
| API URL | `http://localhost:8000` | `http://localhost:8100` |

This approach works identically on Linux, macOS, and Windows — no loopback IP tricks or `/etc/hosts` edits required.

---

## Startup order and health checks

The database must be ready before the API or pgAdmin can connect to it. The `compose.yaml` declares this with `depends_on: condition: service_healthy`:

```
podman-compose up
       │
       ▼
  Start postgres
       │
       │  healthcheck: pg_isready (every 10s, up to 5 retries)
       │
       ▼  (only after postgres reports healthy)
  Start pgadmin
  Start api
```

The health check runs `pg_isready` inside the postgres container, which is the standard tool for checking whether PostgreSQL is accepting connections.

**Caveat — `podman-compose` startup ordering:** `podman-compose` 1.x translates `depends_on` into the `--requires` flag on `podman run`, which only guarantees that postgres *starts* before the API — not that it has passed the health check. In practice, postgres initialises quickly enough that this is not a problem on a clean start. If it does become an issue (API exits on first run with a connection error), simply run `podman-compose up -d api` again after postgres is healthy.

---

## Data persistence

Containers are **stateless** by default — when a container is deleted, everything inside it is gone. Databases need their data to survive restarts.

The `compose.yaml` uses **bind mounts** to solve this: a folder on your host machine is mounted into the container. The database writes its files there instead of inside the container.

| Host folder | Mounted into | What is stored |
|-------------|--------------|----------------|
| `./postgres/` | `/var/lib/postgresql/data` | All database tables, indexes, and records |
| `./pgadmin/` | `/var/lib/pgadmin` | pgAdmin saved connections and preferences |
| `./${SCHEMA_FOLDER}/` | `/schemas/` | The `*.schema.yaml` files |

No special volume flags are used — the bind mounts work as-is on Linux, macOS, and Windows. On SELinux-enabled systems (Fedora, RHEL), you may need to add `:Z` to each volume mount if Podman reports a permission error on the host directory.

---

## The two-stage Docker build

Building the `api` container image is split into two stages. This is the most important design decision in the Dockerfile, so it deserves a detailed explanation.

### The problem being solved

Generating Python code from schemas requires `frictionless` and `jinja2` — two libraries that are only needed during code generation. The running API does not need them. Including them in the final image would:

- Make the image larger (~50–100 MB extra)
- Increase the attack surface (more software = more potential vulnerabilities)

### The solution: two-stage build

```
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 1: generator  (temporary, discarded after build)          │
│                                                                  │
│  FROM fastapi-from-frictionless-generator:latest                 │
│       │                                                          │
│       │  already has: python, frictionless[generate], jinja2     │
│       │                                                          │
│  COPY schemas/ → /schemas/                                       │
│  RUN  python -m fastapifromfrictionless.cli generate             │
│         /schemas → /generator/api/                               │
│                                                                  │
│  produces: models.py, app.py, database.py, __init__.py           │
└──────────────┬───────────────────────────────────────────────────┘
               │  COPY --from=generator
               │  only the generated .py files are carried forward
               ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 2: runtime  (this is the final image)                     │
│                                                                  │
│  FROM fastapi-from-frictionless-runtime:latest                   │
│       │                                                          │
│       │  already has: python, fastapifromfrictionless,           │
│       │               uvicorn, psycopg2-binary                   │
│       │                                                          │
│  COPY /generator/api/ → /app/api/                                │
│  CMD  uvicorn api.app:app                                        │
│                                                                  │
│  does NOT contain: frictionless schemas, jinja2, schema files    │
└──────────────────────────────────────────────────────────────────┘
```

The final image contains only:
- The Python runtime
- The installed packages needed to run a FastAPI app
- The three generated `.py` files

The schema YAML files, Jinja2, and the Frictionless library do not exist in the running container.

> **Note:** The schema folder is still **volume-mounted** into the runtime container at `/schemas/`. This is needed at runtime for the Excel import/export endpoints, which read schema files to understand column names and data types.

---

## Layer caching and build speed

The `Dockerfile` is ordered to maximise Docker's layer cache:

1. `pip install` — slow (~2–3 min on a cold machine); runs first so it is cached
2. `COPY schemas/` — fast; invalidates only the layers below it
3. `python -m fastapifromfrictionless.cli generate` — fast

This means schema changes only retrigger the code-generation step and later layers — the slow pip install is skipped unless the Dockerfile itself changes. On a warm cache, a schema rebuild takes seconds.

To pin a specific `fastapifromfrictionless` version instead of installing the latest:

```bash
docker compose build --build-arg PACKAGE_VERSION=0.2.16 api
```

---

## Environment variables and the `.env` file

All configuration is passed through environment variables. The `.env` file holds these values on the host; `compose.yaml` injects them into each container at startup.

```
.env file (on host)
    │
    │  read by podman-compose
    ▼
compose.yaml environment: blocks
    │
    │  injected into container at startup
    ▼
os.getenv("API_KEY") inside the running Python process
```

| Variable | Used by | Purpose |
|----------|---------|---------|
| `SUBNET_BASE` | compose.yaml | First two octets of the internal container network (e.g. `10.91`); must be unique per simultaneously running stack |
| `API_PORT` | compose.yaml | Host port for the FastAPI service; must be unique per simultaneously running stack |
| `PGADMIN_PORT` | compose.yaml | Host port for pgAdmin; must be unique per simultaneously running stack |
| `DB_PORT` | compose.yaml | Host port for PostgreSQL; must be unique per simultaneously running stack |
| `PROJECT_NAME` | compose.yaml | Informational label; no longer drives hostnames |
| `POSTGRES_USER` | postgres, api | Database login name |
| `POSTGRES_PASSWORD` | postgres, api | Database password |
| `POSTGRES_DB` | postgres, api | Name of the database to create |
| `PGADMIN_DEFAULT_EMAIL` | pgadmin | pgAdmin web UI login |
| `PGADMIN_DEFAULT_PASSWORD` | pgadmin | pgAdmin web UI password |
| `SCHEMA_FOLDER` | Dockerfile build, api | Host path to schema files; also determines what gets copied at build time |
| `API_KEY` | api | If set, all requests must include `X-API-Key: <value>` |
| `ALLOWED_ORIGINS` | api | CORS policy — which websites may call the API |
| `API_URL` | api | The public base URL of the API (e.g. `http://localhost:8000`); must match `API_PORT`; used by the Excel export/import endpoints |

---

## Security considerations

### 1. Secret management — the `.env` file

**The `.env` file is listed in `.gitignore` and must never be committed to version control.**

It contains database passwords and the API key in plain text. If it were committed to a public repository, anyone could access the database. The `.env.example` file serves as a template showing which variables are needed, with placeholder values.

For production deployments, consider using a secrets manager (such as HashiCorp Vault, AWS Secrets Manager, or systemd credentials) instead of a plain `.env` file.

### 2. API key authentication

The generated `app.py` checks the `X-API-Key` header on every request when `API_KEY` is set:

```python
async def verify_api_key(api_key: str = Security(_api_key_header)):
    if _API_KEY and api_key != _API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
```

- **`API_KEY` is empty**: authentication is disabled. Fine for local development; never appropriate for a publicly accessible deployment.
- **`API_KEY` is set**: every HTTP request must include the header `X-API-Key: <your_key>`.

Use a long, randomly generated key (32+ characters). A command to generate one:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 3. CORS — controlling which websites can call the API

CORS (Cross-Origin Resource Sharing) is a browser security mechanism. If your API is at `http://server:8000` and a web page at `http://other-site.com` tries to call it, the browser will block the request unless the API explicitly allows that origin.

| `ALLOWED_ORIGINS` value | Effect | When to use |
|-------------------------|--------|-------------|
| `*` | Any website can call the API | Local development only |
| `http://myapp.example.com` | Only that specific site | Production |
| `http://app1.com,http://app2.com` | Two specific sites | Multiple known frontends |

**Always restrict `ALLOWED_ORIGINS` in production.** Leaving it as `*` means any malicious website could make requests to your API on behalf of a logged-in user.

### 4. Security response headers

The generated `app.py` adds three security headers to every HTTP response via `SecurityHeadersMiddleware`:

| Header | What it prevents |
|--------|-----------------|
| `X-Content-Type-Options: nosniff` | Browser MIME-type sniffing attacks |
| `X-Frame-Options: DENY` | Clickjacking — embedding your page inside an `<iframe>` on another site |
| `Strict-Transport-Security` | Downgrade attacks — forces HTTPS on repeat visits |

These headers are a standard baseline. They have no effect on the API's functionality.

### 5. Network isolation

The private bridge network means containers communicate with each other using service names (`postgres`, `api`, `pgadmin`) without leaving the host. Each service also has a host-facing port binding on `localhost`.

For a server exposed to a wider network, also consider:
- Removing the `DB_PORT` host binding for postgres (pgAdmin inside the network can still reach it via the service name)
- Adding a TLS-terminating reverse proxy (e.g. Caddy or nginx) in front of `API_PORT`
- Restricting pgAdmin behind a VPN

### 6. Rootless Podman

Unlike Docker, Podman runs containers as your regular user by default. This means:

- A compromised container process runs with the same limited permissions as your user account
- No root daemon is listening on a socket that could be exploited
- File ownership: files written by the container (into the `./postgres/` and `./pgadmin/` volumes) are owned by your user, not root

### 7. Changing default credentials

The `.env.example` ships with `CHANGE_ME_STRONG_PASSWORD` as a placeholder. Before any deployment:

- Set `POSTGRES_PASSWORD` to a long random string
- Set `PGADMIN_DEFAULT_PASSWORD` to a different long random string
- Set `API_KEY` to a long random string
- Never reuse passwords across services

---

## Updating the deployment

### Schema change (e.g. adding a field)

Schema changes require a rebuild because code generation happens at build time:

```bash
# 1. Edit your *.schema.yaml file
# 2. Rebuild the API image
docker compose build api   # or: podman-compose build api

# 3. Restart the API container
docker compose up -d api   # or: podman-compose up -d api
```

The database is not automatically migrated. If you add a column to a schema, you may also need to alter the database table manually, or drop and recreate it (losing data).

### Package version update

When a new version of `fastapifromfrictionless` is released:

```bash
# Rebuild the API image — pip installs the latest version from PyPI
docker compose build --no-cache api   # or: podman-compose build --no-cache api

# Restart
docker compose up -d api
```

To pin a specific version instead of taking the latest:

```bash
docker compose build --build-arg PACKAGE_VERSION=0.2.17 api
docker compose up -d api
```

### Stopping and cleaning up

```bash
# Stop containers
docker compose down   # or: podman-compose down

# Also delete persisted data (destructive — cannot be undone)
docker compose down
rm -rf ./postgres/ ./pgadmin/
```

---

## Rootless Podman networking gotchas

Rootless Podman uses a more complex network stack than Docker. Two issues come up reliably when starting, stopping, and restarting deployments.

### Ghost bridge blocks DNS after a failed first run

Rootless Podman's networking has two layers:
- **Container networking** — `netavark` creates a bridge inside the user's network namespace (not visible in the host's `ip link` output). Each compose stack gets a bridge named `podman1`, `podman2`, etc.
- **DNS** — `aardvark-dns` runs in that same namespace and listens at the bridge gateway IP (e.g. `10.93.0.1:53`). Containers have this IP configured as their nameserver, which is how they resolve service names like `postgres`.

**The problem:** `podman-compose down` removes containers and the Podman network record, but **does not remove the bridge interface** from the user network namespace. If a first run fails partway through — for example, because a port is already in use — the bridge is left behind. On the next `podman-compose up`, Podman assigns the same bridge name to the new network but finds the interface already exists and skips recreating it. The bridge retains the old gateway IP, aardvark-dns cannot bind to the new one, and all hostname resolution silently fails. Containers can still ping each other by IP, but service name lookups time out.

**The fix:** run `podman-compose down`, then manually delete the stale bridge before restarting:

```bash
podman-compose down
podman unshare --rootless-netns -- ip link delete podmanN
podman-compose up -d
```

**How to diagnose:** if containers start but the API can't connect to postgres, run:

```bash
podman unshare --rootless-netns ip -brief addr
```

If the bridge for your network has the wrong IP (e.g. shows `10.91.0.1` when `SUBNET_BASE` is `10.92`), that is the ghost bridge. Delete it with:

```bash
podman unshare --rootless-netns -- ip link delete podmanN
```

Then run `podman-compose down && podman-compose up -d` for a clean start.

### Port conflicts between stacks

Since each stack binds services directly to host ports, two stacks using the same `API_PORT`, `PGADMIN_PORT`, or `DB_PORT` will conflict. The second stack to start will fail with a "port already in use" error. Fix by assigning each stack a non-overlapping port set in its `.env`.
