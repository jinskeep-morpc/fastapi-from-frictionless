@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  Phase 2: Docker Deployment Test
echo  Tests the full docker compose deployment on Windows
echo ============================================================

:: ── Wait for Docker Engine to be ready ───────────────────────
echo.
echo [1/4] Waiting for Docker Engine...
set DOCKER_READY=0
for /l %%i in (1,1,20) do (
    if !DOCKER_READY! == 0 (
        docker info >nul 2>&1
        if !errorlevel! == 0 (
            set DOCKER_READY=1
            echo Docker is ready.
        ) else (
            echo   Attempt %%i/20 - not ready yet, waiting 15s...
            timeout /t 15 /nobreak >nul
        )
    )
)
if %DOCKER_READY% == 0 (
    echo ERROR: Docker Engine did not become ready after 5 minutes.
    echo Make sure Docker Desktop is running and Hyper-V is enabled.
    pause
    exit /b 1
)

:: ── Copy deployment files to C:\deploy\ ──────────────────────
echo.
echo [2/4] Copying deployment files...
mkdir C:\deploy 2>nul
xcopy /E /I /Y "\\host.lan\Data\deploy" "C:\deploy\"
if %errorlevel% neq 0 (
    echo ERROR: Failed to copy deployment files from \\host.lan\Data\deploy
    pause
    exit /b 1
)
echo Deployment files copied to C:\deploy\

:: .env.test is tracked in git; rename to .env for compose
copy /Y "C:\deploy\.env.test" "C:\deploy\.env"

:: ── Build and run docker compose ─────────────────────────────
echo.
echo [3/4] Building API image (no cache) and starting services...
echo (Pulls latest fastapifromfrictionless from PyPI — takes 5-10 minutes)
cd /d C:\deploy
docker compose build --no-cache api
if %errorlevel% neq 0 (
    echo ERROR: docker compose build failed.
    echo Check logs with: docker compose logs
    pause
    exit /b 1
)
docker compose up -d --force-recreate
if %errorlevel% neq 0 (
    echo ERROR: docker compose up failed.
    echo Check logs with: docker compose logs
    pause
    exit /b 1
)

:: ── Wait for API to respond ───────────────────────────────────
echo.
echo [4/4] Waiting for API to be ready at http://localhost:8000/docs ...
set API_READY=0
for /l %%i in (1,1,24) do (
    if !API_READY! == 0 (
        powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/docs' -UseBasicParsing -TimeoutSec 5; exit 0 } catch { exit 1 }" >nul 2>&1
        if !errorlevel! == 0 (
            set API_READY=1
        ) else (
            echo   Attempt %%i/24 - not ready yet, waiting 15s...
            timeout /t 15 /nobreak >nul
        )
    )
)

echo.
echo ============================================================
if %API_READY% == 1 (
    echo  PASS: API is running at http://localhost:8000
    echo  Swagger UI: http://localhost:8000/docs
    echo  pgAdmin:    http://localhost:5050
    echo  All services:
    docker compose ps
) else (
    echo  FAIL: API did not respond after 6 minutes.
    echo  Check logs with: cd C:\deploy ^&^& docker compose logs
)
echo ============================================================
pause
