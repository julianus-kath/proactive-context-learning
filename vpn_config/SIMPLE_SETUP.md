# Simple SQL Proxy Setup (No Admin Required)

This is a simplified setup that bypasses the complex security requirements for development/testing.

## Quick Start (Windows)

1. **Double-click** `start_proxy_simple.bat`
   - This will install dependencies and start the proxy in development mode
   - No certificates, API keys, or admin privileges required

2. **Test the proxy:**
   ```
   http://localhost:5000/health
   ```

## Alternative: Command Line Setup

If the batch file doesn't work, follow these manual steps:

## Manual Setup (if batch file doesn't work)

1. **Install Python packages:**
   ```cmd
   pip install flask pyodbc pyyaml flask-limiter
   pip install psycopg2-binary
   ```

2. **Set development mode:**
   ```cmd
   set PROXY_DEVELOPMENT_MODE=true
   ```

3. **Set your database password (optional):**
   ```cmd
   set SQLSERVER_PASSWORD=your_actual_password
   ```

4. **Start the proxy:**
   ```cmd
   python proxy.py
   ```

## What's Different in Development Mode

- ✅ **No TLS certificates required** - runs on HTTP instead of HTTPS
- ✅ **No API key required** - authentication is disabled
- ✅ **No admin privileges needed** - just install Python packages
- ✅ **Password can be hardcoded** - fallback in connections.yaml

## Testing the Proxy

### 1. Health Check
```bash
curl http://localhost:5000/health
```

### 2. Test Query (if database is accessible)
```bash
curl -H "Content-Type: application/json" \
  -d '{"conn":"corp_sql_erp","sql":"SELECT 1 as test","limit":10}' \
  http://localhost:5000/query
```

### 3. Diagnostic Info
```bash
curl http://localhost:5000/diag
```

## Configuration

Edit `connections.yaml` to match your database settings:

```yaml
connections:
  corp_sql_erp:
    type: mssql
    host: "192.168.200.16"  # Your SQL Server IP
    port: 1433
    database: "master"
    user: "SimonM"
    password: "your_actual_password"  # Can hardcode for testing
    encrypt: true
    trust_server_certificate: true
```

## Security Notes

⚠️ **This is for development only!**
- No encryption (HTTP instead of HTTPS)
- No authentication (anyone can access)
- Passwords may be visible in config files

For production, use the full setup with certificates and API keys.

## Troubleshooting

1. **"No module named 'flask'"**
   - Run: `pip install flask pyodbc pyyaml flask-limiter`

2. **"connections.yaml not found"**
   - Make sure you're in the same directory as proxy.py

3. **Database connection errors**
   - Check your database IP, username, and password in connections.yaml
   - Make sure SQL Server is accessible from your Windows laptop

4. **"No suitable SQL Server ODBC driver found"**
   - Install ODBC Driver for SQL Server from Microsoft's website