@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  fastapi-from-frictionless Windows test
echo ============================================================

:: ── 1. Install Python 3.12 via winget ────────────────────────
echo.
echo [1/5] Installing Python 3.12...
winget install -e --id Python.Python.3.12 ^
    --silent --accept-source-agreements --accept-package-agreements
if %errorlevel% neq 0 (
    echo ERROR: Python install failed. Check winget is available.
    pause
    exit /b 1
)

:: Reload PATH so python.exe is visible in this session
set "PYTHON=C:\Program Files\Python312\python.exe"
set "PIP=C:\Program Files\Python312\Scripts\pip.exe"

:: ── 2. Upgrade pip ───────────────────────────────────────────
echo.
echo [2/5] Upgrading pip...
"%PYTHON%" -m pip install --upgrade pip

:: ── 3. Install fastapifromfrictionless ───────────────────────
echo.
echo [3/5] Installing fastapifromfrictionless[generate]...
"%PIP%" install "fastapifromfrictionless[generate]"
if %errorlevel% neq 0 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

:: ── 4. Generate API from bundled schemas ─────────────────────
echo.
echo [4/5] Running code generator...
set "SCHEMAS=%~dp0schemas"
set "OUTPUT=C:\test\output"
mkdir "%OUTPUT%" 2>nul
"%PYTHON%" -m fastapifromfrictionless.cli generate "%SCHEMAS%" --output "%OUTPUT%"
if %errorlevel% neq 0 (
    echo ERROR: Code generation failed.
    pause
    exit /b 1
)

echo.
echo Generated files:
dir /b "%OUTPUT%"

:: ── 5. Install runtime deps and start the app ────────────────
echo.
echo [5/5] Installing runtime deps and starting uvicorn...
"%PIP%" install fastapi uvicorn sqlmodel
cd /d "%OUTPUT%"
start "FastAPI test server" "%PYTHON%" -m uvicorn api.app:app --port 8000

echo.
echo ============================================================
echo  SUCCESS
echo  API running at http://localhost:8000
echo  Swagger UI at  http://localhost:8000/docs
echo  Generated files in: %OUTPUT%
echo ============================================================
pause
