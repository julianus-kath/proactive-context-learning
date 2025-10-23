# ============================================================================
# MCP Server Startup Script (PowerShell)
# Windows/VPN - Multi-Agent Orchestrator Ready (Phase 7)
# ============================================================================
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File start_mcp_server_windows.ps1
#
# Or set execution policy:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#   .\start_mcp_server_windows.ps1
#

param(
    [switch]$NoReload = $false,
    [string]$LogLevel = "debug"
)

# Colors for output
$Colors = @{
    Green = "Green"
    Red = "Red"
    Yellow = "Yellow"
    Blue = "Cyan"
    NC = "White"
}

function Write-Status {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

Write-Host ""
Write-Status "================================================" $Colors.Blue
Write-Status "   MCP Server Startup (PowerShell/Windows)" $Colors.Blue
Write-Status "   Phase 7: Multi-Agent Orchestrator Ready" $Colors.Blue
Write-Status "================================================" $Colors.Blue
Write-Host ""

Write-Status "System Architecture:" $Colors.Blue
Write-Status "  [macOS LangGraph + Multi-Agent Orchestrator]" $Colors.NC
Write-Status "  [4 Specialized Agents | Discovery | Join/SQL | Exec | Answer]" $Colors.NC
Write-Status "  ═══════════════════════════════════════════════════════════" $Colors.NC
Write-Status "  [MCP Server (Windows/VPN) | Scout Catalog]" $Colors.NC
Write-Status "  ═══════════════════════════════════════════════════════════" $Colors.NC
Write-Status "  [MSSQL ERP Database]" $Colors.NC
Write-Host ""

# Resolve project root
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_ROOT = Split-Path -Parent $SCRIPT_DIR

Write-Status "Project Root: $PROJECT_ROOT" $Colors.NC

# Find Python executable in venv
$PYTHON_PATHS = @(
    "$PROJECT_ROOT\.venv\Scripts\python.exe",
    "$PROJECT_ROOT\venv\Scripts\python.exe",
    (Get-Command python.exe -ErrorAction SilentlyContinue).Source
)

$PYTHON_CMD = $null
foreach ($path in $PYTHON_PATHS) {
    if ($path -and (Test-Path $path)) {
        $PYTHON_CMD = $path
        break
    }
}

if (-not $PYTHON_CMD) {
    Write-Status "ERROR: Python not found in project venv" $Colors.Red
    Write-Status "Create virtual environment and install dependencies:" $Colors.Yellow
    Write-Status "  python -m venv .venv" $Colors.Yellow
    Write-Status "  .venv\Scripts\pip install -r mcp_server\requirements.txt" $Colors.Yellow
    exit 1
}

Write-Status "✅ Using Python: $PYTHON_CMD" $Colors.Green

# Optional: ensure uvicorn is installed
Write-Status "Checking dependencies..." $Colors.Yellow
& $PYTHON_CMD -m uvicorn --version 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Status "Installing uvicorn and fastapi..." $Colors.Yellow
    & $PYTHON_CMD -m pip install -q --upgrade pip
    & $PYTHON_CMD -m pip install -q "uvicorn[standard]" fastapi
}

# Build the uvicorn command
$UVICORN_ARGS = @(
    "mcp_server.server:app",
    "--host", "0.0.0.0",
    "--port", "8000",
    "--log-level", $LogLevel
)

if (-not $NoReload) {
    $UVICORN_ARGS += "--reload"
}

Write-Host ""
Write-Status "================================================" $Colors.Blue
Write-Status "   🚀 Starting MCP Server on 0.0.0.0:8000" $Colors.Blue
Write-Status "================================================" $Colors.Blue
Write-Host ""

Write-Status "Features:" $Colors.Blue
Write-Status "  ✅ Scout Catalog (tables + views)" $Colors.Green
Write-Status "  ✅ Discovery Tools (search, describe, list)" $Colors.Green
Write-Status "  ✅ Hybrid Ranking (text + role coverage)" $Colors.Green
Write-Status "  ✅ Safe Query Execution (read-only, timeouts)" $Colors.Green
Write-Status "  ✅ Multi-Agent Ready (for macOS LangGraph)" $Colors.Green
Write-Host ""

Write-Status "(Ctrl+C to stop)" $Colors.Yellow
Write-Status "================================================" $Colors.Blue
Write-Host ""

# Change to project root and start server
Push-Location $PROJECT_ROOT
try {
    & $PYTHON_CMD -m uvicorn @UVICORN_ARGS
}
finally {
    Pop-Location
}