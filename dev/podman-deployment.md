# Podman Deployment Architecture

This document explains how the API is packaged and deployed using containers, why certain decisions were made, and what security measures are in place.

---

## Why containers?

Without containers, deploying an application means installing the right version of Python, the right packages, and the right database software on each machine — and hoping they don't conflict with other software already installed. This is fragile and hard to reproduce.

A **container** solves this by bundling the application together with its exact dependencies into a single, self-contained unit. The container runs identically on any machine that has a container runtime installed, whether that is a developer laptop or a production server.

**Why Podman instead of Docker?**

Podman and Docker are largely compatible — they use the same image format and very similar commands. The key difference is that Podman runs **rootless** by default: containers run as your regular user account rather than as the system administrator (`root`). This is a security improvement because a bug inside a container cannot easily escalate to full system access. Docker traditionally requires a background daemon running as root.

---

## The four-container system

The deployment runs four containers that work together:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                  app_network  ({PODMAN_SUBNET}.0/16)                     │
│                                                                          │
│   ┌──────────────────┐    SQL     ┌──────────────────────────────────┐   │
│   │   postgres        │◄──────────│   api                            │   │
│   │   {subnet}.5      │           │   {subnet}.7                     │   │
│   │   PostGIS image   │           │   generated FastAPI app          │   │
│   │   port 5432       │           │   port 8000 (internal only)      │   │
│   └──────────────────┘           └──────────────────────────────────┘   │
│            ▲                                          ▲                  │
│            │  SQL                                     │  proxy           │
│   ┌──────────────────┐           ┌──────────────────────────────────┐   │
│   │   pgadmin         │           │   nginx                          │   │
│   │   {subnet}.6      │◄──────────│   {subnet}.8                     │   │
│   │   pgAdmin 4 image │  proxy    │   reverse proxy                  │   │
│   │   port 80         │           │   port 80                        │   │
│   │   (internal only) │           └──────────────────────────────────┘   │
│   └──────────────────┘                                                   │
└──────────────────────────────────────────────────────────────────────────┘
                                           │
                                    {NGINX_IP}:80
                               {PROJECT_NAME}.api
                               {PROJECT_NAME}.pgadmin
```

`{subnet}` is set by `PODMAN_SUBNET` in `.env` (e.g. `10.93.0`). The internal IPs are only relevant for container-to-container communication and do not need to be unique across deployments — each compose stack gets its own isolated bridge network.

| Container | Image | Purpose |
|-----------|-------|---------|
| `postgres` | `docker.io/postgis/postgis` | The database. PostGIS extends standard PostgreSQL with support for geographic data types (points, polygons, etc.) |
| `pgadmin` | `docker.io/dpage/pgadmin4` | A web-based graphical interface for browsing and editing the database directly |
| `api` | Built locally from `Dockerfile` | The generated FastAPI application |
| `nginx` | `docker.io/nginx:alpine` | Reverse proxy — routes `{project}.api` to the API and `{project}.pgadmin` to pgAdmin |

### Why a private network?

All four containers are placed on a private bridge network (`app_network`). This means:

- Containers talk to each other using their **service names** as hostnames (e.g. `postgres`). The `DATABASE_URL` in the API container uses `@postgres:5432` because the internal DNS resolves `postgres` to the postgres container's IP.
- Traffic between containers **never leaves the host machine** — it stays on the virtual network.
- Only nginx (port 80) is exposed to the host, bound to `NGINX_IP` rather than `0.0.0.0`.

### How hostname routing works

The nginx container receives `PROJECT_NAME` as an environment variable at startup. A small shell one-liner runs `envsubst` to fill `$PROJECT_NAME` into `nginx.conf.template` before nginx starts:

```
nginx.conf.template  +  PROJECT_NAME=my-project
            │
            │  envsubst '$PROJECT_NAME'
            ▼
        nginx.conf
          server_name my-project.api      → proxy_pass http://api:8000
          server_name my-project.pgadmin  → proxy_pass http://pgadmin:80
