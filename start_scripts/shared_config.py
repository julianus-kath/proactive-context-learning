"""
CENTRALIZED CONFIGURATION - SINGLE SOURCE OF TRUTH
====================================================
This is the ONLY file you need to edit to change database settings across the entire system.

Just update the database connection details below and it will be used everywhere:
- Synthetic Data Service
- MCP Server 
- Agent System
- All other components
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from root .env file
load_dotenv()

@dataclass
class GlobalDatabaseConfig:
    """Global database configuration - used by all services."""
    
    # =============================================================================
    # SINGLE SOURCE OF TRUTH - UPDATE THESE VALUES FOR YOUR DATABASE
    # =============================================================================
    
    # Your new PostgreSQL database settings
    db_type: str = os.getenv("DB_TYPE", "postgresql")
    db_host: str = os.getenv("DB_HOST", "localhost")  # or 127.0.0.1
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "mywebshop")
    db_schema: str = os.getenv("DB_SCHEMA", "webshop")
    db_user: str = os.getenv("DB_USER", "juli")  # or "juli"
    db_password: str = os.getenv("DB_PASSWORD", "")
    
    # =============================================================================
    # DERIVED PROPERTIES - DON'T CHANGE THESE
    # =============================================================================
    
    @property
    def connection_string(self) -> str:
        """Generate the database connection string."""
        if self.db_type == "postgresql":
            # Standard PostgreSQL connection string
            return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    @property
    def jdbc_url(self) -> str:
        """Generate JDBC URL for PostgreSQL."""
        return f"jdbc:postgresql://{self.db_host}:{self.db_port}/{self.db_name}"
    
    @property
    def connection_info(self) -> dict:
        """Get connection info as dictionary."""
        return {
            "host": self.db_host,
            "port": self.db_port,
            "database": self.db_name,
            "schema": self.db_schema,
            "user": self.db_user,
            "password": self.db_password
        }

@dataclass 
class GlobalServerConfig:
    """Global server configuration."""
    
    # Query limits for safety
    max_query_results: int = int(os.getenv("MAX_QUERY_RESULTS", "1000"))
    query_timeout: int = int(os.getenv("QUERY_TIMEOUT", "30"))
    
    # Server info
    server_name: str = "erp-database-server"
    server_version: str = "1.0.0"

# =============================================================================
# GLOBAL INSTANCES - USED BY ALL SERVICES
# =============================================================================

# Single global database config instance
global_db_config = GlobalDatabaseConfig()
global_server_config = GlobalServerConfig()

# Print connection info for verification
def print_connection_info():
    """Print current database connection information."""
    print("="*60)
    print("GLOBAL DATABASE CONNECTION SETTINGS")
    print("="*60)
    print(f"Database Type: {global_db_config.db_type}")
    print(f"Host: {global_db_config.db_host}")
    print(f"Port: {global_db_config.db_port}")
    print(f"Database: {global_db_config.db_name}")
    print(f"Schema: {global_db_config.db_schema}")
    print(f"User: {global_db_config.db_user}")
    print(f"Connection String: {global_db_config.connection_string}")
    print(f"JDBC URL: {global_db_config.jdbc_url}")
    print("="*60)

if __name__ == "__main__":
    print_connection_info()