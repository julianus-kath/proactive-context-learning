# Rollback Guide: DB_MODE=direct

This document explains how to use the rollback flag for local development when the proxy is unavailable.

## Overview

The `DB_MODE` environment variable allows you to switch between proxy mode (default) and direct database mode for local development:

- **`DB_MODE=proxy`** (default): Routes all database calls through the SQL proxy server
- **`DB_MODE=direct`**: Connects directly to PostgreSQL database (for local development only)

## When to Use Direct Mode

Use direct mode (`DB_MODE=direct`) in these scenarios:

1. **Local Development**: When developing on your local machine without VPN access
2. **Proxy Unavailable**: When the Windows proxy server is down or unreachable
3. **Testing**: When you need to test against a local PostgreSQL instance
4. **Debugging**: When you need direct database access for troubleshooting

## Configuration

### Proxy Mode (Default)
```bash
# .env.agent.mac
DB_MODE=proxy
PROXY_BASE_URL=https://10.255.152.48:5000
PROXY_API_KEY=your_api_key_here
PROXY_DEFAULT_CONN=corp_sql_erp
```

### Direct Mode (Local Development)
```bash
# .env.agent.mac
DB_MODE=direct
DB_HOST=localhost
DB_PORT=5432
DB_NAME=synthetic_erp_data
DB_USER=postgres
DB_PASSWORD=postgres
```

## Usage Examples

### Switching to Direct Mode

1. **Environment Variable**:
   ```bash
   export DB_MODE=direct
   ```

2. **In Code**:
   ```python
   import os
   os.environ["DB_MODE"] = "direct"
   
   from app.db.client import DatabaseClient
   client = DatabaseClient()  # Will use direct mode
   ```

3. **Configuration File**:
   ```bash
   # Add to .env.agent.mac
   DB_MODE=direct
   ```

### Using DatabaseClient

```python
from app.db.client import DatabaseClient

# Initialize client (mode determined by DB_MODE environment variable)
client = DatabaseClient()

# Check current mode
print(f"Current mode: {client.mode}")

# Query works the same regardless of mode
try:
    columns, rows = client.query("SELECT 1 as test")
    print(f"Result: {columns}, {rows}")
except NotImplementedError:
    print("Direct mode not fully implemented yet")
```

## Implementation Status

### ✅ Proxy Mode (Fully Implemented)
- ✅ HTTPS communication with proxy server
- ✅ API key authentication
- ✅ TLS certificate verification
- ✅ Connection pooling via proxy
- ✅ Error handling and retries
- ✅ Health checks and diagnostics

### ⚠️ Direct Mode (Placeholder)
- ❌ Direct PostgreSQL connection (not implemented)
- ❌ Connection pooling
- ❌ Query execution
- ✅ Mode detection and configuration
- ✅ Error handling (NotImplementedError)

## Implementing Direct Mode

To fully implement direct mode, update the `_query_direct` method in `app/db/client.py`:

```python
def _query_direct(self, sql: str, params: Optional[Dict[str, Any]] = None, 
                  limit: Optional[int] = None, timeout_s: Optional[int] = None) -> Tuple[List[str], List[List[Any]]]:
    """Execute query via direct PostgreSQL connection."""
    import psycopg2
    import psycopg2.extras
    
    try:
        # Create connection
        conn = psycopg2.connect(**self.db_config)
        
        with conn.cursor() as cur:
            # Set timeout if specified
            if timeout_s:
                cur.execute(f"SET statement_timeout = {timeout_s * 1000}")
            
            # Execute query
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            
            # Get results
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall() if columns else []
            
            # Apply limit if specified
            if limit and len(rows) > limit:
                rows = rows[:limit]
            
            return columns, [list(row) for row in rows]
            
    except Exception as e:
        logger.error(f"Direct query failed: {e}")
        raise RuntimeError(f"Direct database query failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()
```

## Security Considerations

### ⚠️ Direct Mode Security
- **Local Development Only**: Never use direct mode in production
- **Database Credentials**: Direct mode requires database credentials in environment
- **Network Security**: Direct mode bypasses proxy security controls
- **VPN Requirements**: May require VPN for database access

### ✅ Proxy Mode Security
- **No Database Credentials**: Agent never stores database passwords
- **API Key Authentication**: Secure authentication with proxy
- **TLS Encryption**: All communication encrypted
- **Read-Only Access**: Proxy enforces SELECT-only queries

## Troubleshooting

### Common Issues

1. **Mode Not Switching**:
   ```bash
   # Check environment variable
   echo $DB_MODE
   
   # Restart application after changing
   ```

2. **Direct Mode Not Working**:
   ```python
   # Expected behavior - not implemented yet
   NotImplementedError: Direct mode not implemented yet
   ```

3. **Proxy Mode Connection Issues**:
   ```bash
   # Check proxy configuration
   curl -k -H "X-API-Key: $PROXY_API_KEY" $PROXY_BASE_URL/health
   ```

### Debug Commands

```bash
# Test current mode
python -c "from app.db.client import DatabaseClient; print(DatabaseClient().mode)"

# Test proxy connectivity
python test_prompt7_e2e.py

# Test safety features
python test_prompt8_safety.py
```

## Migration Path

### From Proxy to Direct (Development)
1. Set `DB_MODE=direct`
2. Configure PostgreSQL connection variables
3. Implement direct mode functionality
4. Test with local database

### From Direct to Proxy (Production)
1. Set `DB_MODE=proxy` (or remove - it's default)
2. Configure proxy connection variables
3. Ensure proxy server is running
4. Test connectivity with health checks

## Best Practices

1. **Environment-Specific Configuration**: Use different `.env` files for different environments
2. **Default to Proxy**: Keep proxy mode as default for security
3. **Document Switches**: Always document when and why you switch modes
4. **Test Both Modes**: Ensure your code works in both modes during development
5. **Security First**: Never use direct mode with production credentials

## Example Configurations

### Development Environment
```bash
# .env.development
DB_MODE=direct
DB_HOST=localhost
DB_PORT=5432
DB_NAME=test_erp_data
DB_USER=dev_user
DB_PASSWORD=dev_password
```

### Production Environment
```bash
# .env.production
DB_MODE=proxy
PROXY_BASE_URL=https://proxy.company.com:5000
PROXY_API_KEY=prod_api_key_here
PROXY_DEFAULT_CONN=prod_sql_server
PROXY_TLS_VERIFY=true
PROXY_CA_BUNDLE=/etc/ssl/certs/company-ca.crt
```

This rollback mechanism ensures you can always continue development even when the proxy infrastructure is unavailable.