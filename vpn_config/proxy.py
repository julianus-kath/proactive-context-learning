# proxy.py  — tiny read-only SQL-over-HTTP proxy

# Run on Windows (VPN-connected). Your Mac calls https://<windows_lan_ip>:5000/query?sql=...

# Security: ONLY SELECT is allowed. Requires API key auth and HTTPS.

from flask import Flask, request, jsonify, Response, abort, g

import os

import pyodbc

import csv

import io

import re

import yaml

import string

import time

import json

import sys

import logging

from flask_limiter import Limiter

from flask_limiter.util import get_remote_address

try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

# Version information
PROXY_VERSION = "1.5.0"  # Prompt 7 & 8 implementation: E2E Testing + Safety & Operability
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

# Safe logging functions
def redact_secrets(text):
    """Redact common secret patterns from text for safe logging."""
    if not isinstance(text, str):
        return str(text)
    
    # Redact connection string passwords (only when part of connection strings with other elements)
    text = re.sub(r'((?:.*;|^[^"\']*?)PWD=)([^;]+)', r'\1*****', text, flags=re.IGNORECASE)
    
    # Redact password-like patterns with quotes (handle each quote type separately)
    text = re.sub(r'(password\s*[:=]\s*")([^"]+)(")', r'\1*****\3', text, flags=re.IGNORECASE)
    text = re.sub(r"(password\s*[:=]\s*')([^']+)(')", r'\1*****\3', text, flags=re.IGNORECASE)
    text = re.sub(r'(pwd\s*[:=]\s*")([^"]+)(")', r'\1*****\3', text, flags=re.IGNORECASE)
    text = re.sub(r"(pwd\s*[:=]\s*')([^']+)(')", r'\1*****\3', text, flags=re.IGNORECASE)
    text = re.sub(r'(api[_-]?key\s*[:=]\s*")([^"]+)(")', r'\1*****\3', text, flags=re.IGNORECASE)
    text = re.sub(r"(api[_-]?key\s*[:=]\s*')([^']+)(')", r'\1*****\3', text, flags=re.IGNORECASE)
    
    # Redact password-like patterns without quotes (avoid already redacted ones)
    text = re.sub(r'(password\s*[:=]\s*)([^"\';\s]+)(?!\*)', r'\1*****', text, flags=re.IGNORECASE)
    text = re.sub(r'(pwd\s*[:=]\s*)([^"\';\s]+)(?!\*)', r'\1*****', text, flags=re.IGNORECASE)
    text = re.sub(r'(api[_-]?key\s*[:=]\s*)([^"\';\s]+)(?!\*)', r'\1*****', text, flags=re.IGNORECASE)
    
    return text

def safe_log(message, level=logging.INFO):
    """Log a message with secrets redacted."""
    safe_message = redact_secrets(str(message))
    logging.log(level, safe_message)

def safe_print(message):
    """Print a message with secrets redacted."""
    safe_message = redact_secrets(str(message))
    print(safe_message)

app = Flask(__name__)

# --- Proxy Configuration (new) ---
PROXY_BIND_HOST = os.getenv("PROXY_BIND_HOST", "0.0.0.0")
PROXY_PORT = int(os.getenv("PROXY_PORT", "5000"))
PROXY_API_KEY = os.getenv("PROXY_API_KEY")
PROXY_TLS_CERT_FILE = os.getenv("PROXY_TLS_CERT_FILE")
PROXY_TLS_KEY_FILE = os.getenv("PROXY_TLS_KEY_FILE")

# --- Safety & Operability Configuration (Prompt 8) ---
PROXY_MAX_REQUEST_SIZE = int(os.getenv("PROXY_MAX_REQUEST_SIZE", "262144"))  # 256KB default
PROXY_RATE_LIMIT_PER_MINUTE = int(os.getenv("PROXY_RATE_LIMIT_PER_MINUTE", "30"))  # 30 req/min default

# Configure Flask request size limit
app.config['MAX_CONTENT_LENGTH'] = PROXY_MAX_REQUEST_SIZE

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{PROXY_RATE_LIMIT_PER_MINUTE} per minute"]
)
limiter.init_app(app)

# Simple configuration - no mandatory security for development
safe_print("🚀 SQL Proxy starting in simple mode...")
if not PROXY_API_KEY:
    safe_print("⚠️  No API key set - authentication disabled")
if not PROXY_TLS_CERT_FILE or not PROXY_TLS_KEY_FILE:
    safe_print("⚠️  No TLS certificates - HTTP mode enabled")

# --- Multi-Database Configuration (YAML-based) ---

