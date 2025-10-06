@echo off
REM =============================================================================
REM Windows MCP Server Startup Script
REM =============================================================================
REM This script starts the MCP server on Windows with VPN access to SQL Server.
REM The MCP server provides database access to the Mac machine over the network.
REM =============================================================================

echo.
echo ========================================
echo   MCP Server Startup (Windows)
echo ========================================
echo.

REM Get the project root directory (parent of vpn_config)
cd /d "%~dp0\.."
set PROJECT_ROOT=%CD%

echo Project Root: %PROJECT_ROOT%
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.11+ and add it to PATH
    pause
    exit /b 1
)

echo [OK] Python is installed
echo.

REM Check if .env file exists
if not exist "%PROJECT_ROOT%\.env" (
    echo [WARNING] .env file not found
    echo.
    echo Please create .env file from .env.windows template:
    echo   1. Copy .env.windows to .env
    echo   2. Update MSSQL_PASSWORD with your actual password
    echo   3. Update MCP_API_KEY if needed
    echo   4. Verify MSSQL_SERVER IP address
    echo.
    pause
    exit /b 1
)

echo [OK] .env file found
echo.

REM Check if ODBC Driver is installed
echo Checking for ODBC Driver 17 for SQL Server...
reg query "HKLM\SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 17 for SQL Server" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] ODBC Driver 17 for SQL Server not found
    echo.
    echo Please install ODBC Driver 17 for SQL Server:
    echo https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
    echo.
    echo Or update MSSQL_DRIVER in .env to match your installed driver
    pause
    exit /b 1
)

echo [OK] ODBC Driver 17 for SQL Server is installed
echo.

REM Install dependencies
echo Installing MCP server dependencies...
pip install -r "%PROJECT_ROOT%\mcp_server\requirements.txt" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    echo Please run manually: pip install -r mcp_server\requirements.txt
    pause
    exit /b 1
)

echo [OK] Dependencies installed
echo.

REM Check if port 8000 is already in use
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port 8000 is already in use
    echo.
    set /p KILL_PORT="Kill existing process on port 8000? (y/n): "
    if /i "%KILL_PORT%"=="y" (
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
            echo Killing process %%a...
            taskkill /F /PID %%a >nul 2>&1
        )
        timeout /t 2 /nobreak >nul
    ) else (
        echo Please stop the existing process manually
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo   Starting MCP Server on port 8000
echo ========================================
echo.
echo The MCP server will:
echo   - Connect to SQL Server via VPN
echo   - Listen on 0.0.0.0:8000 (accessible from Mac)
echo   - Provide database access via MCP JSON-RPC
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the MCP server
cd "%PROJECT_ROOT%\mcp_server"
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload

pause