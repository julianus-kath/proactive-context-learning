"""
Test client for the MCP server.
"""

import asyncio
import json
import logging
from typing import Any, Dict
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPTestClient:
    """Test client for the MCP server."""
    
    def __init__(self):
        self.session = None
    
    async def connect(self):
        """Connect to the MCP server."""
        try:
            # Start the server process
            import subprocess
            import sys
            
            server_process = subprocess.Popen([
                sys.executable, "-m", "mcp_server.server"
            ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Create client session
            read_stream, write_stream = stdio_client(server_process)
            self.session = ClientSession(read_stream, write_stream)
            
            # Initialize the session
            await self.session.initialize()
            logger.info("Connected to MCP server successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise
    
    async def list_resources(self):
        """List available resources."""
        try:
            resources = await self.session.list_resources()
            print("\n📚 Available Resources:")
            print("=" * 50)
            for resource in resources:
                print(f"URI: {resource.uri}")
                print(f"Name: {resource.name}")
                print(f"Description: {resource.description}")
                print(f"MIME Type: {resource.mimeType}")
                print("-" * 30)
            return resources
        except Exception as e:
            logger.error(f"Error listing resources: {e}")
            return []
    
    async def read_resource(self, uri: str):
        """Read a specific resource."""
        try:
            content = await self.session.read_resource(uri)
            print(f"\n📖 Resource Content ({uri}):")
            print("=" * 50)
            print(content)
            return content
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            return None
    
    async def list_tools(self):
        """List available tools."""
        try:
            tools = await self.session.list_tools()
            print("\n🔧 Available Tools:")
            print("=" * 50)
            for tool in tools:
                print(f"Name: {tool.name}")
                print(f"Description: {tool.description}")
                print(f"Input Schema: {json.dumps(tool.inputSchema, indent=2)}")
                print("-" * 30)
            return tools
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return []
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]):
        """Call a specific tool."""
        try:
            result = await self.session.call_tool(name, arguments)
            print(f"\n🛠️ Tool Result ({name}):")
            print("=" * 50)
            for content in result:
                if hasattr(content, 'text'):
                    print(content.text)
                else:
                    print(str(content))
            return result
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            return None
    
    async def run_tests(self):
        """Run a comprehensive test suite."""
        print("🚀 Starting MCP Server Test Suite")
        print("=" * 60)
        
        # Test 1: List resources
        print("\n🧪 Test 1: List Resources")
        resources = await self.list_resources()
        
        # Test 2: Read database schema
        print("\n🧪 Test 2: Read Database Schema")
        await self.read_resource("schema://database")
        
        # Test 3: List tools
        print("\n🧪 Test 3: List Tools")
        tools = await self.list_tools()
        
        # Test 4: Search for tables
        print("\n🧪 Test 4: Search Tables")
        await self.call_tool("search_tables", {"search_term": "customer"})
        
        # Test 5: Get table info
        print("\n🧪 Test 5: Get Table Info")
        await self.call_tool("get_table_info", {"table_name": "customers"})
        
        # Test 6: Get sample data
        print("\n🧪 Test 6: Get Sample Data")
        await self.call_tool("get_sample_data", {"table_name": "customers", "limit": 3})
        
        # Test 7: Execute SQL query
        print("\n🧪 Test 7: Execute SQL Query")
        await self.call_tool("execute_sql_query", {
            "query": "SELECT COUNT(*) as total_customers FROM customers WHERE is_active = true"
        })
        
        # Test 8: Complex query with joins
        print("\n🧪 Test 8: Complex Query with Joins")
        await self.call_tool("execute_sql_query", {
            "query": """
                SELECT 
                    c.name as customer_name,
                    c.industry,
                    COUNT(s.sale_id) as total_orders,
                    SUM(s.total_amount) as total_revenue
                FROM customers c
                LEFT JOIN sales s ON c.customer_id = s.customer_id
                WHERE c.is_active = true
                GROUP BY c.customer_id, c.name, c.industry
                ORDER BY total_revenue DESC
                LIMIT 5
            """
        })
        
        # Test 9: Query performance analysis
        print("\n🧪 Test 9: Query Performance Analysis")
        await self.call_tool("analyze_query_performance", {
            "query": "SELECT * FROM sales WHERE sale_date >= '2024-01-01' ORDER BY total_amount DESC LIMIT 10"
        })
        
        print("\n✅ Test Suite Completed!")
    
    async def interactive_mode(self):
        """Run in interactive mode for manual testing."""
        print("\n🎮 Interactive Mode - Enter SQL queries (type 'exit' to quit)")
        print("=" * 60)
        
        while True:
            try:
                query = input("\nSQL> ").strip()
                
                if query.lower() in ['exit', 'quit', 'q']:
                    break
                
                if not query:
                    continue
                
                if query.startswith('\\'):
                    # Handle special commands
                    if query == '\\tables':
                        await self.call_tool("search_tables", {"search_term": ""})
                    elif query.startswith('\\desc '):
                        table_name = query[6:].strip()
                        await self.call_tool("get_table_info", {"table_name": table_name})
                    elif query.startswith('\\sample '):
                        table_name = query[8:].strip()
                        await self.call_tool("get_sample_data", {"table_name": table_name, "limit": 5})
                    else:
                        print("Available commands:")
                        print("  \\tables - List all tables")
                        print("  \\desc <table> - Describe table structure")
                        print("  \\sample <table> - Show sample data")
                else:
                    # Execute SQL query
                    await self.call_tool("execute_sql_query", {"query": query})
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
        
        print("\nGoodbye! 👋")

async def main():
    """Main test function."""
    client = MCPTestClient()
    
    try:
        await client.connect()
        
        # Run automated tests
        await client.run_tests()
        
        # Ask if user wants interactive mode
        response = input("\n🎮 Would you like to enter interactive mode? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            await client.interactive_mode()
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())