@echo off
setlocal EnableExtensions

echo.
echo ================================================
echo   MCP Server Startup (Windows/VPN)
echo   Phase 7: Multi-Agent Orchestrator Ready
echo ================================================
echo.
echo System Architecture:
echo   [macOS LangGraph + Multi-Agent Orchestrator]
echo   [4 Specialized Agents ^| Discovery ^| Join/SQL ^| Exec ^| Answer]
echo   ════════════════════════════════════════
echo   [MCP Server (Windows/VPN) ^| Scout Catalog]
echo   ════════════════════════════════════════
echo   [MSSQL ERP Database]
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

rem --- Force fresh catalog rebuild by deleting old catalog ---
echo.
echo ================================================
echo   🔄 Forcing Fresh Catalog Rebuild
echo ================================================
echo.
if exist "%PROJECT_ROOT%\data\catalog\catalog.json.gz" (
  echo   📦 Found old catalog, deleting...
  del /q "%PROJECT_ROOT%\data\catalog\catalog.json.gz" 2>nul
  echo   ✅ Old catalog deleted - will rebuild with accurate row counts
) else (
  echo   ℹ️  No old catalog found - will build fresh catalog
)
echo.
echo   Why force rebuild?
echo     • Consolidated ScoutRunner with semantic search
echo     • Accurate row counts from sys.dm_db_partition_stats
echo     • Intent-aware ranking (customer/product/revenue)
echo     • Archive table penalties + master table boosts
echo.
echo   ⏳ Catalog build will take 30-60 seconds on first startup...
echo.

rem --- Start the server from the project root (so mcp_server package is in sys.path) ---
pushd "%PROJECT_ROOT%"
echo.
echo ================================================
echo   🚀 Starting MCP Server on 0.0.0.0:8000
echo ================================================
echo.
echo   NEW Features (Consolidated Scout):
echo     ✅ Scout Catalog with Semantic Search
echo     ✅ Accurate Row Counts (not 0!)
echo     ✅ Intent-Aware Ranking (archive penalties)
echo     ✅ Customer Master Boost (KHKAdressen priority)
echo     ✅ Fuzzy Matching (German compound words)
echo     ✅ Safe Query Execution (read-only, timeouts)
echo     ✅ Multi-Agent Ready (for macOS LangGraph)
echo.
echo   (Ctrl+C to stop)
echo ================================================
echo.
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