```

The `setup.sh` script adds the matching entries to `/etc/hosts`:

```
127.0.1.1   my-project.api
127.0.1.1   my-project.pgadmin
```

### Running multiple stacks without port conflicts

Each deployment is assigned a unique loopback IP via `NGINX_IP`. Linux treats the entire `127.0.0.0/8` range as loopback, so `127.0.1.1`, `127.0.1.2`, and so on all work without any extra network configuration.

```
127.0.1.1:80  →  stack A nginx  →  project-a.api / project-a.pgadmin
127.0.1.2:80  →  stack B nginx  →  project-b.api / project-b.pgadmin
```

Postgres for each stack is similarly bound to its `NGINX_IP`, so `127.0.1.1:5432` and `127.0.1.2:5432` never conflict either.

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
  Start nginx
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

The `:Z` suffix on each volume (`./postgres:/var/lib/postgresql/data:Z`) is a Podman/SELinux label that tells the operating system to grant the container permission to read and write that folder. It is required on systems with SELinux enabled (such as Fedora or RHEL).

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

## Pre-built base images

Building the generator and runtime base images (running `pip install`) takes 2–5 minutes. If every deployment rebuild had to `pip install` all packages from scratch, iterating on schema changes would be slow.

The solution is to publish **pre-built base images** to the GitHub Container Registry (`ghcr.io`). These images have all the packages already installed. Your project's `Dockerfile` inherits from them, so a rebuild only needs to:

1. Copy schema files into the generator stage (~seconds)
2. Run the CLI to generate three `.py` files (~seconds)
3. Copy those files into the runtime stage (~seconds)

### Where the base images come from

```
Developer merges code and creates a GitHub release
                    │
                    ▼
          python-publish.yml
          builds wheel → uploads to PyPI
                    │
                    ▼ (triggered automatically)
          build-images.yml
          polls PyPI until new version is visible
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
  Dockerfile.generator-base   Dockerfile.runtime-base
  FROM python:3.12-slim        FROM python:3.12-slim
  pip install                  pip install
    fastapifromfrictionless       fastapifromfrictionless
    [generate]==${VERSION}        uvicorn psycopg2-binary …
          │                    │
          ▼                    ▼
  ghcr.io/…/generator:latest  ghcr.io/…/runtime:latest
  ghcr.io/…/generator:0.2.16  ghcr.io/…/runtime:0.2.16
```

Both `:latest` and version-pinned tags (e.g. `:0.2.16`) are published. Using `:latest` always gives you the most recent release. Pinning to a version (e.g. `FROM …/runtime:0.2.14`) freezes your deployment to a specific known-good state.

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
| `PROJECT_NAME` | nginx, setup.sh | Hostname prefix — produces `{PROJECT_NAME}.api` and `{PROJECT_NAME}.pgadmin` |
| `NGINX_IP` | compose.yaml, setup.sh | Loopback IP this deployment binds to (e.g. `127.0.1.1`); must be unique per simultaneously running stack |
| `PODMAN_SUBNET` | compose.yaml | First three octets of the internal container network (e.g. `10.93.0`); used for static container IPs |
| `POSTGRES_USER` | postgres, api | Database login name |
| `POSTGRES_PASSWORD` | postgres, api | Database password |
| `POSTGRES_DB` | postgres, api | Name of the database to create |
| `PGADMIN_DEFAULT_EMAIL` | pgadmin | pgAdmin web UI login |
| `PGADMIN_DEFAULT_PASSWORD` | pgadmin | pgAdmin web UI password |
| `SCHEMA_FOLDER` | Dockerfile build, api | Host path to schema files; also determines what gets copied at build time |
| `API_KEY` | api | If set, all requests must include `X-API-Key: <value>` |
| `ALLOWED_ORIGINS` | api | CORS policy — which websites may call the API |
| `API_URL` | api | The public URL of the API (set to `http://{PROJECT_NAME}.api`); used when the import endpoint calls back to itself |

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

