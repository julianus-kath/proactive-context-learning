"""
Configuration for the MCP server.
Supports both PostgreSQL and SQL Server via DB_DIALECT environment variable.
"""

import os
from dataclasses import dataclass
from typing import Optional, Literal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DatabaseDialect = Literal["postgres", "mssql"]


@dataclass
class MCPServerConfig:
    """Configuration for the MCP server."""
    
    # Database dialect selection
    db_dialect: DatabaseDialect = os.getenv("DB_DIALECT", "postgres")  # postgres | mssql
    
    # PostgreSQL configuration (dev mode)
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_database: str = os.getenv("POSTGRES_DATABASE", "synthetic_erp_data")
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "")
    
    # SQL Server configuration (production mode)
    mssql_server: str = os.getenv("MSSQL_SERVER", "")
    mssql_database: str = os.getenv("MSSQL_DATABASE", "")
    mssql_user: str = os.getenv("MSSQL_USER", "")
    mssql_password: str = os.getenv("MSSQL_PASSWORD", "")
    mssql_driver: str = os.getenv("MSSQL_DRIVER", "ODBC Driver 17 for SQL Server")
    
    # Legacy database configuration (for backward compatibility)
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "synthetic_erp_data")
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "postgres")
    
    # Server configuration
    server_name: str = "erp-database-server"
    server_version: str = "1.0.0"
    
    # Query limits for safety
    max_query_results: int = int(os.getenv("MAX_QUERY_RESULTS", "1000"))
    query_timeout: int = int(os.getenv("QUERY_TIMEOUT", "30"))
    
    # Connection pool settings
    min_pool_size: int = int(os.getenv("MIN_POOL_SIZE", "1"))
    max_pool_size: int = int(os.getenv("MAX_POOL_SIZE", "10"))
    
    @property
    def connection_string(self) -> str:
        """Generate the database connection string (legacy)."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    def validate(self) -> None:
        """Validate configuration based on selected dialect."""
        if self.db_dialect == "mssql":
            if not self.mssql_server:
                raise ValueError("MSSQL_SERVER is required when DB_DIALECT=mssql")
            if not self.mssql_database:
                raise ValueError("MSSQL_DATABASE is required when DB_DIALECT=mssql")
            if not self.mssql_user:
                raise ValueError("MSSQL_USER is required when DB_DIALECT=mssql")
            if not self.mssql_password:
                raise ValueError("MSSQL_PASSWORD is required when DB_DIALECT=mssql")
        
        elif self.db_dialect == "postgres":
            if not self.postgres_host:
                raise ValueError("POSTGRES_HOST is required when DB_DIALECT=postgres")
            if not self.postgres_database:
                raise ValueError("POSTGRES_DATABASE is required when DB_DIALECT=postgres")
            if not self.postgres_user:
                raise ValueError("POSTGRES_USER is required when DB_DIALECT=postgres")
        
        else:
            raise ValueError(f"Invalid DB_DIALECT: {self.db_dialect}. Must be 'postgres' or 'mssql'")


# Global configuration instance
config = MCPServerConfig()