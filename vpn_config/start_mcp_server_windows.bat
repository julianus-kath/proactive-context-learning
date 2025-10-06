@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo.
echo ========================================
echo   MCP Server Startup (Windows)
echo ========================================
echo.

REM Go to project root (parent of this script folder)
cd /d "%~dp0\.."
set "PROJECT_ROOT=%CD%"
echo Project Root: %PROJECT_ROOT%
echo.

REM --- Resolve a Python command ---
set "PYTHON_CMD="

REM 1) Prefer project venv if it exists
if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
  set "PYTHON_CMD=%PROJECT_ROOT%\venv\Scripts\python.exe"
)

REM 2) Try the Windows py launcher (3.11)
if not defined PYTHON_CMD (
  where py >nul 2>nul && set "PYTHON_CMD=py -3.11"
)

REM 3) Fall back to python on PATH
if not defined PYTHON_CMD (
  where python >nul 2>nul && set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
  echo [ERROR] No Python found.
  echo Tried: venv\Scripts\python.exe, py -3.11, and python on PATH.
  echo Install Python 3.11+ OR create a venv: python -m venv venv
  exit /b 1
)

echo Using Python: %PYTHON_CMD%
%PYTHON_CMD% --version || (
  echo [ERROR] Python command failed: %PYTHON_CMD%
  exit /b 1
)
echo.

REM --- Optional: install deps (uncomment if needed) ---
REM %PYTHON_CMD% -m pip install -r "%PROJECT_ROOT%\mcp_server\requirements.txt" || exit /b 1

REM --- Start the server ---
cd "%PROJECT_ROOT%\mcp_server"
echo Starting MCP server on 0.0.0.0:8000 ...
%PYTHON_CMD% -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload

endlocal
