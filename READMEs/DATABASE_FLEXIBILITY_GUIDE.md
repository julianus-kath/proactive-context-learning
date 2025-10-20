# Database Flexibility Guide

## Current Flexibility

The LangGraph database agent is designed with flexibility in mind and can easily switch between different PostgreSQL databases by simply updating environment variables.

## Switching PostgreSQL Databases

### 1. Update Environment Variables
```bash
# .env file
DB_HOST=your-host
DB_PORT=5432
DB_NAME=your-database
DB_USER=your-user
DB_PASSWORD=your-password
```

### 2. Restart the Agent
The agent will automatically connect to the new database and discover its schema.

## Supported Database Operations

The agent uses standard SQL queries that work across most SQL databases:

### Schema Discovery
```sql
SELECT schema_name 
FROM information_schema.schemata 
WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
ORDER BY schema_name
```

### Table Discovery
```sql
SELECT table_name, table_type 
FROM information_schema.tables 
WHERE table_schema = 'schema_name' 
ORDER BY table_name
```

### Column Information
```sql
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_schema = 'schema_name' AND table_name = 'table_name'
ORDER BY ordinal_position
```

## Extending to Other SQL Databases

To support other SQL databases (MySQL, SQLite, SQL Server, etc.), you would need to:

### 1. Create Database Adapters

```python
# database_adapters.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class DatabaseAdapter(ABC):
    """Abstract base class for database adapters."""
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]):
        """Initialize database connection."""
        pass
    
    @abstractmethod
    async def fetch(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query."""
        pass
    
    @abstractmethod
    async def close(self):
        """Close database connection."""
        pass

class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL adapter using asyncpg."""
    
    def __init__(self):
        self.pool = None
    
    async def initialize(self, config: Dict[str, Any]):
        import asyncpg
        self.pool = await asyncpg.create_pool(**config)
    
    async def fetch(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            if params:
                rows = await conn.fetch(query, *params)
            else:
                rows = await conn.fetch(query)
            return [dict(row) for row in rows]
    
    async def close(self):
        if self.pool:
            await self.pool.close()

class MySQLAdapter(DatabaseAdapter):
    """MySQL adapter using aiomysql."""
    
    def __init__(self):
        self.pool = None
    
    async def initialize(self, config: Dict[str, Any]):
        import aiomysql
        self.pool = await aiomysql.create_pool(**config)
    
    async def fetch(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                return await cursor.fetchall()
    
    async def close(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

class SQLiteAdapter(DatabaseAdapter):
    """SQLite adapter using aiosqlite."""
    
    def __init__(self):
        self.connection = None
    
    async def initialize(self, config: Dict[str, Any]):
        import aiosqlite
        self.connection = await aiosqlite.connect(config['database'])
        self.connection.row_factory = aiosqlite.Row
    
    async def fetch(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        async with self.connection.execute(query, params or []) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def close(self):
        if self.connection:
            await self.connection.close()
```

### 2. Update Database Manager

```python
# Enhanced DatabaseManager
class DatabaseManager:
    """Database-agnostic manager."""
    
    def __init__(self):
        self.adapter = None
        self.db_type = os.getenv('DB_TYPE', 'postgresql').lower()
        self.db_config = self._get_config()
    
    def _get_config(self) -> Dict[str, Any]:
        """Get database configuration based on type."""
        if self.db_type == 'postgresql':
            return {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', '5432')),
                'database': os.getenv('DB_NAME', 'postgres'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', '')
            }
        elif self.db_type == 'mysql':
            return {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', '3306')),
                'db': os.getenv('DB_NAME', 'mysql'),
                'user': os.getenv('DB_USER', 'root'),
                'password': os.getenv('DB_PASSWORD', '')
            }
        elif self.db_type == 'sqlite':
            return {
                'database': os.getenv('DB_NAME', 'database.db')
            }
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    async def initialize(self):
        """Initialize the appropriate database adapter."""
        if self.db_type == 'postgresql':
            self.adapter = PostgreSQLAdapter()
        elif self.db_type == 'mysql':
            self.adapter = MySQLAdapter()
        elif self.db_type == 'sqlite':
            self.adapter = SQLiteAdapter()
        
        await self.adapter.initialize(self.db_config)
    
    async def fetch(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query."""
        return await self.adapter.fetch(query, params)
    
    async def close(self):
        """Close database connection."""
        if self.adapter:
            await self.adapter.close()
```

### 3. Database-Specific Schema Queries

```python
# schema_queries.py
class SchemaQueries:
    """Database-specific schema discovery queries."""
    
    @staticmethod
    def get_schemas_query(db_type: str) -> str:
        """Get query to discover schemas."""
        if db_type in ['postgresql', 'mysql']:
            return """
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys', 'pg_catalog', 'pg_toast')
            ORDER BY schema_name
            """
        elif db_type == 'sqlite':
            return "SELECT 'main' as schema_name"  # SQLite has no schemas
        
    @staticmethod
    def get_tables_query(db_type: str) -> str:
        """Get query to discover tables."""
        if db_type in ['postgresql', 'mysql']:
            return """
            SELECT table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            ORDER BY table_name
            """
        elif db_type == 'sqlite':
            return """
            SELECT name as table_name, 'BASE TABLE' as table_type 
            FROM sqlite_master 
            WHERE type = 'table' 
            ORDER BY name
            """
```

## Environment Configuration Examples

### PostgreSQL
```bash
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mywebshop
DB_USER=juli
DB_PASSWORD=
```

### MySQL
```bash
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_NAME=ecommerce
DB_USER=root
DB_PASSWORD=password
```

### SQLite
```bash
DB_TYPE=sqlite
DB_NAME=/path/to/database.db
```

### SQL Server
```bash
DB_TYPE=sqlserver
DB_HOST=localhost
DB_PORT=1433
DB_NAME=ECommerce
DB_USER=sa
DB_PASSWORD=password
```

## Benefits of This Approach

1. **Easy Switching**: Change database by updating environment variables
2. **Automatic Discovery**: Agent automatically discovers schema regardless of database type
3. **Standard SQL**: Uses standard SQL queries that work across databases
4. **Extensible**: Easy to add support for new database types
5. **Configuration-Driven**: No code changes needed to switch databases

## Current Status

✅ **Fully Flexible for PostgreSQL**: Can switch between any PostgreSQL databases
✅ **Standard SQL Queries**: Uses portable SQL for schema discovery
✅ **Environment-Based Config**: Easy configuration management
⚠️ **PostgreSQL-Specific**: Currently uses asyncpg (PostgreSQL-only)

## Recommendation

The current system is already very flexible for PostgreSQL databases. If you need support for other SQL databases, implementing the adapter pattern above would provide full database flexibility while maintaining the same agent interface.