# Enhanced SQL Proxy with Multi-Database Support

This proxy provides secure HTTPS access to multiple database backends from your Mac development environment through a Windows laptop connected to VPN.

## Features

- **HTTPS with API Key Authentication**: Secure encrypted communication
- **Multi-Database Support**: Connect to MSSQL and PostgreSQL databases
- **YAML Configuration**: Flexible database connection management
- **Environment Variable Expansion**: Secure credential handling
- **JSON-Only API**: Consistent POST request/response format
- **Parameterized Queries**: Safe parameter binding to prevent SQL injection
- **Server-Side Limits**: Automatic TOP/LIMIT clause injection
- **Query Timeouts**: Configurable per-query timeout protection
- **Read-Only Guards**: Enhanced validation against write operations
- **Read-Only Transactions**: Wrapped in read-only transactions where supported

## Files

- `proxy.py` - Main proxy server
- `connections.yaml` - Database connection configuration
- `setup_proxy_windows.ps1` - Windows setup script
- `test_proxy_auth.py` - Authentication test script
- `test_yaml_config.py` - Configuration validation script
- `test_query_post.py` - POST /query endpoint test script

## Setup Instructions

### 1. Windows Laptop (VPN Connected)

1. **Run the setup script:**
   ```powershell
   .\setup_proxy_windows.ps1
   ```

2. **Or manual setup:**
   ```powershell
   # Generate certificates
   openssl req -x509 -newkey rsa:4096 -keyout proxy.key -out proxy.crt -days 365 -nodes -subj "/CN=proxy.local"
   
   # Install dependencies
   py -m pip install flask pyodbc psycopg2-binary pyyaml
   
   # Set environment variables
   $env:PROXY_API_KEY = "your-secure-api-key"
   $env:PROXY_TLS_CERT_FILE = "C:\temp\sqlproxy\proxy.crt"
   $env:PROXY_TLS_KEY_FILE = "C:\temp\sqlproxy\proxy.key"
   $env:SQLSERVER_PASSWORD = "your-sql-password"
   $env:PG_PASSWORD = "your-postgres-password"
   
   # Copy connections.yaml to the same directory as proxy.py
   # Edit connections.yaml to match your database configurations
   
   # Start the proxy
   python proxy.py
   ```

### 2. Configuration (connections.yaml)

Edit `connections.yaml` to configure your database connections:

```yaml
connections:
  corp_sql_erp:
    type: mssql
    driver: "ODBC Driver 18 for SQL Server"
    host: "<YOUR_MSSQL_HOST_IP>"
    port: 1433
    database: "master"
    user: "<YOUR_SQL_USER>"
    password: "${SQLSERVER_PASSWORD}"
    encrypt: true
    trust_server_certificate: true
  
  local_postgres:
    type: postgres
    host: "127.0.0.1"
    port: 5432
    database: "mydb"
    user: "postgres"
    password: "${PG_PASSWORD}"
    sslmode: "require"
```

### 3. Environment Variables

Required environment variables:

- `PROXY_API_KEY` - API key for authentication
- `PROXY_TLS_CERT_FILE` - Path to TLS certificate file
- `PROXY_TLS_KEY_FILE` - Path to TLS private key file
- `SQLSERVER_PASSWORD` - SQL Server password (referenced in YAML)
- `PG_PASSWORD` - PostgreSQL password (referenced in YAML)

Optional:
- `PROXY_BIND_HOST` - Host to bind to (default: "0.0.0.0")
- `PROXY_PORT` - Port to listen on (default: 5000)

## API Endpoints

### GET /health
Returns proxy status and available connections.

**Authentication:** None required

**Response:**
```json
{
  "status": "ok",
  "connections": ["corp_sql_erp", "local_postgres"]
}
```

### GET /diag
Get diagnostic information for debugging without exposing secrets.

**Authentication:** Required (`X-API-Key` header)

**Response:**
```json
{
  "version": {
    "proxy": "1.3.0",
    "python": "3.11.2"
  },
  "connections": [
    {"name": "corp_sql_erp", "type": "mssql"},
    {"name": "analytics_pg", "type": "postgres"}
  ],
  "drivers": {
    "mssql": ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"],
    "postgres": "Available"
  }
}
```

**Example:**
```bash
curl -k -H "X-API-Key: your-api-key" \
  https://10.255.152.48:5000/diag
```

### POST /query
Execute SELECT queries with JSON request/response format. Supports parameterized queries, server-side limits, and timeouts.

**Authentication:** Required (`X-API-Key` header)

