@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  Phase 1: Install Docker Desktop
echo  Run this ONCE from \\host.lan\Data\install_docker.bat
echo  The VM will reboot; deploy_test.bat runs automatically after.
echo ============================================================

:: ── Download Docker Desktop installer ────────────────────────
echo.
echo [1/3] Downloading Docker Desktop...
powershell -Command "Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker Desktop Installer.exe' -OutFile 'C:\DockerDesktopInstaller.exe'"
if %errorlevel% neq 0 (
    echo ERROR: Failed to download Docker Desktop installer.
    pause
    exit /b 1
)

:: ── Install Docker Desktop silently ──────────────────────────
echo.
echo [2/3] Installing Docker Desktop (this takes a few minutes)...
"C:\DockerDesktopInstaller.exe" install --quiet --accept-license --backend=hyper-v
if %errorlevel% neq 0 (
    echo ERROR: Docker Desktop installation failed.
    pause
    exit /b 1
)

:: ── Schedule deploy_test.bat to run after reboot ─────────────
echo.
echo [3/3] Scheduling deploy_test.bat to run after reboot...
schtasks /create /tn "DockerDeployTest" /tr "cmd.exe /c '\\host.lan\Data\deploy_test.bat' > C:\deploy_test.log 2>&1" /sc ONLOGON /ru "%USERNAME%" /f
if %errorlevel% neq 0 (
    echo WARNING: Could not schedule deploy_test.bat. Run it manually after reboot.
)

echo.
echo ============================================================
echo  Rebooting in 15 seconds...
echo  After reboot: deploy_test.bat will run automatically, OR
echo  run it manually from \\host.lan\Data\deploy_test.bat
echo ============================================================
shutdown /r /t 15
