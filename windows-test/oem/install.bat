@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  fastapi-from-frictionless Windows test
echo ============================================================

:: ── 1. Download and install Python 3.12 ─────────────────────
echo.
echo [1/5] Downloading Python 3.12...
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe' -OutFile 'C:\python-installer.exe'"
if %errorlevel% neq 0 (
    echo ERROR: Failed to download Python installer. Check network connectivity.
    pause
    exit /b 1
)

echo Installing Python 3.12 (silent)...
C:\python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
if %errorlevel% neq 0 (
    echo ERROR: Python installation failed.
    pause
    exit /b 1
)

:: Allow installer to finalise before referencing the new paths
timeout /t 10 /nobreak >nul

set "PYTHON=C:\Program Files\Python312\python.exe"
set "PIP=C:\Program Files\Python312\Scripts\pip.exe"

:: Verify Python is reachable
"%PYTHON%" --version
if %errorlevel% neq 0 (
    echo ERROR: python.exe not found at expected path after installation.
    pause
    exit /b 1
)

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
