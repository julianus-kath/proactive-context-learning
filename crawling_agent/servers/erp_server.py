"""
MCP Server for ERP data source.
Exposes SQL query capabilities through the MCP protocol.
"""
import time
import sqlite3
import pandas as pd
from typing import Dict, Any, List, Optional
import os

from crawling_agent.servers.base_server import BaseMCPServer, QueryRequest, QueryResponse


class ERPServer(BaseMCPServer):
    """
    MCP Server for ERP data source.
    Provides SQL query capabilities.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8001,
        config_path: Optional[str] = None,
        mock_mode: bool = False
    ):
        """
        Initialize the ERP MCP server.
        
        Args:
            host: Host to bind the server to
            port: Port to bind the server to
            config_path: Path to the configuration file
            mock_mode: Whether to run in mock mode
        """
        super().__init__(
            server_type="ERP",
            version="1.0.0",
            host=host,
            port=port,
            config_path=config_path
        )
        
        self.mock_mode = mock_mode
        self.connection = None
        
        # Register additional routes
        self._register_additional_routes()
    
    def _register_additional_routes(self):
        """Register additional API routes specific to ERP server."""
        
        @self.app.get("/tables", tags=["ERP"])
        async def get_tables():
            """Get list of tables in the ERP database."""
            try:
                self._connect()
                cursor = self.connection.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                return {"tables": tables}
            except Exception as e:
                self.logger.error(f"Error getting tables: {str(e)}")
                return {"error": str(e)}
            finally:
                # Keep connection open for future queries
                pass
        
        @self.app.get("/schema/{table_name}", tags=["ERP"])
        async def get_table_schema(table_name: str):
            """Get schema for a specific table."""
            try:
                self._connect()
                cursor = self.connection.cursor()
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()
                schema = [
                    {
                        "cid": col[0],
                        "name": col[1],
                        "type": col[2],
                        "notnull": col[3],
                        "default_value": col[4],
                        "pk": col[5]
                    }
                    for col in columns
                ]
                return {"table": table_name, "schema": schema}
            except Exception as e:
                self.logger.error(f"Error getting schema for table {table_name}: {str(e)}")
                return {"error": str(e)}
            finally:
                # Keep connection open for future queries
                pass
    
    def get_capabilities(self) -> List[str]:
        """
        Get server capabilities.
        
        Returns:
            List of capability strings
        """
        return ["query", "schema", "tables"]
    
    def get_query_types(self) -> List[str]:
        """
        Get supported query types.
        
        Returns:
            List of supported query type strings
        """
        return ["SQL"]
    
    def _connect(self):
        """Establish a connection to the ERP database."""
        if self.connection is not None:
            return
        
        try:
            if self.mock_mode:
                # Use in-memory database for mock mode
                self.connection = sqlite3.connect(":memory:")
                self._setup_mock_database()
                self.logger.info("Connected to in-memory SQLite database (mock mode)")
            else:
                # Use configured database
                db_uri = self.config['data_sources']['erp']['uri']
                self.logger.info(f"Connecting to ERP database: {db_uri}")
                
                # For SQLite, extract the path from the URI
                if db_uri.startswith('sqlite:///'):
                    db_path = db_uri[10:]
                    self.connection = sqlite3.connect(db_path)
                    self.logger.info(f"Connected to SQLite database at {db_path}")
                else:
                    # For other database types, you would use appropriate drivers
                    raise NotImplementedError(f"Database driver for {db_uri} not implemented")
        except Exception as e:
            self.logger.error(f"Error connecting to ERP database: {str(e)}")
            raise
    
    def _setup_mock_database(self):
        """Set up mock database with sample data."""
        cursor = self.connection.cursor()
        
        # Create products table
        cursor.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            category TEXT,
            stock INTEGER DEFAULT 0
        )
        ''')
        
        # Insert sample products
        products = [
            (1, 'Expensive Product 1', 'A very expensive product', 150.0, 'Electronics', 10),
            (2, 'Expensive Product 2', 'Another expensive product', 200.0, 'Electronics', 5),
            (3, 'Budget Product 1', 'An affordable product', 50.0, 'Home', 20),
            (4, 'Budget Product 2', 'Another affordable product', 75.0, 'Home', 15),
            (5, 'Premium Service', 'A premium service offering', 300.0, 'Services', 0)
        ]
        cursor.executemany('INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)', products)
        
        # Create employees table
        cursor.execute('''
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT,
            position TEXT,
            salary REAL,
            hire_date TEXT
        )
        ''')
        
        # Insert sample employees
        employees = [
            (1, 'John Doe', 'Sales', 'Manager', 75000.0, '2020-01-15'),
            (2, 'Jane Smith', 'Sales', 'Associate', 50000.0, '2021-03-10'),
            (3, 'Bob Johnson', 'Engineering', 'Senior Engineer', 90000.0, '2019-05-22'),
            (4, 'Alice Brown', 'Engineering', 'Engineer', 70000.0, '2022-02-18'),
            (5, 'Charlie Wilson', 'Marketing', 'Director', 85000.0, '2018-11-30')
        ]
        cursor.executemany('INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?)', employees)
        
        # Create orders table
        cursor.execute('''
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            order_date TEXT,
            total_amount REAL,
            status TEXT
        )
        ''')
        
        # Insert sample orders
        orders = [
            (1, 101, '2023-01-10', 350.0, 'Completed'),
            (2, 102, '2023-01-15', 200.0, 'Completed'),
            (3, 103, '2023-02-05', 150.0, 'Processing'),
            (4, 101, '2023-02-20', 75.0, 'Completed'),
            (5, 104, '2023-03-01', 500.0, 'Processing')
        ]
        cursor.executemany('INSERT INTO orders VALUES (?, ?, ?, ?, ?)', orders)
        
        # Create order_items table
        cursor.execute('''
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            price REAL
        )
        ''')
        
        # Insert sample order items
        order_items = [
            (1, 1, 1, 2, 150.0),
            (2, 1, 3, 1, 50.0),
            (3, 2, 2, 1, 200.0),
            (4, 3, 1, 1, 150.0),
            (5, 4, 3, 1, 50.0),
            (6, 4, 4, 1, 25.0),
            (7, 5, 2, 1, 200.0),
            (8, 5, 5, 1, 300.0)
        ]
        cursor.executemany('INSERT INTO order_items VALUES (?, ?, ?, ?, ?)', order_items)
        
        # Commit the changes
        self.connection.commit()
    
    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """
        Execute a SQL query against the ERP database.
        
        Args:
            request: The query request
            
        Returns:
            Query response with results
        """
        if request.query_type != "SQL":
            return QueryResponse(
                request_id=request.request_id,
                status="error",
                error=f"Invalid query type for ERP server: {request.query_type}"
            )
        
        self._connect()
        
        start_time = time.time()
        
        try:
            self.logger.info(f"Executing SQL query: {request.query}")
            self.logger.debug(f"Query parameters: {request.parameters}")
            
            # Execute the query
            df = pd.read_sql_query(request.query, self.connection, params=request.parameters)
            
            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            
            # Prepare the result
            result = QueryResponse(
                request_id=request.request_id,
                data=df.to_dict(orient="records"),
                metadata={
                    "row_count": len(df),
                    "columns": list(df.columns),
                    "execution_time_ms": execution_time
                },
                status="success"
            )
            
            self.logger.info(f"Query executed successfully. Retrieved {len(df)} rows in {execution_time:.2f}ms")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing SQL query: {str(e)}")
            return QueryResponse(
                request_id=request.request_id,
                status="error",
                error=str(e)
            )


def main():
    """Run the ERP MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ERP MCP Server")
    parser.add_argument("--host", type=str, default="localhost", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind the server to")
    parser.add_argument("--config", type=str, help="Path to the configuration file")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    
    args = parser.parse_args()
    
    server = ERPServer(
        host=args.host,
        port=args.port,
        config_path=args.config,
        mock_mode=args.mock
    )
    
    server.run()


if __name__ == "__main__":
    main()