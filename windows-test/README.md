# Windows Test VM

Spins up a Windows 11 VM using [dockur/windows](https://github.com/dockur/windows) (QEMU/KVM inside Docker) and automatically installs and tests `fastapifromfrictionless` on Windows.

## Prerequisites

- Linux host with `/dev/kvm` available (`ls /dev/kvm`)
- Docker with Compose plugin (`docker compose version`)

## Usage

```bash
cd windows-test/
cp .env.example .env   # adjust RAM/CPU if needed
docker compose up -d
```

Then open **http://localhost:8006** in your browser.

### First run (~15–30 min)

Windows 11 downloads and installs automatically. Once the desktop appears, `install.bat` from the `/oem` volume runs automatically and:

1. Installs Python 3.12 via `winget`
2. Installs `fastapifromfrictionless[generate]` from PyPI
3. Generates a FastAPI app from `oem/schemas/sensor.schema.yaml` into `C:\test\output\`
4. Starts the generated app with `uvicorn` on port 8000

A summary is printed and the window pauses so you can review the output.

### Subsequent runs (~1 min)

The Windows disk image is persisted in the `windows-data` Docker volume — Windows does not reinstall. Start and stop with:

```bash
docker compose up -d    # start
docker compose down     # stop (disk preserved)
```

To wipe the disk and start fresh:
```bash
docker compose down -v  # removes the windows-data volume
```

## Connecting via RDP

Use any RDP client (Windows Remote Desktop, Remmina, FreeRDP):

- **Host**: `localhost:3389`
- **Username**: value of `WIN_USERNAME` in `.env` (default: `User`)
- **Password**: value of `WIN_PASSWORD` in `.env` (default: `test`)

## What's being tested

| Check | How |
|-------|-----|
| `pip install` on Windows | `install.bat` step 3 |
| CLI code generation on Windows paths | `install.bat` step 4 |
| Generated `app.py` / `models.py` / `database.py` exist | `dir C:\test\output\` |
| `uvicorn` starts the generated app | `install.bat` step 5 |
| Swagger UI loads | `http://localhost:8000/docs` in the VM browser |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WINDOWS_VERSION` | `11` | Windows version (`10`, `11`, `2022`, etc.) |
| `RAM_SIZE` | `4G` | RAM allocated to the VM |
| `CPU_CORES` | `2` | CPU cores allocated |
| `DISK_SIZE` | `64G` | Disk image size |
| `WIN_USERNAME` | `User` | Windows login username |
| `WIN_PASSWORD` | `test` | Windows login password |
| `NOVNC_PORT` | `8006` | Host port for browser UI |
| `RDP_PORT` | `3389` | Host port for RDP |
