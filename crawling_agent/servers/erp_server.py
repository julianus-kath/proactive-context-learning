"""
MCP Server for ERP data source.
Exposes SQL query capabilities through the MCP protocol.
"""
import time
import sqlite3
import pandas as pd
from typing import Dict, Any, List, Optional
import os
import json

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
            # Use the synthetic_data.db file
            db_path = "/app/synthetic_data.db"
            
            # Check if the file exists
            if not os.path.exists(db_path):
                self.logger.error(f"Database file {db_path} not found.")
                raise FileNotFoundError(f"Database file {db_path} not found. Please ensure the database file exists.")
            
            self.connection = sqlite3.connect(db_path)
            self.logger.info(f"Connected to SQLite database at {db_path}")
            
            # Log the tables in the database for debugging
            cursor = self.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            self.logger.info(f"Tables in the database: {tables}")
        except Exception as e:
            self.logger.error(f"Error connecting to ERP database: {str(e)}")
            raise
    
    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """
        Execute a SQL query against the ERP database.
        
        Args:
            request: The query request
            
        Returns:
            Query response with results
        """
        if request.query_type != "SQL":
            error_msg = f"Invalid query type for ERP server: {request.query_type}"
            self.logger.error(error_msg)
            return QueryResponse(
                request_id=request.request_id,
                status="error",
                error=error_msg
            )
        
        self._connect()
        
        start_time = time.time()
        self.logger.info(f"Starting query execution (request_id: {request.request_id})")
        self.logger.info(f"Query: {request.query}")
        
        if request.parameters:
            self.logger.info(f"Parameters: {json.dumps(request.parameters, indent=2)}")
        
        try:
            self.logger.info("Executing SQL query using pandas")
            
            # Execute the query
            df = pd.read_sql_query(request.query, self.connection, params=request.parameters)
            
            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            
            # Log query statistics
            self.logger.info(f"Query execution completed in {execution_time:.2f}ms")
            self.logger.info(f"Retrieved {len(df)} rows")
            
            if not df.empty:
                # Log column information
                self.logger.info("Column information:")
                for col in df.columns:
                    self.logger.info(f"  - {col} ({df[col].dtype})")
                
                # Log a sample of the data (first few rows)
                self.logger.info("Sample data (first row):")
                self.logger.info(df.iloc[0].to_dict())
            
            # Prepare the result
            result = QueryResponse(
                request_id=request.request_id,
                data=df.to_dict(orient="records"),
                metadata={
                    "row_count": len(df),
                    "columns": list(df.columns),
                    "column_types": {col: str(df[col].dtype) for col in df.columns},
                    "execution_time_ms": execution_time
                },
                status="success"
            )
            
            self.logger.info(f"Query executed successfully. Retrieved {len(df)} rows in {execution_time:.2f}ms")
            self.logger.debug(f"Full metadata: {json.dumps(result.metadata, indent=2)}")
            
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error_msg = str(e)
            self.logger.error(f"Error executing SQL query after {execution_time:.2f}ms: {error_msg}")
            self.logger.error(f"Failed query: {request.query}")
            if request.parameters:
                self.logger.error(f"Failed query parameters: {json.dumps(request.parameters, indent=2)}")
            
            return QueryResponse(
                request_id=request.request_id,
                status="error",
                error=error_msg,
                metadata={
                    "execution_time_ms": execution_time,
                    "error_type": type(e).__name__
                }
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