**Content-Type:** `application/json`

**Request Body:**
```json
{
  "conn": "corp_sql_erp",
  "sql": "SELECT name FROM sys.databases WHERE name LIKE ?",
  "params": ["%master%"],
  "limit": 1000,
  "timeout_s": 30
}
```

**Request Fields:**
- `conn` (required) - Database connection name from connections.yaml
- `sql` (required) - SQL SELECT query to execute
- `params` (optional) - Array of parameters for parameterized queries
- `limit` (optional) - Maximum rows to return (default: 1000, max: 10000)
- `timeout_s` (optional) - Query timeout in seconds (default: 30, max: 300)

**Example:**
```bash
curl -k -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"conn":"corp_sql_erp","sql":"SELECT name FROM sys.databases","limit":10}' \
  https://10.255.152.48:5000/query
```

**Success Response:**
```json
{
  "ok": true,
  "connection": "corp_sql_erp",
  "columns": ["name"],
  "rows": [["master"], ["tempdb"], ["model"], ["msdb"]],
  "rowcount": 4,
  "elapsed_ms": 12
}
```

**Error Response:**
```json
{
  "ok": false,
  "error": "Only SELECT queries are allowed",
  "code": "BAD_QUERY"
}
```

### GET /diag
Returns diagnostic information about available drivers and connection configurations.

**Authentication:** Required (`X-API-Key` header)

**Response:**
```json
{
  "connections": {
    "corp_sql_erp": {
      "type": "mssql",
      "host": "<YOUR_MSSQL_HOST_IP>",
      "port": 1433,
      "database": "master",
      "user": "<YOUR_SQL_USER>",
      "password": "*****"
    }
  },
  "available_drivers": {
    "mssql": ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"],
    "postgres": "Available"
  }
}
```

## Testing

### 1. Validate Configuration
```bash
python test_yaml_config.py
```

### 2. Test Authentication and API
```bash
python test_proxy_auth.py
```

### 3. Test POST /query Endpoint
```bash
python test_query_post.py [proxy_ip] [api_key]
```

### 4. Manual Testing from Mac
```bash
# Test health endpoint (no auth required)
curl -k https://10.255.152.48:5000/health

# Test POST query endpoint
curl -k -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"conn":"corp_sql_erp","sql":"SELECT 1 as test","limit":10}' \
  https://10.255.152.48:5000/query

# Test with parameters
curl -k -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"conn":"corp_sql_erp","sql":"SELECT name FROM sys.databases WHERE name LIKE ?","params":["%master%"]}' \
  https://10.255.152.48:5000/query
```

## Error Handling

The proxy returns JSON error responses with structured error codes:

- `401 Unauthorized` - Missing or invalid API key
- `400 Bad Request` - Invalid request format, parameters, or database errors
  - `INVALID_CONTENT_TYPE` - Non-JSON content type
  - `INVALID_JSON` - Malformed JSON request
  - `MISSING_SQL` / `MISSING_CONNECTION` - Required fields missing
  - `BAD_QUERY` - Non-SELECT query or multiple statements
  - `INVALID_LIMIT` / `INVALID_TIMEOUT` - Parameter validation failed
  - `DATABASE_ERROR` - Database connection or execution error

## Security Notes

- **Read-Only Enforcement**: Only SELECT queries allowed, enhanced validation against multiple statements
- **Parameterized Queries**: Safe parameter binding prevents SQL injection
- **Query Limits**: Server-side row limits prevent resource exhaustion
- **Timeouts**: Query timeouts prevent long-running operations
- **Read-Only Transactions**: Queries wrapped in read-only transactions where supported
- **Password Redaction**: Passwords redacted in diagnostic output
- **HTTPS Required**: No HTTP fallback, encrypted communication only
- **API Key Authentication**: Required on all endpoints except /health
- **Self-Signed Certificates**: Disable SSL verification in clients

## Troubleshooting

1. **"connections.yaml not found"**
   - Ensure connections.yaml is in the same directory as proxy.py

2. **"Environment variable not found"**
   - Check that all referenced environment variables are set
   - Use `test_yaml_config.py` to validate configuration

3. **"No suitable SQL Server ODBC driver found"**
   - Install ODBC Driver 18 or 17 for SQL Server on Windows

4. **"psycopg2 not available"**
   - Install psycopg2-binary: `pip install psycopg2-binary`

5. **SSL Certificate Issues**
   - Regenerate certificates if expired
   - Use `-k` flag with curl to ignore certificate warnings