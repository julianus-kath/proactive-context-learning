@echo off
setlocal EnableExtensions EnableDelayedExpansion

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

rem --- Check catalog TTL and ask user about rebuild ---
echo.
echo ================================================
echo   📊 Checking Catalog Status
echo ================================================
echo.

set "CATALOG_FILE=%PROJECT_ROOT%\data\catalog\catalog.json.gz"
set "METADATA_FILE=%PROJECT_ROOT%\data\catalog\metadata.json"
set "TTL_THRESHOLD=3600"

if exist "%CATALOG_FILE%" (
  if exist "%METADATA_FILE%" (
    echo   📦 Found existing catalog and metadata files

    rem --- Extract catalog age using PowerShell ---
    for /f "usebackq tokens=2 delims=:,}" %%A in (`"powershell -NoLogo -NoProfile -Command ^
      try { ^
        $metadata = Get-Content '%METADATA_FILE%' | ConvertFrom-Json; ^
        $timestamp = [DateTime]::Parse($metadata.timestamp); ^
        $ageSeconds = ([DateTime]::UtcNow - $timestamp).TotalSeconds; ^
        $ttlHours = $metadata.ttl_hours; ^
        $ttlSeconds = $ttlHours * 3600; ^
        \"age_seconds=:$ageSeconds, ttl_seconds=:$ttlSeconds\" ^
      } catch { \"age_seconds=:error, ttl_seconds=:error\" }"`) do (
      set "CATALOG_INFO=%%A"
    )

    rem --- Parse the results ---
    for /f "tokens=1,2 delims=," %%i in ("%CATALOG_INFO%") do (
      set "AGE_SECONDS=%%i"
      set "TTL_SECONDS=%%j"
    )

    set "AGE_SECONDS=%AGE_SECONDS:age_seconds=:%"
    set "TTL_SECONDS=%TTL_SECONDS:ttl_seconds=:%"

    if "%AGE_SECONDS%"=="error" (
      echo   ⚠️  Could not read catalog metadata
      echo   🔄 Will rebuild catalog to be safe
      del /q "%CATALOG_FILE%" 2>nul
      del /q "%METADATA_FILE%" 2>nul
      echo   ✅ Old catalog deleted - will rebuild
      goto :rebuild_info
    )

    rem --- Calculate remaining TTL ---
    set /a "REMAINING_TTL=%TTL_SECONDS%-%AGE_SECONDS%"

    echo   📊 Catalog Age: %AGE_SECONDS% seconds
    echo   🎯 TTL Threshold: %TTL_THRESHOLD% seconds
    echo   ⏰ Remaining TTL: %REMAINING_TTL% seconds

    if %AGE_SECONDS% GEQ %TTL_THRESHOLD% (
      echo.
      echo   ⚠️  Catalog is older than TTL threshold (%TTL_THRESHOLD% seconds)
      echo.
      set /p "REBUILD_CHOICE=Press Y to rebuild catalog or N to continue with cached catalog [Y/N]: "

      if /i "!REBUILD_CHOICE!"=="Y" (
        echo.
        echo   🔄 Rebuilding catalog as requested...
        del /q "%CATALOG_FILE%" 2>nul
        del /q "%METADATA_FILE%" 2>nul
        echo   ✅ Old catalog deleted - will rebuild
      ) else (
        echo.
        echo   📦 Keeping existing catalog as requested
        echo   ℹ️  Note: Using cached catalog may have outdated schema information
      )
    ) else (
      echo.
      echo   ✅ Catalog is fresh (under %TTL_THRESHOLD% seconds old)
      echo   📦 Will use existing catalog
    )
  ) else (
    echo   ⚠️  Found catalog file but no metadata - catalog may be corrupted
    del /q "%CATALOG_FILE%" 2>nul
    echo   🔄 Will rebuild catalog
  )
) else (
  echo   ℹ️  No existing catalog found - will build fresh catalog
)

:rebuild_info
echo.
echo   Why rebuild catalog?
echo     • Ensures schema is up-to-date with database changes
echo     • Fixes any catalog corruption or format issues
echo     • Updates table/view counts and metadata
echo.
echo   ⏳ Catalog build will take 30-60 seconds...
echo.

rem --- Start the server from the project root (so mcp_server package is in sys.path) ---
pushd "%PROJECT_ROOT%"
echo.
echo ================================================
echo   🚀 Starting MCP Server on 0.0.0.0:8000
echo ================================================
echo.
echo   INTERACTIVE CATALOG MANAGEMENT:
echo     ✅ Smart TTL checking with user prompts
echo     ✅ Choose to rebuild or use cached catalogs
echo     ✅ Automatic rebuild for expired catalogs
echo.
echo   SCOUT FEATURES (Consolidated):
echo     ✅ Semantic Search with Intent-Awareness
echo     ✅ Table Ranking (business vs archive tables)
echo     ✅ Customer/Product Master Table Priority
echo     ✅ Fuzzy Matching (German compound words)
echo     ✅ Safe Query Execution (timeouts, limits)
echo     ✅ Multi-Agent Ready (macOS LangGraph integration)
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
