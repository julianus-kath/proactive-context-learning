@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo.
echo ========================================
echo   MCP Server Startup (Windows)
echo ========================================
echo.

rem ---- Determine project root ----
cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%CD%"
echo Project Root: %PROJECT_ROOT%
echo.

rem ---- Choose Python interpreter ----
set "PYTHON_CMD="

if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" set "PYTHON_CMD=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" set "PYTHON_CMD=%PROJECT_ROOT%\venv\Scripts\python.exe"
if not defined PYTHON_CMD where py >nul 2>nul && set "PYTHON_CMD=py -3.11"
if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    echo [ERROR] No Python found (.venv, py -3.11, or python).
    pause
    exit /b 1
)

echo Using Python: %PYTHON_CMD%
%PYTHON_CMD% --version || (
    echo [ERROR] Python is not runnable.
    pause
    exit /b 1
)

rem ---- Ensure required packages ----
echo Checking uvicorn installation...
%PYTHON_CMD% -m uvicorn --version >nul 2>nul || (
    echo Installing required packages...
    %PYTHON_CMD% -m pip install --quiet --upgrade pip
    %PYTHON_CMD% -m pip install --quiet "uvicorn[standard]" fastapi
)

rem ---- Launch server ----
cd "%PROJECT_ROOT%\mcp_server" || (
    echo [ERROR] mcp_server folder not found.
    pause
    exit /b 1
)

echo Starting MCP server on 0.0.0.0:8000 ...
echo (Press Ctrl+C to stop)
echo ========================================
%PYTHON_CMD% -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload --log-level debug

set "EC=%ERRORLEVEL%"
echo.
if not "%EC%"=="0" (
    echo [ERROR] Uvicorn exited with code %EC%.
    echo - Check for missing imports or occupied port.
)
pause
exit /b %EC%
