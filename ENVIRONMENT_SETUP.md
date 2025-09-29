# Environment Setup Guide (Prompt 6)

This guide explains how to set up the declarative configuration for the SQL proxy system, ensuring no secrets are stored in the agent code.

## Overview

The system uses two separate environment configuration files:
- **Agent Configuration** (`.env.agent.mac`): For the Mac-based agent
- **Proxy Configuration** (`.env.proxy.windows`): For the Windows-based proxy server

## Agent Configuration (.env.agent.mac)

### Location
Place this file in the project root directory on your Mac.

### Required Variables

```bash
# Database Client Mode
DB_MODE=proxy                                    # Use proxy mode (secure)

# Proxy Connection
PROXY_BASE_URL=https://10.255.152.48:5000       # Your proxy server URL
PROXY_API_KEY=your_secure_api_key_here          # Shared secret with proxy

# TLS Configuration
PROXY_TLS_VERIFY=true                           # Enable TLS verification
```

### Optional Variables

```bash
# Custom CA Bundle (for self-signed certificates)
PROXY_CA_BUNDLE=/path/to/proxy.crt

# Default Connection
PROXY_DEFAULT_CONN=corp_sql_erp                 # Default database connection

# Request Configuration
PROXY_TIMEOUT=30                                # Request timeout (seconds)
PROXY_MAX_RETRIES=3                            # Max retry attempts
```

### Development Override

For local development, you can switch to direct database mode:

```bash
DB_MODE=direct                                  # Use direct PostgreSQL connection
```

## Proxy Configuration (.env.proxy.windows)

### Location
Place this file on your Windows machine where the proxy server runs.

### Required Variables

```bash
# Server Binding
PROXY_BIND_HOST=0.0.0.0                        # Bind to all interfaces
PROXY_PORT=5000                                # Proxy server port

# Authentication
PROXY_API_KEY=your_secure_api_key_here         # Must match agent config

# TLS Certificates
PROXY_TLS_CERT_FILE=C:\temp\sqlproxy\proxy.crt # TLS certificate file
PROXY_TLS_KEY_FILE=C:\temp\sqlproxy\proxy.key  # TLS private key file

# Database Credentials (for YAML expansion)
SQLSERVER_PASSWORD=your_sqlserver_password     # SQL Server password
PG_PASSWORD=your_postgresql_password           # PostgreSQL password
```

### Optional Variables

```bash
# Additional Database Passwords
MYSQL_PASSWORD=your_mysql_password
ORACLE_PASSWORD=your_oracle_password

# Operational Settings
PROXY_MAX_CONNECTIONS=100                      # Max concurrent connections
PROXY_QUERY_TIMEOUT=30                         # Query timeout (seconds)
PROXY_MAX_QUERY_SIZE=1048576                   # Max query size (bytes)

# Logging
PROXY_LOG_LEVEL=INFO                           # Log level
PROXY_LOG_FILE=C:\temp\sqlproxy\proxy.log      # Log file path

# Security
PROXY_RATE_LIMIT_PER_MINUTE=60                 # Rate limit per IP
PROXY_MAX_REQUEST_SIZE=262144                  # Max request size (bytes)

# Connection Pooling
PROXY_POOL_SIZE=10                             # Connection pool size
PROXY_POOL_TIMEOUT=30                          # Pool timeout (seconds)
```

## Security Considerations

### File Permissions

**On Mac (Agent):**
```bash
chmod 600 .env.agent.mac
```

**On Windows (Proxy):**
```cmd
icacls .env.proxy.windows /grant:r "%USERNAME%":R /inheritance:r
```

### Version Control

**NEVER commit these files to version control!**

Add to `.gitignore`:
```
.env.agent.mac
.env.proxy.windows
*.env.local
*.env.production
```

### Secret Management

1. **Generate Strong API Keys:**
   ```bash
   # Generate a secure API key
   openssl rand -hex 32
   ```

2. **Rotate Credentials Regularly:**
   - Change API keys monthly
   - Update database passwords quarterly
   - Regenerate TLS certificates annually

3. **Backup Securely:**
   - Store encrypted backups of configuration files
   - Use secure password managers for credentials

## Loading Configuration

### Automatic Loading

The system automatically loads configuration when initializing the DatabaseClient:

```python
from app.db.client import DatabaseClient

# Automatically loads from .env.agent.mac
client = DatabaseClient()
```

### Manual Loading

You can also load configuration manually:

```python
from app.config import load_agent_config, print_config_status

# Load configuration
load_agent_config()

# Check configuration status
print_config_status()
```

### Configuration Validation

Validate your configuration:

```python
from app.config import validate_proxy_config

if validate_proxy_config():
    print("✅ Configuration is valid")
else:
    print("❌ Configuration is incomplete")
```

## Testing Configuration

Run the configuration test script:

```bash
python test_prompt6_config.py
```

This will validate:
- Environment file parsing
- Configuration validation
- DatabaseClient integration
- Security (no secrets exposed in logs)

## Troubleshooting

### Common Issues

1. **Missing Configuration File:**
   ```
   Error: PROXY_BASE_URL environment variable is required
   ```
   **Solution:** Create `.env.agent.mac` with required variables

2. **Invalid URL Format:**
   ```
   Error: Invalid PROXY_BASE_URL format
   ```
   **Solution:** Use full URL with protocol: `https://10.255.152.48:5000`

3. **TLS Certificate Issues:**
   ```
   Error: SSL certificate verification failed
   ```
   **Solutions:**
   - Set `PROXY_TLS_VERIFY=false` for testing
   - Provide `PROXY_CA_BUNDLE` path for self-signed certificates

4. **Connection Timeout:**
   ```
   Error: Connection timeout
   ```
   **Solutions:**
   - Increase `PROXY_TIMEOUT` value
   - Check network connectivity
   - Verify proxy server is running

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from app.config import print_config_status
print_config_status()
```

## Integration with Existing Code

### Minimal Changes Required

The configuration system is designed for minimal refactoring:

1. **Replace imports:**
   ```python
   # Old
   from langgraph_integration.direct_db_client import get_database_schema
   
   # New
   from app.db.adapter import get_database_schema
   ```

2. **Load configuration:**
   ```python
   from app.config import load_agent_config
   load_agent_config()  # Call once at startup
   ```

3. **Use DatabaseClient:**
   ```python
   from app.db.client import get_database_client
   
   client = get_database_client()
   columns, rows = client.query("SELECT * FROM users LIMIT 10")
   ```

## Next Steps

After setting up the configuration:

1. **Customize Configuration Files:**
   - Update `.env.agent.mac` with your actual proxy details
   - Update `.env.proxy.windows` with your actual credentials

2. **Set Up Proxy Server:**
   - Deploy proxy server on Windows machine
   - Configure TLS certificates
   - Start proxy service

3. **Test End-to-End:**
   - Run connectivity tests (Prompt 7)
   - Verify query execution
   - Test error handling

4. **Deploy to Production:**
   - Secure configuration files
   - Set up monitoring
   - Configure logging