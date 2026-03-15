@echo off
setlocal EnableExtensions

rem -----------------------------------------------------------------------------
rem H2b Overnight Runner (Windows, no PowerShell script dependency)
rem Usage:
rem   eval\scripts\run_h2b_overnight_windows.bat
rem   eval\scripts\run_h2b_overnight_windows.bat --setup-only --dry-run
rem -----------------------------------------------------------------------------

rem Resolve project root from eval/scripts/
pushd "%~dp0\..\.."
set "PROJECT_ROOT=%CD%"
popd

rem Choose Python interpreter (prefer local venvs)
set "PYTHON_CMD=%PROJECT_ROOT%\.venv1\Scripts\python.exe"
if not exist "%PYTHON_CMD%" set "PYTHON_CMD=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_CMD%" set "PYTHON_CMD=%PROJECT_ROOT%\venv\Scripts\python.exe"
if not exist "%PYTHON_CMD%" set "PYTHON_CMD=python"

rem Load minimal keys from .env only if not already defined in current shell
set "ENV_FILE=%PROJECT_ROOT%\.env"
if exist "%ENV_FILE%" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
    if /I "%%A"=="API_KEY" if not defined API_KEY set "API_KEY=%%B"
    if /I "%%A"=="MCP_API_KEY" if not defined MCP_API_KEY set "MCP_API_KEY=%%B"
    if /I "%%A"=="OPENAI_API_KEY" if not defined OPENAI_API_KEY set "OPENAI_API_KEY=%%B"
  )
)

if not defined API_KEY (
  set "API_KEY=supersecretapikey"
  echo [warn] API_KEY missing; using fallback default.
)
if not defined MCP_API_KEY set "MCP_API_KEY=%API_KEY%"

rem Defaults (override via env vars if needed)
if not defined H2B_DATASET set "H2B_DATASET=eval/datasets/cockpit_partner_queries_v1.jsonl"
if not defined H2B_TABLE_LABELS set "H2B_TABLE_LABELS=eval/datasets/cockpit_partner_table_labels_v1.json"
if not defined H2B_TARGET set "H2B_TARGET=http://127.0.0.1:5001"
if not defined H2B_MCP_URL set "H2B_MCP_URL=http://127.0.0.1:8000"
if not defined H2B_REPLICATES set "H2B_REPLICATES=1"
if not defined H2B_RUN_TAG set "H2B_RUN_TAG=h2b_overnight"

pushd "%PROJECT_ROOT%"

echo.
echo ===============================================================
echo   H2b Overnight /process_query Grounding Runner
echo ===============================================================
echo Project root: %PROJECT_ROOT%
echo Python:       %PYTHON_CMD%
echo Target:       %H2B_TARGET%
echo MCP URL:      %H2B_MCP_URL%
echo Replicates:   %H2B_REPLICATES%
echo Run tag:      %H2B_RUN_TAG%
echo.

if /I "%H2B_SKIP_PIP_INSTALL%"=="1" (
  echo [setup] Skipping pip install because H2B_SKIP_PIP_INSTALL=1
) else (
  echo [setup] Installing/updating Python dependencies...
  "%PYTHON_CMD%" -m pip install --upgrade pip
  if errorlevel 1 (
    echo [ERROR] pip upgrade failed.
    popd
    exit /b 1
  )
  "%PYTHON_CMD%" -m pip install -r requirements.txt -r simple_sql_agent\requirements.txt -r mcp_server\requirements.txt
  if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    popd
    exit /b 1
  )
  "%PYTHON_CMD%" -m pip install --upgrade httpx
  if errorlevel 1 (
    echo [ERROR] Explicit httpx install failed.
    popd
    exit /b 1
  )
  "%PYTHON_CMD%" -c "import httpx; print('httpx_ok', httpx.__version__)"
  if errorlevel 1 (
    echo [ERROR] httpx import test failed for interpreter: %PYTHON_CMD%
    popd
    exit /b 1
  )
)

echo [run] Starting orchestrator...
echo.
"%PYTHON_CMD%" -m eval.run_h2b_process_query_grounding ^
  --dataset "%H2B_DATASET%" ^
  --table-labels "%H2B_TABLE_LABELS%" ^
  --target "%H2B_TARGET%" ^
  --mcp-url "%H2B_MCP_URL%" ^
  --api-key "%API_KEY%" ^
  --mcp-api-key "%MCP_API_KEY%" ^
  --start-services-per-mode ^
  --replicates %H2B_REPLICATES% ^
  --run-tag "%H2B_RUN_TAG%" ^
  %*

set "EC=%ERRORLEVEL%"
echo.
if "%EC%"=="0" (
  echo [done] H2b orchestrator completed successfully.
) else (
  echo [fail] H2b orchestrator failed with exit code %EC%.
)

popd
exit /b %EC%
