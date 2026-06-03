# Windows Test VM

Spins up a Windows 11 VM using [dockur/windows](https://github.com/dockur/windows) (QEMU/KVM inside Docker) and tests `fastapifromfrictionless` on Windows in two modes:

- **Package test** (`install.bat`) — pip install + CLI code generation + uvicorn
- **Docker deployment test** (`install_docker.bat` → `deploy_test.bat`) — full `docker compose up -d` with PostGIS, pgAdmin, and the generated API

## Prerequisites

- Linux host with `/dev/kvm` available (`ls /dev/kvm`)
- Nested virtualization enabled (required for Docker Desktop in the VM): `cat /sys/module/kvm_amd/parameters/nested` should return `1`
- Docker with Compose plugin (`docker compose version`)
- 8 GB RAM allocated to the VM (default)

## Start the VM

```bash
cd windows-test/
cp .env.example .env   # adjust RAM/CPU if needed
docker compose up -d
```

Then open **http://localhost:8006** in your browser.

**First run:** Windows 11 downloads and installs automatically (~15–30 min). `install.bat` runs once Windows is ready.

**Subsequent runs:** Windows boots from the persisted disk (~1 min). Start/stop with:
```bash
docker compose up -d    # start
docker compose down     # stop (disk preserved)
docker compose down -v  # wipe disk and start fresh
```

> **Note:** If upgrading from a previous `windows-test` setup without `HYPERV: Y`, recreate the container: `docker compose up -d --force-recreate`

## Test 1 — Python package (`install.bat`)

Runs **automatically** on first Windows boot via the OEM mechanism. Also available at `\\host.lan\Data\install.bat`.

Steps:
1. Downloads and installs Python 3.12 from python.org
2. `pip install fastapifromfrictionless[generate] uvicorn`
3. Generates a FastAPI app from `schemas/sensor.schema.yaml`
4. Starts the app with `uvicorn` on port 8000

Check: open `http://localhost:8000/docs` from inside the VM browser.

## Test 2 — Docker deployment (two phases)

Tests the full `docker compose` deployment that end users run in production.

### Phase 1 — Install Docker Desktop (run once, requires reboot)

In the Windows VM (via noVNC or RDP):
1. Open **File Explorer** → address bar → `\\host.lan\Data`
2. Right-click `install_docker.bat` → **Run as administrator**
3. Docker Desktop installs silently, then the VM reboots automatically
4. `deploy_test.bat` is scheduled to run at next logon

### Phase 2 — Run the deployment test (auto after reboot, or manual)

After reboot, `deploy_test.bat` runs automatically. Or run it manually:
1. Open `\\host.lan\Data\deploy_test.bat` → **Run as administrator**

The script:
1. Waits for Docker Engine to be ready
2. Copies `\\host.lan\Data\deploy\` → `C:\deploy\` (compose.yaml, Dockerfile, schemas, .env)
3. Runs `docker compose up -d` — builds the API image, starts postgres + pgAdmin + API
4. Polls `http://localhost:8000/docs` until the API responds
5. Prints **PASS** or **FAIL** with service status

Check: open `http://localhost:8000/docs` and `http://localhost:5050` from inside the VM browser.

Logs are saved to `C:\deploy_test.log`.

## Connecting via RDP

- **Host**: `localhost:3389`
- **Username**: value of `WIN_USERNAME` in `.env` (default: `User`)
- **Password**: value of `WIN_PASSWORD` in `.env` (default: `test`)

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WINDOWS_VERSION` | `11` | Windows version (`10`, `11`, `2022`, etc.) |
| `RAM_SIZE` | `8G` | RAM allocated to the VM (8G needed for Docker Desktop) |
| `CPU_CORES` | `2` | CPU cores allocated |
| `DISK_SIZE` | `64G` | Disk image size |
| `WIN_USERNAME` | `User` | Windows login username |
| `WIN_PASSWORD` | `test` | Windows login password |
| `NOVNC_PORT` | `8006` | Host port for browser UI |
| `RDP_PORT` | `3389` | Host port for RDP |
