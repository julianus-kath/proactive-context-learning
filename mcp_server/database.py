"""
Database connection and query utilities for the MCP server.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import json
from datetime import datetime, date
from decimal import Decimal

from .config import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections and queries for the MCP server."""
    
    def __init__(self):
        """Initialize the database manager."""
        self.engine = create_engine(
            config.connection_string,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.metadata = MetaData()
        self._load_schema()
    
    def _load_schema(self):
        """Load database schema information."""
        try:
            self.metadata.reflect(bind=self.engine)
            logger.info(f"Loaded schema with {len(self.metadata.tables)} tables")
        except Exception as e:
            logger.error(f"Failed to load database schema: {e}")
            raise
    
    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()
    
    def get_table_info(self) -> Dict[str, Any]:
        """Get information about all tables in the database."""
        tables_info = {}
        
        for table_name, table in self.metadata.tables.items():
            columns_info = []
            for column in table.columns:
                column_info = {
                    "name": column.name,
                    "type": str(column.type),
                    "nullable": column.nullable,
                    "primary_key": column.primary_key,
                    "foreign_key": bool(column.foreign_keys)
                }
                if column.foreign_keys:
                    fk = list(column.foreign_keys)[0]
                    column_info["references"] = f"{fk.column.table.name}.{fk.column.name}"
                columns_info.append(column_info)
            
            tables_info[table_name] = {
                "columns": columns_info,
                "row_count": self._get_table_row_count(table_name)
            }
        
        return tables_info
    
    def _get_table_row_count(self, table_name: str) -> int:
        """Get the number of rows in a table."""
        try:
            with self.get_session() as session:
                result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                return result.scalar()
        except Exception as e:
            logger.warning(f"Could not get row count for {table_name}: {e}")
            return 0
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a SQL query and return results.
        
        Args:
            query: SQL query string
            params: Optional query parameters
            
        Returns:
            Dictionary with query results and metadata
        """
        try:
            with self.get_session() as session:
                # Execute the query
                if params:
                    result = session.execute(text(query), params)
                else:
                    result = session.execute(text(query))
                
                # Handle different types of queries
                if result.returns_rows:
                    # SELECT query
                    rows = result.fetchmany(config.max_query_results)
                    columns = list(result.keys())
                    
                    # Convert rows to dictionaries with JSON-serializable values
                    data = []
                    for row in rows:
                        row_dict = {}
                        for i, value in enumerate(row):
                            row_dict[columns[i]] = self._serialize_value(value)
                        data.append(row_dict)
                    
                    return {
                        "type": "select",
                        "columns": columns,
                        "data": data,
                        "row_count": len(data),
                        "truncated": len(data) >= config.max_query_results
                    }
                else:
                    # INSERT, UPDATE, DELETE, etc.
                    session.commit()
                    return {
                        "type": "modification",
                        "rows_affected": result.rowcount,
                        "message": f"Query executed successfully. {result.rowcount} rows affected."
                    }
                    
        except SQLAlchemyError as e:
            logger.error(f"Database error executing query: {e}")
            return {
                "type": "error",
                "error": str(e),
                "message": "Database error occurred while executing query"
            }
        except Exception as e:
            logger.error(f"Unexpected error executing query: {e}")
            return {
                "type": "error",
                "error": str(e),
                "message": "Unexpected error occurred while executing query"
            }
    
    def _serialize_value(self, value: Any) -> Any:
        """Convert database values to JSON-serializable format."""
        if value is None:
            return None
        elif isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, (bytes, bytearray)):
            return value.decode('utf-8', errors='ignore')
        else:
            return value
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> Dict[str, Any]:
        """Get sample data from a table."""
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        return self.execute_query(query)
    
    def search_tables(self, search_term: str) -> List[str]:
        """Search for tables containing the search term."""
        matching_tables = []
        search_term_lower = search_term.lower()
        
        for table_name in self.metadata.tables.keys():
            if search_term_lower in table_name.lower():
                matching_tables.append(table_name)
        
        return matching_tables
    
    def get_table_relationships(self) -> Dict[str, List[Dict[str, str]]]:
        """Get foreign key relationships between tables."""
        relationships = {}
        
        for table_name, table in self.metadata.tables.items():
            table_relationships = []
            
            for column in table.columns:
                if column.foreign_keys:
                    for fk in column.foreign_keys:
                        table_relationships.append({
                            "column": column.name,
                            "references_table": fk.column.table.name,
                            "references_column": fk.column.name
                        })
            
            if table_relationships:
                relationships[table_name] = table_relationships
        
        return relationships

# Global database manager instance
db_manager = DatabaseManager()