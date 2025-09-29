# PowerShell script to set up and run the enhanced proxy.py on Windows
# Run this script from PowerShell as Administrator if needed

Write-Host "Setting up Enhanced SQL Proxy with HTTPS and API Key Auth" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

# Step 1: Generate self-signed certificates
Write-Host "`n1. Generating self-signed TLS certificates..." -ForegroundColor Yellow

$certDir = "C:\temp\sqlproxy"
if (!(Test-Path $certDir)) {
    New-Item -ItemType Directory -Path $certDir -Force
    Write-Host "Created directory: $certDir" -ForegroundColor Green
}

Set-Location $certDir

# Generate certificate using OpenSSL (requires Git Bash or OpenSSL installation)
Write-Host "Generating certificate and key files..." -ForegroundColor Yellow
$opensslCmd = 'openssl req -x509 -newkey rsa:4096 -keyout proxy.key -out proxy.crt -days 365 -nodes -subj "/CN=proxy.local"'

try {
    # Try to run OpenSSL command
    cmd /c $opensslCmd
    if (Test-Path "proxy.crt" -and Test-Path "proxy.key") {
        Write-Host "✓ Certificate files generated successfully" -ForegroundColor Green
    } else {
        throw "Certificate files not found after generation"
    }
} catch {
    Write-Host "✗ Failed to generate certificates with OpenSSL" -ForegroundColor Red
    Write-Host "Please install OpenSSL or Git Bash and run:" -ForegroundColor Yellow
    Write-Host $opensslCmd -ForegroundColor Cyan
    Write-Host "Then run this script again." -ForegroundColor Yellow
    exit 1
}

# Step 2: Set environment variables
Write-Host "`n2. Setting environment variables..." -ForegroundColor Yellow

# Proxy configuration
$env:PROXY_BIND_HOST = "0.0.0.0"
$env:PROXY_PORT = "5000"
$env:PROXY_API_KEY = "secure-api-key-$(Get-Random)"
$env:PROXY_TLS_CERT_FILE = "$certDir\proxy.crt"
$env:PROXY_TLS_KEY_FILE = "$certDir\proxy.key"

# Database configuration (update these for your environment)
$env:SQLSERVER_PASSWORD = '%Si!Mon!Ma1'
$env:PG_PASSWORD = 'your-postgres-password'

Write-Host "✓ Environment variables set:" -ForegroundColor Green
Write-Host "  PROXY_API_KEY: $env:PROXY_API_KEY" -ForegroundColor Cyan
Write-Host "  PROXY_TLS_CERT_FILE: $env:PROXY_TLS_CERT_FILE" -ForegroundColor Cyan
Write-Host "  PROXY_TLS_KEY_FILE: $env:PROXY_TLS_KEY_FILE" -ForegroundColor Cyan

# Copy connections.yaml if it doesn't exist
if (!(Test-Path "$certDir\connections.yaml")) {
    Write-Host "`nCopying connections.yaml template..." -ForegroundColor Yellow
    # Note: You'll need to copy connections.yaml to the same directory as proxy.py
    Write-Host "⚠️  Make sure connections.yaml is in the same directory as proxy.py" -ForegroundColor Yellow
}

# Step 3: Install Python dependencies
Write-Host "`n3. Installing Python dependencies..." -ForegroundColor Yellow
try {
    py -m pip install flask pyodbc psycopg2-binary pyyaml --quiet
    Write-Host "✓ Python dependencies installed" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to install Python dependencies" -ForegroundColor Red
    Write-Host "Please run: py -m pip install flask pyodbc psycopg2-binary pyyaml" -ForegroundColor Yellow
}

# Step 4: Display startup information
Write-Host "`n4. Ready to start proxy!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

$localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -like "10.*" -or $_.IPAddress -like "192.168.*"} | Select-Object -First 1).IPAddress

Write-Host "To start the proxy, run:" -ForegroundColor Yellow
Write-Host "python $certDir\proxy.py" -ForegroundColor Cyan

Write-Host "`nFrom your Mac, test with:" -ForegroundColor Yellow
Write-Host "curl -k -H `"X-API-Key: $env:PROXY_API_KEY`" https://${localIP}:5000/health" -ForegroundColor Cyan

Write-Host "`nProxy will be available at:" -ForegroundColor Yellow
Write-Host "https://${localIP}:5000" -ForegroundColor Cyan

Write-Host "`nIMPORTANT: Save this API key for your Mac client:" -ForegroundColor Red
Write-Host "$env:PROXY_API_KEY" -ForegroundColor White -BackgroundColor Red

# Optionally start the proxy
Write-Host "`nStart the proxy now? (y/n): " -ForegroundColor Yellow -NoNewline
$response = Read-Host
if ($response -eq "y" -or $response -eq "Y") {
    Write-Host "Starting proxy..." -ForegroundColor Green
    python "$certDir\proxy.py"
}