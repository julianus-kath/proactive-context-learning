"""
SQL Agent for interacting with the ERP database.
"""
import os
import sqlite3
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import from synthetic_data_service
import sys
sys.path.append('/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code')
from synthetic_data_service.db import get_db_session
from synthetic_data_service.models import Customer, Product, Sale, Supplier, Employee, WarehouseItem


class SQLDatabaseConnector:
    """
    Connector for the ERP database (SQLite).
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize the SQL database connector.
        
        Args:
            db_path: Path to the SQLite database file
        """
        if db_path is None:
            # Default to the synthetic data service database
            db_path = '/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/synthetic_data.db'
        
        self.db_path = db_path
        self.connection = None
        self.engine = None
        
    def connect(self):
        """
        Connect to the database.
        """
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
            self.engine = create_engine(f'sqlite:///{self.db_path}')
            
    def disconnect(self):
        """
        Disconnect from the database.
        """
        if self.connection is not None:
            self.connection.close()
            self.connection = None
            
    def get_tables(self) -> List[str]:
        """
        Get a list of tables in the database.
        
        Returns:
            List of table names
        """
        self.connect()
        cursor = self.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        return [table[0] for table in tables]
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, str]]:
        """
        Get the schema for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of column definitions
        """
        self.connect()
        cursor = self.connection.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        
        schema = []
        for col in columns:
            schema.append({
                "name": col[1],
                "type": col[2],
                "primary_key": bool(col[5])
            })
            
        return schema
    
    def get_database_schema(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get the schema for the entire database.
        
        Returns:
            Dictionary mapping table names to their schemas
        """
        tables = self.get_tables()
        schema = {}
        
        for table in tables:
            schema[table] = self.get_table_schema(table)
            
        return schema
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            
        Returns:
            Query results
        """
        self.connect()
        
        try:
            # Execute the query
            df = pd.read_sql_query(query, self.connection, params=params)
            
            # Prepare the result
            result = {
                "data": df.to_dict(orient="records"),
                "metadata": {
                    "row_count": len(df),
                    "columns": list(df.columns)
                }
            }
            
            return result
            
        except Exception as e:
            return {
                "error": str(e),
                "metadata": {
                    "row_count": 0,
                    "columns": []
                }
            }
    
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


# SQL query functions for the agent
def run_sql_query(query: str) -> str:
    """
    Run a SQL query against the ERP database.
    
    Args:
        query: SQL query to execute
        
    Returns:
        Query results as a formatted string
    """
    connector = SQLDatabaseConnector()
    result = connector.execute_query(query)
    
    if "error" in result:
        return f"Error executing query: {result['error']}"
    
    # Format the results as a table
    if result["metadata"]["row_count"] == 0:
        return "No results found."
    
    # Convert to DataFrame for easier formatting
    df = pd.DataFrame(result["data"])
    
    # Return formatted results
    return df.to_string(index=False)


def get_table_info(table_name: str = None) -> str:
    """
    Get information about database tables.
    
    Args:
        table_name: Optional name of a specific table
        
    Returns:
        Table information as a formatted string
    """
    connector = SQLDatabaseConnector()
    
    if table_name:
        # Get schema for a specific table
        schema = connector.get_table_schema(table_name)
        
        if not schema:
            return f"Table '{table_name}' not found."
        
        # Format the schema
        result = f"Table: {table_name}\n\n"
        result += "Columns:\n"
        
        for col in schema:
            pk_marker = " (PK)" if col["primary_key"] else ""
            result += f"- {col['name']}: {col['type']}{pk_marker}\n"
            
        # Get a sample of data
        sample_query = f"SELECT * FROM {table_name} LIMIT 5;"
        sample_result = connector.execute_query(sample_query)
        
        if "error" not in sample_result and sample_result["metadata"]["row_count"] > 0:
            result += "\nSample data:\n"
            df = pd.DataFrame(sample_result["data"])
            result += df.to_string(index=False)
            
        return result
    else:
        # Get all tables
        tables = connector.get_tables()
        
        if not tables:
            return "No tables found in the database."
        
        result = "Database Tables:\n\n"
        
        for table in tables:
            schema = connector.get_table_schema(table)
            result += f"Table: {table}\n"
            result += "Columns: " + ", ".join([col["name"] for col in schema]) + "\n\n"
            
        return result


def get_database_schema() -> str:
    """
    Get the complete database schema.
    
    Returns:
        Database schema as a formatted string
    """
    connector = SQLDatabaseConnector()
    schema = connector.get_database_schema()
    
    if not schema:
        return "No tables found in the database."
    
    result = "Database Schema:\n\n"
    
    for table_name, columns in schema.items():
        result += f"Table: {table_name}\n"
        result += "Columns:\n"
        
        for col in columns:
            pk_marker = " (PK)" if col["primary_key"] else ""
            result += f"- {col['name']}: {col['type']}{pk_marker}\n"
            
        result += "\n"
        
    return result