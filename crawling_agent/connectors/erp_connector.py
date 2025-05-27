"""
ERP Connector for executing SQL queries against the ERP database.
"""
import time
from typing import Dict, List, Any, Optional, Union
import sqlite3
import pandas as pd
import yaml
import os

from crawling_agent.models.task_instruction import DataSourceQuery, QueryType
from crawling_agent.models.crawling_context import ActionRequest
from crawling_agent.utils.logger import get_logger


class ERPConnector:
    """
    Connector for crawling data from an ERP system using SQL queries.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the ERP connector.
        
        Args:
            config_path: Path to the configuration file (optional)
        """
        self.logger = get_logger(__name__)
        
        # Load configuration
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config",
                "config.yaml"
            )
        
        self.config = self._load_config(config_path)
        self.connection = None
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from the YAML file with environment variable substitution.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Dictionary containing the configuration
        """
        with open(config_path, 'r') as f:
            # Load the YAML content
            config_str = f.read()
            
            # Replace environment variables
            for env_var in os.environ:
                placeholder = f"${{{env_var}}}"
                if placeholder in config_str:
                    config_str = config_str.replace(placeholder, os.environ[env_var])
            
            # Handle default values in format ${VAR:default}
            import re
            pattern = r'\${([^{}]+):([^{}]*)}'
            
            def replace_with_default(match):
                env_var, default = match.groups()
                return os.environ.get(env_var, default)
            
            config_str = re.sub(pattern, replace_with_default, config_str)
            
            # Parse the modified YAML
            config = yaml.safe_load(config_str)
            
            return config
    
    def connect(self) -> None:
        """
        Establish a connection to the ERP database.
        """
        if self.connection is not None:
            return
        
        try:
            db_uri = self.config['data_sources']['erp']['uri']
            self.logger.info(f"Connecting to ERP database: {db_uri}")
            
            # For SQLite, extract the path from the URI
            if db_uri.startswith('sqlite:///'):
                db_path = db_uri[10:]
                self.connection = sqlite3.connect(db_path)
                self.logger.info(f"Connected to SQLite database at {db_path}")
            else:
                # For other database types, you would use appropriate drivers
                # For example, with SQLAlchemy:
                # from sqlalchemy import create_engine
                # self.connection = create_engine(db_uri).connect()
                raise NotImplementedError(f"Database driver for {db_uri} not implemented")
                
        except Exception as e:
            self.logger.error(f"Error connecting to ERP database: {str(e)}")
            raise
    
    def disconnect(self) -> None:
        """
        Close the connection to the ERP database.
        """
        if self.connection is not None:
            self.connection.close()
            self.connection = None
            self.logger.info("Disconnected from ERP database")
    
    def execute_query(self, query: DataSourceQuery) -> Dict[str, Any]:
        """
        Execute a SQL query against the ERP database.
        
        Args:
            query: The DataSourceQuery object containing the SQL query and parameters
            
        Returns:
            Dictionary containing the query results and metadata
        """
        if query.query_type != QueryType.SQL:
            raise ValueError(f"Invalid query type for ERP connector: {query.query_type}")
        
        self.connect()
        
        start_time = time.time()
        
        try:
            self.logger.info(f"Executing SQL query: {query.query}")
            self.logger.debug(f"Query parameters: {query.parameters}")
            
            # Execute the query
            df = pd.read_sql_query(query.query, self.connection, params=query.parameters)
            
            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            
            # Prepare the result
            result = {
                "data": df.to_dict(orient="records"),
                "metadata": {
                    "row_count": len(df),
                    "columns": list(df.columns),
                    "execution_time_ms": execution_time
                }
            }
            
            self.logger.info(f"Query executed successfully. Retrieved {len(df)} rows in {execution_time:.2f}ms")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing SQL query: {str(e)}")
            raise
        finally:
            # Keep the connection open for potential future queries
            pass
    
    def __enter__(self):
        """
        Context manager entry point.
        """
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit point.
        """
        self.disconnect()