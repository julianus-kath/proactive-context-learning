"""
Database connection and operations using asyncpg.
"""

import asyncpg
import logging
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages PostgreSQL connections and operations."""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'database': os.getenv('DB_NAME', 'synthetic_erp_data'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres')
        }
    
    async def initialize(self):
        """Initialize the database connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                **self.db_config,
                min_size=5,
                max_size=20,
                command_timeout=30
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    async def close(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    async def fetch_schema(self) -> List[Dict[str, Any]]:
        """Fetch database schema information."""
        query = """
        SELECT 
            t.table_name,
            t.table_type,
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.column_default,
            tc.constraint_type
        FROM information_schema.tables t
        LEFT JOIN information_schema.columns c ON t.table_name = c.table_name
        LEFT JOIN information_schema.table_constraints tc ON t.table_name = tc.table_name 
            AND c.column_name = ANY(
                SELECT column_name 
                FROM information_schema.key_column_usage 
                WHERE constraint_name = tc.constraint_name
            )
        WHERE t.table_schema = 'public'
        ORDER BY t.table_name, c.ordinal_position;
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            
            # Group by table
            tables = {}
            for row in rows:
                table_name = row['table_name']
                if table_name not in tables:
                    tables[table_name] = {
                        'name': table_name,
                        'type': row['table_type'],
                        'columns': []
                    }
                
                if row['column_name']:  # Some tables might not have columns in result
                    column_info = {
                        'name': row['column_name'],
                        'type': row['data_type'],
                        'nullable': row['is_nullable'] == 'YES',
                        'default': row['column_default']
                    }
                    
                    if row['constraint_type']:
                        column_info['constraint'] = row['constraint_type']
                    
                    tables[table_name]['columns'].append(column_info)
            
            return list(tables.values())
    
    async def fetch(self, query: str, params: Optional[List[Any]] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results."""
        # Security: Only allow SELECT queries
        query_stripped = query.strip().upper()
        if not query_stripped.startswith('SELECT'):
            raise ValueError("Only SELECT queries are allowed")
        
        # Add LIMIT if not present
        if 'LIMIT' not in query_stripped:
            # Remove trailing semicolon if present
            query = query.rstrip(';').strip()
            query += f" LIMIT {limit}"
        
        async with self.pool.acquire() as conn:
            try:
                if params:
                    rows = await conn.fetch(query, *params)
                else:
                    rows = await conn.fetch(query)
                
                # Convert to list of dictionaries
                result = []
                for row in rows:
                    row_dict = {}
                    for key, value in row.items():
                        # Handle special types that aren't JSON serializable
                        if hasattr(value, 'isoformat'):  # datetime objects
                            row_dict[key] = value.isoformat()
                        elif isinstance(value, (bytes, bytearray)):
                            row_dict[key] = value.decode('utf-8', errors='ignore')
                        else:
                            row_dict[key] = value
                    result.append(row_dict)
                
                return result
                
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                raise
    
    async def get_table_count(self, table_name: str) -> int:
        """Get the number of rows in a table."""
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        result = await self.fetch(query)
        return result[0]['count'] if result else 0
    
    async def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample data from a table."""
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        return await self.fetch(query)


# Global database manager instance
db_manager = DatabaseManager()