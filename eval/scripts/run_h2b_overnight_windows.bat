@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem -----------------------------------------------------------------------------
rem H2b Overnight Runner (Windows)
rem One-command wrapper for:
rem   - /process_query feasibility probe
rem   - partner label normalization
rem   - mode-switched runs (scout_on/off_aligned/off_legacy)
rem   - grounding evaluation + comparisons + report synthesis
rem
rem Usage:
rem   eval\scripts\run_h2b_overnight_windows.bat
rem   eval\scripts\run_h2b_overnight_windows.bat --setup-only --dry-run
rem -----------------------------------------------------------------------------

rem Resolve project root from eval/scripts/
pushd "%~dp0\..\.."
set "PROJECT_ROOT=%CD%"
popd

rem Pick Python interpreter (prefer local venvs)
set "PYTHON_CMD=%PROJECT_ROOT%\.venv1\Scripts\python.exe"
if not exist "%PYTHON_CMD%" set "PYTHON_CMD=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_CMD%" set "PYTHON_CMD=%PROJECT_ROOT%\venv\Scripts\python.exe"
if not exist "%PYTHON_CMD%" set "PYTHON_CMD=python"

rem Load secrets from .env only if not already present in shell env
set "ENV_FILE=%PROJECT_ROOT%\.env"
if not defined API_KEY call :load_env_var API_KEY
if not defined MCP_API_KEY call :load_env_var MCP_API_KEY
if not defined OPENAI_API_KEY call :load_env_var OPENAI_API_KEY

if not defined API_KEY (
  set "API_KEY=supersecretapikey"
  echo [warn] API_KEY not set in env/.env. Using fallback default.
)
if not defined MCP_API_KEY set "MCP_API_KEY=%API_KEY%"

rem Defaults (can be overridden as environment variables)
if not defined H2B_DATASET set "H2B_DATASET=eval/datasets/cockpit_partner_queries_v1.jsonl"
if not defined H2B_TABLE_LABELS set "H2B_TABLE_LABELS=eval/datasets/cockpit_partner_table_labels_v1.json"
if not defined H2B_TARGET set "H2B_TARGET=http://127.0.0.1:5001"
if not defined H2B_MCP_URL set "H2B_MCP_URL=http://127.0.0.1:8000"
if not defined H2B_REPLICATES set "H2B_REPLICATES=1"
if not defined H2B_RUN_TAG set "H2B_RUN_TAG=h2b_overnight"

set "MODE_SCRIPT=%PROJECT_ROOT%\eval\scripts\set_h2b_mode_windows.ps1"
if not exist "%MODE_SCRIPT%" (
  echo [ERROR] Missing mode script: %MODE_SCRIPT%
  exit /b 1
)

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

rem Ensure required dependency exists for eval tooling
"%PYTHON_CMD%" -c "import httpx" >nul 2>nul
if errorlevel 1 (
  echo [setup] httpx missing. Installing required dependencies...
  "%PYTHON_CMD%" -m pip install --upgrade pip
  "%PYTHON_CMD%" -m pip install -r simple_sql_agent\requirements.txt -r mcp_server\requirements.txt
  if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    popd
    exit /b 1
  )
)

set "MODE_PREP_CMD=powershell -ExecutionPolicy Bypass -File \"%MODE_SCRIPT%\" -Mode {mode} -ProjectRoot \"%PROJECT_ROOT%\" -PythonExe python -ApiKey %API_KEY% -McpApiKey %MCP_API_KEY%"

echo [run] Starting orchestrator...
echo.
"%PYTHON_CMD%" -m eval.run_h2b_process_query_grounding ^
  --dataset "%H2B_DATASET%" ^
  --table-labels "%H2B_TABLE_LABELS%" ^
  --target "%H2B_TARGET%" ^
  --mcp-url "%H2B_MCP_URL%" ^
  --api-key "%API_KEY%" ^
  --mcp-api-key "%MCP_API_KEY%" ^
  --mode-prepare-cmd "%MODE_PREP_CMD%" ^
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

:load_env_var
set "LOOKUP_KEY=%~1"
set "LOOKUP_VALUE="
if not exist "%ENV_FILE%" exit /b 0

for /f "usebackq tokens=1,* delims==" %%A in (`findstr /R /C:"^%LOOKUP_KEY%=" "%ENV_FILE%"`) do (
  set "LOOKUP_VALUE=%%B"
)

if defined LOOKUP_VALUE (
  if "!LOOKUP_VALUE:~0,1!"=="^"" (
    set "LOOKUP_VALUE=!LOOKUP_VALUE:~1,-1!"
  )
  set "%LOOKUP_KEY%=!LOOKUP_VALUE!"
)

set "LOOKUP_KEY="
set "LOOKUP_VALUE="
exit /b 0
