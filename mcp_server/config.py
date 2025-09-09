"""
Configuration for the MCP server.

NOTE: Database configuration now comes from the global shared_config.py
This ensures all services use the same database connection details.
"""

import os
import sys
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the parent directory to the path to import shared_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from shared_config import global_db_config, global_server_config
    
    @dataclass
    class MCPServerConfig:
        """Configuration for the MCP server using global settings."""
        
        # Database configuration from global config
        db_host: str = global_db_config.db_host
        db_port: int = global_db_config.db_port
        db_name: str = global_db_config.db_name
        db_user: str = global_db_config.db_user
        db_password: str = global_db_config.db_password
        db_schema: str = global_db_config.db_schema
        
        # Server configuration
        server_name: str = global_server_config.server_name
        server_version: str = global_server_config.server_version
        
        # Query limits for safety
        max_query_results: int = global_server_config.max_query_results
        query_timeout: int = global_server_config.query_timeout
        
        @property
        def connection_string(self) -> str:
            """Generate the database connection string."""
            return global_db_config.connection_string

except ImportError:
    # Fallback to local configuration if shared_config is not available
    @dataclass
    class MCPServerConfig:
        """Configuration for the MCP server."""
        
        # Database configuration (fallback values for your new database)
        db_host: str = os.getenv("DB_HOST", "localhost")
        db_port: int = int(os.getenv("DB_PORT", "5432"))
        db_name: str = os.getenv("DB_NAME", "mywebshop")
        db_user: str = os.getenv("DB_USER", "postgres")
        db_password: str = os.getenv("DB_PASSWORD", "your_password_here")
        db_schema: str = os.getenv("DB_SCHEMA", "webshop")
        
        # Server configuration
        server_name: str = "erp-database-server"
        server_version: str = "1.0.0"
        
        # Query limits for safety
        max_query_results: int = int(os.getenv("MAX_QUERY_RESULTS", "1000"))
        query_timeout: int = int(os.getenv("QUERY_TIMEOUT", "30"))
        
        @property
        def connection_string(self) -> str:
            """Generate the database connection string."""
            return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

# Global configuration instance
config = MCPServerConfig()