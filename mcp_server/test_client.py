"""
Test client for the MCP server.
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPTestClient:
    """Test client for MCP server."""
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = "supersecretapikey"):
        self.base_url = base_url
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_id = 0
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _get_next_id(self) -> int:
        """Get next request ID."""
        self.request_id += 1
        return self.request_id
    
    async def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a JSON-RPC request to the MCP server."""
        request_data = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self._get_next_id()
        }
        
        if params:
            request_data["params"] = params
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with self.session.post(
            f"{self.base_url}/mcp",
            json=request_data,
            headers=headers
        ) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}: {await response.text()}")
            
            return await response.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check server health."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with self.session.get(f"{self.base_url}/health", headers=headers) as response:
            return await response.json()
    
    async def initialize(self) -> Dict[str, Any]:
        """Initialize MCP session."""
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
        return await self._make_request("initialize", params)
    
    async def list_tools(self) -> Dict[str, Any]:
        """List available tools."""
        return await self._make_request("list_tools")
    
    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call a specific tool."""
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments
        return await self._make_request("call_tool", params)
    
    async def run_comprehensive_test(self):
        """Run comprehensive test suite."""
        print("🚀 Starting MCP Server Test Suite")
        print("=" * 60)
        
        try:
            # Test 1: Health check
            print("\n🧪 Test 1: Health Check")
            health = await self.health_check()
            print(f"Health Status: {health}")
            
            # Test 2: Initialize
            print("\n🧪 Test 2: Initialize MCP Session")
            init_response = await self.initialize()
            print(f"Initialize Response: {json.dumps(init_response, indent=2)}")
            
            # Test 3: List tools
            print("\n🧪 Test 3: List Available Tools")
            tools_response = await self.list_tools()
            print(f"Available Tools: {json.dumps(tools_response, indent=2)}")
            
            # Test 4: Get schema
            print("\n🧪 Test 4: Get Database Schema")
            schema_response = await self.call_tool("get_schema")
            print(f"Schema Response: {json.dumps(schema_response, indent=2)}")
            
            # Test 5: Get table info
            print("\n🧪 Test 5: Get Table Info")
            table_info_response = await self.call_tool("get_table_info", {"table_name": "customers"})
            print(f"Table Info Response: {json.dumps(table_info_response, indent=2)}")
            
            # Test 6: Get sample data
            print("\n🧪 Test 6: Get Sample Data")
            sample_response = await self.call_tool("get_sample_data", {"table_name": "customers", "limit": 3})
            print(f"Sample Data Response: {json.dumps(sample_response, indent=2)}")
            
            # Test 7: Execute query
            print("\n🧪 Test 7: Execute SQL Query")
            query_response = await self.call_tool("query", {
                "sql": "SELECT COUNT(*) as total_customers FROM customers WHERE is_active = true",
                "limit": 10
            })
            print(f"Query Response: {json.dumps(query_response, indent=2)}")
            
            # Test 8: Complex query
            print("\n🧪 Test 8: Complex Query with Joins")
            complex_query_response = await self.call_tool("query", {
                "sql": """
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
                """,
                "limit": 5
            })
            print(f"Complex Query Response: {json.dumps(complex_query_response, indent=2)}")
            
            print("\n✅ All tests completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
    
    async def interactive_mode(self):
        """Interactive mode for manual testing."""
        print("\n🎮 Interactive Mode - Enter commands (type 'help' for commands, 'exit' to quit)")
        print("=" * 60)
        
        # Initialize session first
        try:
            await self.initialize()
            print("✅ MCP session initialized")
        except Exception as e:
            print(f"❌ Failed to initialize: {e}")
            return
        
        while True:
            try:
                command = input("\nMCP> ").strip()
                
                if command.lower() in ['exit', 'quit', 'q']:
                    break
                elif command.lower() == 'help':
                    print("Available commands:")
                    print("  help - Show this help")
                    print("  health - Check server health")
                    print("  tools - List available tools")
                    print("  schema - Get database schema")
                    print("  table <name> - Get table info")
                    print("  sample <name> [limit] - Get sample data")
                    print("  query <sql> - Execute SQL query")
                    print("  exit - Exit interactive mode")
                elif command.lower() == 'health':
                    health = await self.health_check()
                    print(f"Health: {json.dumps(health, indent=2)}")
                elif command.lower() == 'tools':
                    tools = await self.list_tools()
                    print(f"Tools: {json.dumps(tools, indent=2)}")
                elif command.lower() == 'schema':
                    schema = await self.call_tool("get_schema")
                    print(f"Schema: {json.dumps(schema, indent=2)}")
                elif command.startswith('table '):
                    table_name = command[6:].strip()
                    table_info = await self.call_tool("get_table_info", {"table_name": table_name})
                    print(f"Table Info: {json.dumps(table_info, indent=2)}")
                elif command.startswith('sample '):
                    parts = command[7:].split()
                    table_name = parts[0]
                    limit = int(parts[1]) if len(parts) > 1 else 5
                    sample = await self.call_tool("get_sample_data", {"table_name": table_name, "limit": limit})
                    print(f"Sample Data: {json.dumps(sample, indent=2)}")
                elif command.startswith('query '):
                    sql = command[6:].strip()
                    query_result = await self.call_tool("query", {"sql": sql})
                    print(f"Query Result: {json.dumps(query_result, indent=2)}")
                elif command:
                    print("Unknown command. Type 'help' for available commands.")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
        
        print("\nGoodbye! 👋")


async def main():
    """Main test function."""
    async with MCPTestClient() as client:
        # Run comprehensive tests
        await client.run_comprehensive_test()
        
        # Ask if user wants interactive mode
        response = input("\n🎮 Would you like to enter interactive mode? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            await client.interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())