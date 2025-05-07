"""
ERP API service for the crawling agent.
Provides a REST API for querying the ERP database.
"""
import os
import time
import sqlite3
import pandas as pd
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    """Model for SQL query requests."""
    sql: str = Field(..., description="The SQL query to execute")
    parameters: Dict[str, Any] = Field(default={}, description="Query parameters")


class QueryResponse(BaseModel):
    """Model for query responses."""
    data: List[Dict[str, Any]] = Field(default=[], description="The query results as a list of records")
    metadata: Dict[str, Any] = Field(default={}, description="Metadata about the query execution")
    status: str = Field(default="success", description="Status of the query execution")
    error: Optional[str] = Field(default=None, description="Error message if the query failed")


class TableSchema(BaseModel):
    """Model for table schema information."""
    name: str = Field(..., description="Table name")
    columns: List[Dict[str, Any]] = Field(..., description="Column information")


class DatabaseMetadata(BaseModel):
    """Model for database metadata."""
    tables: List[TableSchema] = Field(..., description="List of tables in the database")


class ERPAPIService:
    """
    ERP API service for the crawling agent.
    Provides a REST API for querying the ERP database.
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8001,
        db_path: Optional[str] = None
    ):
        """
        Initialize the ERP API service.
        
        Args:
            host: Host to bind the server to
            port: Port to bind the server to
            db_path: Path to the SQLite database file
        """
        self.host = host
        self.port = port
        
        # Use the provided database path or default to the synthetic_data.db file
        self.db_path = db_path or os.environ.get("SQL_DB_PATH", "/app/synthetic_data.db")
        
        # Initialize the connection to None, will be created when needed
        self.connection = None
        
        # Create the FastAPI app
        self.app = FastAPI(
            title="ERP API Service",
            description="REST API for querying the ERP database",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json"
        )
        
        # Register routes
        self._register_routes()
        
        logger.info(f"Initialized ERP API service on {host}:{port} with database at {self.db_path}")
    
    def _register_routes(self):
        """Register API routes."""
        
        @self.app.get("/", tags=["General"])
        async def root():
            """Root endpoint that returns basic server information."""
            return {
                "service": "ERP API Service",
                "version": "1.0.0",
                "status": "online"
            }
        
        @self.app.get("/health", tags=["General"])
        async def health_check():
            """Health check endpoint."""
            try:
                self._connect()
                return {"status": "healthy", "database": "connected"}
            except Exception as e:
                logger.error(f"Health check failed: {str(e)}")
                return {"status": "unhealthy", "error": str(e)}
        
        @self.app.get("/metadata", tags=["Metadata"], response_model=DatabaseMetadata)
        async def get_metadata():
            """Get metadata about the database (tables and columns)."""
            try:
                self._connect()
                
                # Get list of tables
                cursor = self.connection.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                
                # Get schema for each table
                table_schemas = []
                for table_name in tables:
                    cursor.execute(f"PRAGMA table_info({table_name});")
                    columns = cursor.fetchall()
                    
                    column_info = [
                        {
                            "name": col[1],
                            "type": col[2],
                            "notnull": bool(col[3]),
                            "default_value": col[4],
                            "primary_key": bool(col[5])
                        }
                        for col in columns
                    ]
                    
                    table_schemas.append(
                        TableSchema(
                            name=table_name,
                            columns=column_info
                        )
                    )
                
                return DatabaseMetadata(tables=table_schemas)
                
            except Exception as e:
                logger.error(f"Error getting metadata: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/query", tags=["Query"], response_model=QueryResponse)
        async def execute_query(request: QueryRequest):
            """Execute a SQL query against the database."""
            try:
                self._connect()
                
                start_time = time.time()
                logger.info(f"Executing SQL query: {request.sql}")
                
                # Execute the query
                df = pd.read_sql_query(request.sql, self.connection, params=request.parameters)
                
                # Calculate execution time
                execution_time = (time.time() - start_time) * 1000  # in milliseconds
                
                # Log query statistics
                logger.info(f"Query execution completed in {execution_time:.2f}ms")
                logger.info(f"Retrieved {len(df)} rows")
                
                if not df.empty:
                    # Log column information
                    logger.info("Column information:")
                    for col in df.columns:
                        logger.info(f"  - {col} ({df[col].dtype})")
                    
                    # Log a sample of the data (first row)
                    logger.info("Sample data (first row):")
                    logger.info(df.iloc[0].to_dict())
                
                # Prepare the result
                result = QueryResponse(
                    data=df.to_dict(orient="records"),
                    metadata={
                        "row_count": len(df),
                        "columns": list(df.columns),
                        "column_types": {col: str(df[col].dtype) for col in df.columns},
                        "execution_time_ms": execution_time
                    },
                    status="success"
                )
                
                return result
                
            except Exception as e:
                logger.error(f"Error executing SQL query: {str(e)}")
                return QueryResponse(
                    status="error",
                    error=str(e),
                    metadata={
                        "error_type": type(e).__name__
                    }
                )
    
    def _connect(self):
        """Establish a connection to the ERP database."""
        if self.connection is not None:
            return
        
        try:
            # Check if the file exists
            if not os.path.exists(self.db_path):
                logger.error(f"Database file {self.db_path} not found.")
                raise FileNotFoundError(f"Database file {self.db_path} not found. Please ensure the database file exists.")
            
            self.connection = sqlite3.connect(self.db_path)
            logger.info(f"Connected to SQLite database at {self.db_path}")
            
            # Log the tables in the database for debugging
            cursor = self.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"Tables in the database: {tables}")
        except Exception as e:
            logger.error(f"Error connecting to ERP database: {str(e)}")
            raise
    
    def run(self):
        """Run the ERP API service."""
        logger.info(f"Starting ERP API service on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port)


def main():
    """Run the ERP API service."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ERP API Service")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind the server to")
    parser.add_argument("--db-path", type=str, help="Path to the SQLite database file")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    service = ERPAPIService(
        host=args.host,
        port=args.port,
        db_path=args.db_path
    )
    
    service.run()


if __name__ == "__main__":
    main()