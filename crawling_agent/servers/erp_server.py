"""
ERP Server implementation using MCP.
"""
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from crawling_agent.base_server import BaseMCPServer
from crawling_agent.custom_resource import CustomResource
from fastmcp.resources import Resource


class ERPServer(BaseMCPServer):
    """
    ERP Server that exposes SQL query tools over MCP.
    
    This server connects to a SQLite database and provides tools to query it.
    """

    def __init__(
        self,
        db_path: str,
        host: str = "0.0.0.0",
        port: int = 8001,
    ):
        """
        Initialize the ERP Server.

        Args:
            db_path: Path to the SQLite database
            host: Host to bind to (default: "0.0.0.0")
            port: Port to listen on (default: 8001)
        """
        super().__init__(
            name="ERPServer",
            host=host,
            port=port,
            description="ERP Server providing SQL query capabilities over MCP",
        )
        
        self.db_path = db_path
        
        # Register resources
        self._register_resources()
        
        # Register tools
        self._register_tools()
    
    def _register_resources(self):
        """Register resources with the MCP server."""
        # Load the schema from the JSON file
        schema_path = os.path.join(
            os.path.dirname(__file__), 
            "resources", 
            "erp_schema.json"
        )
        
        with open(schema_path, "r") as f:
            schema = json.load(f)
        
        # Create the resource
        erp_resource = CustomResource(
            name="erp_database",
            description="ERP database schema and metadata",
            schema=schema,
        )
        
        # Register the resource with the MCP server
        self.mcp.add_resource(erp_resource)
        
        # Populate the resource with actual database metadata
        self._populate_resource(erp_resource)
    
    def _populate_resource(self, resource: Resource):
        """
        Populate the resource with actual database metadata.
        
        Args:
            resource: The resource to populate
        """
        # Connect to the database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get the list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        # Prepare the tables data
        tables_data = []
        
        for table in tables:
            table_name = table[0]
            
            # Get the columns for this table
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns_info = cursor.fetchall()
            
            columns = []
            for col in columns_info:
                # col structure: (cid, name, type, notnull, dflt_value, pk)
                columns.append({
                    "name": col[1],
                    "type": col[2],
                    "description": f"Column {col[1]} of type {col[2]} in table {table_name}"
                })
            
            tables_data.append({
                "name": table_name,
                "columns": columns
            })
        
        # Update the resource with the tables data
        resource.update({"tables": tables_data})
        
        # Close the connection
        conn.close()
    
    def _register_tools(self):
        """Register tools with the MCP server."""
        
        @self.mcp.tool()
        def execute_sql_query(query: str) -> str:
            """
            Execute a SQL query against the ERP database.
            
            Args:
                query: The SQL query to execute
                
            Returns:
                The query results as a JSON string
            """
            try:
                # Connect to the database
                conn = sqlite3.connect(self.db_path)
                
                # Execute the query and get the results as a DataFrame
                df = pd.read_sql_query(query, conn)
                
                # Convert the DataFrame to a JSON string
                result = df.to_json(orient="records")
                
                # Close the connection
                conn.close()
                
                return result
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        @self.mcp.tool()
        def get_table_schema(table_name: str) -> str:
            """
            Get the schema for a specific table.
            
            Args:
                table_name: The name of the table
                
            Returns:
                The table schema as a JSON string
            """
            try:
                # Connect to the database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Get the columns for this table
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns_info = cursor.fetchall()
                
                columns = []
                for col in columns_info:
                    # col structure: (cid, name, type, notnull, dflt_value, pk)
                    columns.append({
                        "name": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "default_value": col[4],
                        "primary_key": bool(col[5])
                    })
                
                # Close the connection
                conn.close()
                
                return json.dumps({"table": table_name, "columns": columns})
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        @self.mcp.tool()
        def list_tables() -> str:
            """
            List all tables in the ERP database.
            
            Returns:
                A JSON string containing the list of tables
            """
            try:
                # Connect to the database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Get the list of tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                # Extract the table names
                table_names = [table[0] for table in tables]
                
                # Close the connection
                conn.close()
                
                return json.dumps({"tables": table_names})
            except Exception as e:
                return json.dumps({"error": str(e)})


if __name__ == "__main__":
    # Path to the SQLite database
    db_path = "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/synthetic_data.db"
    
    # Create and run the server
    server = ERPServer(db_path=db_path)
    server.run(transport="sse")