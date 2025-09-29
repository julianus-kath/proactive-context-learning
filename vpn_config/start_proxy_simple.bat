@echo off
echo ================================================
echo SQL Proxy - Simple Development Setup
echo ================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found! Please install Python first.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python found
echo.

REM Set development mode to skip security requirements
set PROXY_DEVELOPMENT_MODE=true
echo ✅ Development mode enabled - no certificates or API keys required

REM Optional: Uncomment and set your actual password
REM set SQLSERVER_PASSWORD=your_actual_password

echo.
echo Installing required Python packages...
echo ------------------------------------------------

REM Install required packages
pip install flask pyodbc pyyaml flask-limiter --quiet
if errorlevel 1 (
    echo ❌ Failed to install required packages
    pause
    exit /b 1
)

REM Try to install PostgreSQL support (optional)
pip install psycopg2-binary --quiet
if errorlevel 1 (
    echo ⚠️  PostgreSQL support not installed (optional)
) else (
    echo ✅ PostgreSQL support installed
)

echo ✅ All packages installed
echo.

REM Check if connections.yaml exists
if not exist "connections.yaml" (
    echo ❌ connections.yaml not found!
    echo Please make sure you're in the correct directory.
    pause
    exit /b 1
)

echo ✅ Configuration file found
echo.

echo Starting proxy server...
echo ------------------------------------------------
echo Access URLs:
echo   Health check: http://localhost:5000/health
echo   Diagnostics:  http://localhost:5000/diag
echo.
echo Press Ctrl+C to stop the server
echo ================================================

python proxy.py

echo.
echo Server stopped.
pause