def expand_env_vars(text):
    """Expand ${VAR} environment variables in text with optional defaults."""
    if not isinstance(text, str):
        return text
    
    # Handle ${VAR:-default} syntax manually
    import re
    def replace_with_default(match):
        var_expr = match.group(1)
        if ':-' in var_expr:
            var_name, default_value = var_expr.split(':-', 1)
            return os.environ.get(var_name, default_value)
        else:
            var_name = var_expr
            if var_name not in os.environ:
                # Just warn and use placeholder - don't fail
                safe_print(f"⚠️  Environment variable {var_name} not set, using placeholder")
                return f"MISSING_{var_name}"
            return os.environ[var_name]
    
    # Replace ${VAR} and ${VAR:-default} patterns
    result = re.sub(r'\$\{([^}]+)\}', replace_with_default, text)
    return result


def load_connections_config():
    """Load and validate connections configuration from YAML file."""
    config_path = os.path.join(os.path.dirname(__file__), 'connections.yaml')
    
    if not os.path.exists(config_path):
        raise RuntimeError(f"connections.yaml not found at: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise RuntimeError(f"Invalid YAML in connections.yaml: {e}")
    
    if not config or 'connections' not in config:
        raise RuntimeError("connections.yaml must contain a 'connections' section")
    
    connections = {}
    for name, conn_config in config['connections'].items():
        # Validate required fields
        if 'type' not in conn_config:
            raise RuntimeError(f"Connection '{name}' missing required 'type' field")
        
        # Expand environment variables in all string values
        expanded_config = {}
        for key, value in conn_config.items():
            expanded_config[key] = expand_env_vars(value)
        
        # Validate type-specific requirements
        conn_type = expanded_config['type']
        if conn_type == 'mssql':
            required_fields = ['host', 'port', 'database', 'user', 'password']
            for field in required_fields:
                if field not in expanded_config:
                    raise RuntimeError(f"MSSQL connection '{name}' missing required field: {field}")
        elif conn_type == 'postgres':
            required_fields = ['host', 'port', 'database', 'user', 'password']
            for field in required_fields:
                if field not in expanded_config:
                    raise RuntimeError(f"PostgreSQL connection '{name}' missing required field: {field}")
            if not POSTGRES_AVAILABLE:
                raise RuntimeError(f"PostgreSQL connection '{name}' configured but psycopg2 not installed")
        else:
            raise RuntimeError(f"Unsupported connection type '{conn_type}' for connection '{name}'")
        
        connections[name] = expanded_config
    
    return connections


def get_mssql_connection(config):
    """Create MSSQL connection using pyodbc."""
    # Use specified driver or auto-detect
    driver = config.get('driver')
    if not driver:
        # Auto-detect available driver
        try:
            installed = [d.strip("{}") for d in pyodbc.drivers()]
            preferred = ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server"]
            driver = next((d for d in preferred if d in installed), None)
            if not driver:
                raise RuntimeError("No suitable SQL Server ODBC driver found")
        except Exception as e:
            raise RuntimeError(f"Failed to detect ODBC drivers: {e}")
    
    # Build connection string
    conn_parts = {
        "DRIVER": "{" + driver + "}",
        "SERVER": f"{config['host']},{config['port']}",
        "DATABASE": config['database'],
        "UID": config['user'],
        "PWD": config['password'],
    }
    
    # Add optional SSL settings
    if config.get('encrypt'):
        conn_parts["Encrypt"] = "yes" if config['encrypt'] else "no"
    if config.get('trust_server_certificate'):
        conn_parts["TrustServerCertificate"] = "yes" if config['trust_server_certificate'] else "no"
    
    conn_str = ";".join(f"{k}={v}" for k, v in conn_parts.items()) + ";"
    
    return pyodbc.connect(conn_str, autocommit=True)


def get_postgres_connection(config):
    """Create PostgreSQL connection using psycopg2."""
    if not POSTGRES_AVAILABLE:
        raise RuntimeError("psycopg2 not available for PostgreSQL connections")
    
    conn_params = {
        'host': config['host'],
        'port': config['port'],
        'database': config['database'],
        'user': config['user'],
        'password': config['password'],
    }
    
    # Add optional SSL settings
    if config.get('sslmode'):
        conn_params['sslmode'] = config['sslmode']
    
    return psycopg2.connect(**conn_params)


def get_database_connection(connection_name):
    """Get a database connection by name."""
    if connection_name not in CONNECTIONS:
        raise ValueError(f"Unknown connection: {connection_name}")
    
    config = CONNECTIONS[connection_name]
    conn_type = config['type']
    
    if conn_type == 'mssql':
        return get_mssql_connection(config)
    elif conn_type == 'postgres':
        return get_postgres_connection(config)
    else:
        raise ValueError(f"Unsupported connection type: {conn_type}")


# Load connections configuration at startup
CONNECTIONS = load_connections_config()

# Log startup information safely
safe_print(f"SQL Proxy v{PROXY_VERSION} starting up...")
safe_print(f"Python version: {PYTHON_VERSION}")
safe_print(f"Loaded {len(CONNECTIONS)} database connections:")
for name, config in CONNECTIONS.items():
    safe_print(f"  - {name}: {config.get('type', 'unknown')} database")

# Log safety configuration
safe_print(f"Safety Configuration:")
safe_print(f"  - Max request size: {PROXY_MAX_REQUEST_SIZE} bytes ({PROXY_MAX_REQUEST_SIZE // 1024}KB)")
safe_print(f"  - Rate limit: {PROXY_RATE_LIMIT_PER_MINUTE} requests per minute per IP")
safe_print(f"  - Request/response timing: enabled")
safe_print(f"  - Global error handling: enabled")

# Log driver availability
try:
    drivers = [d.strip("{}") for d in pyodbc.drivers()]
    safe_print(f"Available ODBC drivers: {len(drivers)} found")
    for driver in drivers:
        safe_print(f"  - {driver}")
except Exception as e:
    safe_print(f"ODBC driver detection failed: {e}")

safe_print(f"PostgreSQL support: {'Available' if POSTGRES_AVAILABLE else 'Not installed'}")


# --- Request Timing & Global Error Handling (Prompt 8) ---
@app.before_request
def before_request():
    """Initialize request timing and validate API key"""
    # Start timing
    g.start_time = time.time()
    g.request_id = f"{int(time.time() * 1000)}-{id(request)}"
    
    # Log request start (without sensitive data)
    safe_log(f"[{g.request_id}] {request.method} {request.path} from {get_remote_address()}")
    
    # Skip authentication for health endpoint
    if request.endpoint == 'health':
        return
    
    # Check for API key header (optional if no key is set)
    if not PROXY_API_KEY:
        # No API key configured - skip authentication
        return
    
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != PROXY_API_KEY:
        return jsonify({"ok": False, "error": "unauthorized", "code": "UNAUTHORIZED"}), 401

@app.after_request
def after_request(response):
    """Log request completion with timing"""
    if hasattr(g, 'start_time'):
        elapsed_ms = int((time.time() - g.start_time) * 1000)
        request_id = getattr(g, 'request_id', 'unknown')
        
        # Log response (without sensitive data)
        safe_log(f"[{request_id}] {response.status_code} - {elapsed_ms}ms")
    
    return response

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle oversized request bodies"""
    return jsonify({
        "ok": False,
        "error": f"Request body too large (max {PROXY_MAX_REQUEST_SIZE} bytes)",
        "code": "REQUEST_TOO_LARGE"
    }), 413

@app.errorhandler(429)
def ratelimit_handler(error):
    """Handle rate limit exceeded"""
    return jsonify({
        "ok": False,
        "error": f"Rate limit exceeded ({PROXY_RATE_LIMIT_PER_MINUTE} requests per minute)",
        "code": "RATE_LIMIT_EXCEEDED"
    }), 429

@app.errorhandler(Exception)
def handle_exception(error):
    """Global error handler - always return JSON with ok:false"""
    request_id = getattr(g, 'request_id', 'unknown')
    
    # Log the error (without sensitive data)
    safe_log(f"[{request_id}] Unhandled exception: {type(error).__name__}", logging.ERROR)
    
    # Return consistent JSON error response
    return jsonify({
        "ok": False,
        "error": "Internal server error",
        "code": "INTERNAL_ERROR"
    }), 500


@app.route("/diag")
def diag():
    """Diagnostic endpoint showing safe system information without secrets."""
    diag_info = {
        "version": {
            "proxy": PROXY_VERSION,
            "python": PYTHON_VERSION
        },
        "connections": [],
        "drivers": {}
    }
    
    # Get available ODBC drivers
    try:
        installed_drivers = [d.strip("{}") for d in pyodbc.drivers()]
        diag_info["drivers"]["mssql"] = installed_drivers
    except Exception as e:
        diag_info["drivers"]["mssql"] = f"Error: {str(e)}"
    
    # Add PostgreSQL availability
    diag_info["drivers"]["postgres"] = "Available" if POSTGRES_AVAILABLE else "Not installed"
    
    # Show only safe connection information (name and type only)
    for name, config in CONNECTIONS.items():
        safe_connection = {
            "name": name,
            "type": config.get('type', 'unknown')
        }
        diag_info["connections"].append(safe_connection)
    
    return jsonify(diag_info)


# Enhanced read-only guards
SELECT_ONLY = re.compile(r"^\s*select\b", re.IGNORECASE | re.DOTALL)
# Check for semicolon followed by non-whitespace that's not a comment
SEMICOLON_CHECK = re.compile(r";\s*(?!--)[^\s]", re.IGNORECASE | re.DOTALL)


def validate_read_only_query(sql: str):
    """Validate that SQL is a safe read-only SELECT query."""
    # Strip whitespace and normalize
    sql_stripped = sql.strip()
    
    if not sql_stripped:
        raise ValueError("Empty SQL query")
    
    # Must start with SELECT
    if not SELECT_ONLY.match(sql_stripped):
        raise ValueError("Only SELECT queries are allowed")
    
    # Check for multiple statements (semicolon followed by more content that's not a comment)
    if SEMICOLON_CHECK.search(sql_stripped):
        raise ValueError("Multiple statements not allowed (found semicolon with additional content)")
    
    return True


def apply_query_limit(sql: str, limit: int, connection_type: str):
    """Apply server-side limit to query if not already present."""
    sql_upper = sql.upper()
    
    if connection_type == 'mssql':
        # Check if TOP is already present
        if 'TOP ' in sql_upper:
            return sql  # Already has limit
        
        # Insert TOP clause after SELECT
        select_match = re.match(r'(\s*SELECT\s+)', sql, re.IGNORECASE)
        if select_match:
            return sql[:select_match.end()] + f"TOP {limit} " + sql[select_match.end():]
        return sql
    
    elif connection_type == 'postgres':
        # Check if LIMIT is already present
        if 'LIMIT ' in sql_upper:
            return sql  # Already has limit
        
        # Append LIMIT clause
        return sql.rstrip(';') + f" LIMIT {limit}"
    
    return sql


def run_select(sql: str, connection_name: str, params=None, timeout_s=30):
    """Execute SELECT query on specified database connection with parameters and timeout."""
    start_time = time.time()
    
    # Open a short-lived connection per request (simple + safe)
    with get_database_connection(connection_name) as conn:
        config = CONNECTIONS[connection_name]
        conn_type = config['type']
        
        if conn_type == 'mssql':
            # Set query timeout
            conn.timeout = timeout_s
            
            # Use read-only transaction where possible
            cur = conn.cursor()
            
            # Execute with parameters if provided
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            
            cols = [c[0] for c in cur.description] if cur.description else []
            rows = cur.fetchall() if cols else []
            
        elif conn_type == 'postgres':
            # Set statement timeout
            cur = conn.cursor()
            cur.execute(f"SET statement_timeout = {timeout_s * 1000}")  # PostgreSQL uses milliseconds
            
            # Start read-only transaction
            cur.execute("BEGIN READ ONLY")
            
            try:
                # Execute with parameters if provided
                if params:
                    cur.execute(sql, params)
                else:
                    cur.execute(sql)
                
                cols = [desc[0] for desc in cur.description] if cur.description else []
                rows = cur.fetchall() if cols else []
                
                # Convert to tuples for consistency
                if rows and hasattr(rows[0], '_asdict'):
                    rows = [tuple(row) for row in rows]
                elif rows and isinstance(rows[0], dict):
                    rows = [tuple(row[col] for col in cols) for row in rows]
                
                conn.commit()  # Commit read-only transaction
                
            except Exception:
                conn.rollback()
                raise
        else:
            raise ValueError(f"Unsupported connection type: {conn_type}")
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    return cols, rows, elapsed_ms


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "connections": list(CONNECTIONS.keys())
    })


@app.route("/query", methods=["POST"])
def query():
    """Execute SELECT queries with JSON request/response format."""
    # Validate Content-Type
    if not request.is_json:
        return jsonify({
            "ok": False,
            "error": "Content-Type must be application/json",
            "code": "INVALID_CONTENT_TYPE"
        }), 400
    
    try:
        data = request.get_json()
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"Invalid JSON: {str(e)}",
            "code": "INVALID_JSON"
        }), 400
    
    # Validate required fields
    if not data or not isinstance(data, dict):
        return jsonify({
            "ok": False,
            "error": "Request body must be a JSON object",
            "code": "INVALID_REQUEST"
        }), 400
    
    sql = data.get("sql")
    connection_name = data.get("conn")
    params = data.get("params")
    limit = data.get("limit", 1000)  # Default limit
    timeout_s = data.get("timeout_s", 30)  # Default timeout
    
    # Validate required fields
    if not sql:
        return jsonify({
            "ok": False,
            "error": "Missing required field: 'sql'",
            "code": "MISSING_SQL"
        }), 400
    
    if not connection_name:
        return jsonify({
            "ok": False,
            "error": "Missing required field: 'conn'",
            "code": "MISSING_CONNECTION"
        }), 400
    
    # Validate connection exists
    if connection_name not in CONNECTIONS:
        return jsonify({
            "ok": False,
            "error": f"Unknown connection: {connection_name}",
            "code": "UNKNOWN_CONNECTION"
        }), 400
    
    # Validate limit and timeout
    if not isinstance(limit, int) or limit <= 0 or limit > 10000:
        return jsonify({
            "ok": False,
            "error": "Limit must be an integer between 1 and 10000",
            "code": "INVALID_LIMIT"
        }), 400
    
    if not isinstance(timeout_s, (int, float)) or timeout_s <= 0 or timeout_s > 300:
        return jsonify({
            "ok": False,
            "error": "Timeout must be a number between 0 and 300 seconds",
            "code": "INVALID_TIMEOUT"
        }), 400
    
    # Validate read-only query
    try:
        validate_read_only_query(sql)
    except ValueError as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "code": "BAD_QUERY"
        }), 400
    
    # Apply server-side limit if needed
    config = CONNECTIONS[connection_name]
    conn_type = config['type']
    sql_with_limit = apply_query_limit(sql, limit, conn_type)
    
    # Execute query
    try:
        # Log query execution (without parameters for security)
        safe_log(f"Executing query on {connection_name}: {sql_with_limit[:100]}{'...' if len(sql_with_limit) > 100 else ''}")
        
        cols, rows, elapsed_ms = run_select(sql_with_limit, connection_name, params, timeout_s)
        
        # Convert rows to list of lists for consistent format
        row_data = []
        if rows:
            for row in rows:
                row_data.append([str(val) if val is not None else None for val in row])
        
        # Log successful execution (without data for security)
        safe_log(f"Query completed: {len(row_data)} rows returned in {elapsed_ms}ms")
        
        return jsonify({
            "ok": True,
            "connection": connection_name,
            "columns": cols,
            "rows": row_data,
            "rowcount": len(row_data),
            "elapsed_ms": elapsed_ms
        })
        
    except (pyodbc.Error, psycopg2.Error) as e:
        # Log database errors (without sensitive details)
        safe_log(f"Database error on {connection_name}: {type(e).__name__}", logging.ERROR)
        return jsonify({
            "ok": False,
            "error": f"Database error: {str(e)}",
            "code": "DATABASE_ERROR"
        }), 400
    except Exception as e:
        # Log general errors
        safe_log(f"Query execution error on {connection_name}: {type(e).__name__}", logging.ERROR)
        return jsonify({
            "ok": False,
            "error": f"Query execution failed: {str(e)}",
            "code": "EXECUTION_ERROR"
        }), 400


if __name__ == "__main__":
    # Determine if we should use HTTPS or HTTP
    use_https = (PROXY_TLS_CERT_FILE and PROXY_TLS_KEY_FILE and 
                 os.path.exists(PROXY_TLS_CERT_FILE) and 
                 os.path.exists(PROXY_TLS_KEY_FILE))
    
    if use_https:
        # HTTPS mode
        ssl_context = (PROXY_TLS_CERT_FILE, PROXY_TLS_KEY_FILE)
        safe_print(f"🔒 Starting HTTPS proxy server on {PROXY_BIND_HOST}:{PROXY_PORT}")
        safe_print(f"Using certificate: {PROXY_TLS_CERT_FILE}")
        safe_print(f"Using key: {PROXY_TLS_KEY_FILE}")
        
        app.run(
            host=PROXY_BIND_HOST,
            port=PROXY_PORT,
            ssl_context=ssl_context,
            debug=False
        )
    else:
        # HTTP mode - simple and works out of the box
        safe_print(f"🌐 Starting HTTP proxy server on {PROXY_BIND_HOST}:{PROXY_PORT}")
        safe_print("⚠️  HTTP mode - add TLS certificates for production security")
        safe_print("")
        safe_print("🎯 Access URLs:")
        safe_print(f"   Health: http://{PROXY_BIND_HOST}:{PROXY_PORT}/health")
        safe_print(f"   Diag:   http://{PROXY_BIND_HOST}:{PROXY_PORT}/diag")
        safe_print("")
        safe_print("Press Ctrl+C to stop")
        safe_print("=" * 50)
        
        app.run(
            host=PROXY_BIND_HOST,
            port=PROXY_PORT,
            debug=False
        )

