"""
Configuration for the MCP server.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class MCPServerConfig:
    """Configuration for the MCP server."""
    
    # Database configuration
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
    
    @property
    def connection_string(self) -> str:
        """Generate the database connection string."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

# Global configuration instance
config = MCPServerConfig()