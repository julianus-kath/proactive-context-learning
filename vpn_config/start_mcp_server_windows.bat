@echo off
setlocal EnableExtensions

echo.
echo ========================================
echo   MCP Server Startup (Windows)
echo ========================================
echo.

rem --- Resolve PROJECT_ROOT robustly (parent of this folder) ---
pushd "%~dp0\.."
set "PROJECT_ROOT=%CD%"
popd

rem --- Prefer project virtualenv python (no fancy string ops) ---
set "PYTHON_CMD=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_CMD%" set "PYTHON_CMD=%PROJECT_ROOT%\venv\Scripts\python.exe"

if not exist "%PYTHON_CMD%" (
  echo [ERROR] No project venv found at:
  echo   %PROJECT_ROOT%\.venv\Scripts\python.exe
  echo   %PROJECT_ROOT%\venv\Scripts\python.exe
  echo Create one and install deps, e.g.:
  echo   python -m venv .venv
  echo   .venv\Scripts\pip install -r mcp_server\requirements.txt
  exit /b 1
)

echo Project Root: %PROJECT_ROOT%
echo Using Python: %PYTHON_CMD%
echo.

rem --- Optional: ensure uvicorn is present in THIS venv ---
"%PYTHON_CMD%" -m uvicorn --version >nul 2>nul || (
  echo Installing uvicorn into project venv...
  "%PYTHON_CMD%" -m pip install -q --upgrade pip
  "%PYTHON_CMD%" -m pip install -q "uvicorn[standard]" fastapi
)

rem --- Start the server from the project root (so mcp_server package is in sys.path) ---
pushd "%PROJECT_ROOT%"
echo Starting MCP server on 0.0.0.0:8000 ...
echo (Ctrl+C to stop)
echo ========================================
"%PYTHON_CMD%" -m uvicorn mcp_server.server:app --host 0.0.0.0 --port 8000 --reload --log-level debug
set "EC=%ERRORLEVEL%"

REM --- Optional: Print a quick Scout summary if health endpoint is reachable ---
for /f "usebackq tokens=2 delims=:, }" %%A in (`"powershell -NoLogo -NoProfile -Command ^
  try { $resp = Invoke-WebRequest -Uri http://127.0.0.1:8000/health -UseBasicParsing -TimeoutSec 3; ^
        $json = $resp.Content | ConvertFrom-Json; ^
        $tables = $json.catalog.tables_count; ^
        $age = [math]::Round($json.catalog.catalog_age_s, 1); ^
        \"tables=:$tables, age_s=:$age\" ^
      } catch { \"tables=:n/a, age_s=:n/a\" }"`) do (
  echo Scout Catalog: %%A
)

popd

exit /b %EC%