The private bridge network means postgres and pgadmin are not directly reachable from outside the host — only from other containers on the same network or through nginx.

nginx and postgres are bound to `NGINX_IP` (a loopback address), not `0.0.0.0`, so they are only reachable on the local machine. For a server exposed to a wider network, also consider:
- Removing postgres host port exposure entirely (pgAdmin inside the network can still reach it)
- Adding TLS termination at the nginx layer
- Restricting pgAdmin behind a VPN

### 6. Rootless Podman

Unlike Docker, Podman runs containers as your regular user by default. This means:

- A compromised container process runs with the same limited permissions as your user account
- No root daemon is listening on a socket that could be exploited
- File ownership: files written by the container (into the `./postgres/` and `./pgadmin/` volumes) are owned by your user, not root

The `:Z` volume label works with this model — it relabels the host directory so the container's user-namespace UID can read and write it.

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
podman-compose build api

# 3. Restart the API container
podman-compose up -d api
```

The database is not automatically migrated. If you add a column to a schema, you may also need to alter the database table manually, or drop and recreate it (losing data).

### Package version update

When a new version of `fastapifromfrictionless` is released and the base images on `ghcr.io` are updated:

```bash
# Pull the new base images
podman pull ghcr.io/jinskeep-morpc/fastapi-from-frictionless-generator:latest
podman pull ghcr.io/jinskeep-morpc/fastapi-from-frictionless-runtime:latest

# Rebuild your API image (uses the freshly pulled bases)
podman-compose build --no-cache api

# Restart
podman-compose stop api
podman rm <api_container_name>
podman-compose up -d api
```

### Stopping and cleaning up

Always use `teardown.sh` rather than calling `podman-compose down` directly. It removes the network bridge from the rootless namespace (see [Rootless Podman networking gotchas](#rootless-podman-networking-gotchas)) as well as the `/etc/hosts` entries:

```bash
# Stop containers and clean up hosts entries and bridge
./teardown.sh

# Also delete persisted data (destructive — cannot be undone)
./teardown.sh
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

**The fix:** `setup.sh` reads the assigned bridge name from the network config and deletes any existing interface before starting:

```bash
bridge=$(podman network inspect "${NETWORK_NAME}" | python3 -c "...")
podman unshare --rootless-netns -- ip link delete "$bridge"
```

`teardown.sh` does the same cleanup on the way down so subsequent runs always start with a clean slate.

**How to diagnose it manually:** if containers start but the API can't connect to postgres, run:

```bash
podman unshare --rootless-netns ip -brief addr
```

If the bridge for your network has the wrong IP (e.g. shows `10.91.0.1` when `PODMAN_SUBNET` is `10.93.0`), that is the ghost bridge. Delete it with:

```bash
podman unshare --rootless-netns -- ip link delete podmanN
```

Then run `./teardown.sh && ./setup.sh` for a clean start.

### Port 80 requires a one-time sysctl change

Linux reserves ports below 1024 for privileged processes. Rootless Podman (which runs as a normal user) cannot bind to port 80 by default. The symptom is:

```
Error: rootlessport cannot expose privileged port 80 ... listen tcp ...:80: bind: permission denied
```

Fix with a one-time change to `/etc/sysctl.conf`:

```bash
echo "net.ipv4.ip_unprivileged_port_start=80" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

This allows any process running as your user to bind to port 80 or above. It persists across reboots.

### Postgres port conflicts with legacy stacks

The per-loopback-IP design (`NGINX_IP=127.0.1.1`, `127.0.1.2`, etc.) prevents port conflicts between deployments that both use this scheme, because each stack's services are bound to a different IP address on the same port.

However, a legacy deployment that binds postgres to `0.0.0.0:5432` occupies that port on **all** interfaces — including `127.0.1.1`, `127.0.1.2`, and every other loopback address. No new deployment can expose postgres to the host until the legacy stack is updated or its postgres port mapping is removed.
