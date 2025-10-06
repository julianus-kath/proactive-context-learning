@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo.
echo ========================================
echo   MCP Server Startup (Windows)
echo ========================================
echo.

rem --- Derive absolute project root from script path ---
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI"

echo Project Root: %PROJECT_ROOT%
echo.

rem --- Detect Python interpreter ---
set "PYTHON_CMD="

if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%PROJECT_ROOT%\.venv\Scripts\python.exe"
) else if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
    set "PYTHON_CMD=%PROJECT_ROOT%\venv\Scripts\python.exe"
) else (
    for /f "delims=" %%I in ('where py 2^>nul') do set "PYTHON_CMD=py -3.11"
    if not defined PYTHON_CMD for /f "delims=" %%I in ('where python 2^>nul') do set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo [ERROR] Kein Python gefunden (.venv, py -3.11, oder python auf PATH).
    pause
    exit /b 1
)

echo Verwende Python: %PYTHON_CMD%
%PYTHON_CMD% --version || (
    echo [ERROR] Python ist nicht lauffähig.
    pause
    exit /b 1
)

rem --- Check for uvicorn ---
echo Überprüfe uvicorn Installation...
%PYTHON_CMD% -m uvicorn --version >nul 2>nul
if errorlevel 1 (
    echo Installiere erforderliche Pakete...
    %PYTHON_CMD% -m pip install --quiet --upgrade pip
    %PYTHON_CMD% -m pip install --quiet "uvicorn[standard]" fastapi
)

rem --- Start server ---
if not exist "%PROJECT_ROOT%\mcp_server" (
    echo [ERROR] Ordner mcp_server nicht gefunden.
    pause
    exit /b 1
)

pushd "%PROJECT_ROOT%\mcp_server"
echo Starte MCP Server auf 0.0.0.0:8000 ...
echo (Mit Strg+C beenden)
echo ========================================

%PYTHON_CMD% -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload --log-level debug

set "EC=%ERRORLEVEL%"
popd
echo.
if not "%EC%"=="0" (
    echo [ERROR] Uvicorn ist mit Code %EC% beendet.
    echo - Prüfe Importpfade, belegte Ports oder fehlende Pakete.
)
pause
exit /b %EC%
