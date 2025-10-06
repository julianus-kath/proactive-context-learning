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

rem --- Start the server from the correct working directory ---
pushd "%PROJECT_ROOT%\mcp_server"
echo Starting MCP server on 0.0.0.0:8000 ...
echo (Ctrl+C to stop)
echo ========================================
"%PYTHON_CMD%" -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload --log-level debug
set "EC=%ERRORLEVEL%"
popd

exit /b %EC%
