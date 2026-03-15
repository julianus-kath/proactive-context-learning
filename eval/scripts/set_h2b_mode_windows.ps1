param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("scout_on", "scout_off_aligned", "scout_off_legacy")]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,

    [string]$PythonExe = "python",
    [int]$McpPort = 8000,
    [int]$AgentPort = 5001,
    [string]$ApiKey = "supersecretapikey",
    [string]$McpApiKey = "supersecretapikey",
    [string]$OpenAiApiKey = "",
    [int]$HealthTimeoutSec = 120
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

switch ($Mode) {
    "scout_on" {
        $scoutDisable = "false"
        $offControlMode = ""
    }
    "scout_off_aligned" {
        $scoutDisable = "true"
        $offControlMode = "aligned_table_ranker"
    }
    "scout_off_legacy" {
        $scoutDisable = "true"
        $offControlMode = "legacy_lexical_schema_linking"
    }
}

function Stop-MatchingProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Pattern
    )

    $procs = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and $_.CommandLine -match $Pattern
    }

    foreach ($proc in $procs) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            Write-Host "[stop] Killed PID $($proc.ProcessId) ($Pattern)"
        } catch {
            Write-Host "[warn] Failed to kill PID $($proc.ProcessId): $($_.Exception.Message)"
        }
    }
}

function Wait-Health {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,

        [hashtable]$Headers = @{},

        [int]$TimeoutSec = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            if ($Headers.Count -gt 0) {
                $resp = Invoke-WebRequest -Uri $Url -Method GET -Headers $Headers -TimeoutSec 5 -UseBasicParsing
            } else {
                $resp = Invoke-WebRequest -Uri $Url -Method GET -TimeoutSec 5 -UseBasicParsing
            }
            if ($resp.StatusCode -eq 200) {
                Write-Host "[health] OK: $Url"
                return
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "Health check timeout for $Url"
}

if (-not (Test-Path $ProjectRoot)) {
    throw "Project root does not exist: $ProjectRoot"
}

$logDir = Join-Path $ProjectRoot "eval\runs\windows_service_logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"

Write-Host "[mode] $Mode"
Write-Host "[mode] SCOUT_DISABLE=$scoutDisable"
if ($offControlMode) {
    Write-Host "[mode] SCOUT_OFF_CONTROL_MODE=$offControlMode"
} else {
    Write-Host "[mode] SCOUT_OFF_CONTROL_MODE=<unset>"
}

Stop-MatchingProcess -Pattern "mcp_server\.server\.app"
Stop-MatchingProcess -Pattern "simple_sql_agent\.service:app"
Stop-MatchingProcess -Pattern "uvicorn.*simple_sql_agent\.service:app"
Start-Sleep -Seconds 2

$env:SCOUT_DISABLE = $scoutDisable
if ($offControlMode) {
    $env:SCOUT_OFF_CONTROL_MODE = $offControlMode
} else {
    Remove-Item Env:SCOUT_OFF_CONTROL_MODE -ErrorAction SilentlyContinue
}
$env:MCP_PORT = "$McpPort"
$env:PORT = "$AgentPort"
$env:MCP_API_KEY = $McpApiKey
$env:MCP_SERVER_URL = "http://127.0.0.1:$McpPort"
$env:API_KEY = $ApiKey
if ($OpenAiApiKey) {
    $env:OPENAI_API_KEY = $OpenAiApiKey
}

$mcpLog = Join-Path $logDir "${ts}_${Mode}_mcp.log"
$agentLog = Join-Path $logDir "${ts}_${Mode}_agent.log"

$mcpArgs = @("-m", "mcp_server.server.app")
$agentArgs = @(
    "-m", "uvicorn", "simple_sql_agent.service:app",
    "--host", "0.0.0.0",
    "--port", "$AgentPort"
)

$mcpProc = Start-Process -FilePath $PythonExe -ArgumentList $mcpArgs -WorkingDirectory $ProjectRoot -PassThru -NoNewWindow -RedirectStandardOutput $mcpLog -RedirectStandardError $mcpLog
$agentProc = Start-Process -FilePath $PythonExe -ArgumentList $agentArgs -WorkingDirectory $ProjectRoot -PassThru -NoNewWindow -RedirectStandardOutput $agentLog -RedirectStandardError $agentLog

Write-Host "[start] MCP PID: $($mcpProc.Id)"
Write-Host "[start] Agent PID: $($agentProc.Id)"

Wait-Health -Url "http://127.0.0.1:$McpPort/health" -Headers @{ "X-API-Key" = $McpApiKey } -TimeoutSec $HealthTimeoutSec
Wait-Health -Url "http://127.0.0.1:$AgentPort/health" -TimeoutSec $HealthTimeoutSec

Write-Host "[ready] Mode '$Mode' is active."
Write-Host "[logs] MCP: $mcpLog"
Write-Host "[logs] Agent: $agentLog"
