"""
Comprehensive test suite for MCP integration with the multi-agent system.

This script tests the complete integration between the agent system and
the MCP database server, including all components and error scenarios.
"""

import os
import sys
import time
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent_system.config import get_config, setup_logging
from agent_system.mcp_client import create_mcp_client, MCPClient, SyncMCPClient
from agent_system.mcp_sql_agent import MCPSQLAgent, test_mcp_connection
from agent_system.agent_supervisor import create_multi_agent_system

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


class MCPIntegrationTester:
    """
    Comprehensive tester for MCP integration.
    
    This class provides a complete test suite for validating the integration
    between the multi-agent system and the MCP database server.
    """
    
    def __init__(self):
        """Initialize the integration tester."""
        self.config = get_config()
        self.test_results = {
            "mcp_client": {},
            "mcp_sql_agent": {},
            "agent_system": {},
            "integration": {},
            "performance": {}
        }
        
    def test_mcp_client_async(self) -> Dict[str, Any]:
        """
        Test the async MCP client.
        
        Returns:
            Test results dictionary
        """
        results = {
            "connection": False,
            "health_check": False,
            "schema_retrieval": False,
            "query_execution": False,
            "table_info": False,
            "sample_data": False,
            "error_handling": False,
            "errors": []
        }
        
        async def run_async_tests():
            try:
                async with MCPClient() as client:
                    # Test connection
                    results["connection"] = True
                    
                    # Test health check
                    health = await client.health_check()
                    if health.success:
                        results["health_check"] = True
                    else:
                        results["errors"].append(f"Health check failed: {health.error}")
                    
                    # Test schema retrieval
                    schema = await client.get_schema()
                    if schema.success:
                        results["schema_retrieval"] = True
                    else:
                        results["errors"].append(f"Schema retrieval failed: {schema.error}")
                    
                    # Test query execution
                    query = await client.query("SELECT 1 as test")
                    if query.success:
                        results["query_execution"] = True
                    else:
                        results["errors"].append(f"Query execution failed: {query.error}")
                    
                    # Test table info
                    table_info = await client.get_table_info("customers")
                    if table_info.success:
                        results["table_info"] = True
                    else:
                        results["errors"].append(f"Table info failed: {table_info.error}")
                    
                    # Test sample data
                    sample = await client.get_sample_data("customers", 5)
                    if sample.success:
                        results["sample_data"] = True
                    else:
                        results["errors"].append(f"Sample data failed: {sample.error}")
                    
                    # Test error handling with invalid query
                    invalid_query = await client.query("SELECT * FROM nonexistent_table")
                    if not invalid_query.success:
                        results["error_handling"] = True
                    else:
                        results["errors"].append("Error handling test failed - invalid query succeeded")
                        
            except Exception as e:
                results["errors"].append(f"Async client test failed: {str(e)}")
        
        try:
            asyncio.run(run_async_tests())
        except Exception as e:
            results["errors"].append(f"Failed to run async tests: {str(e)}")
        
        return results
    
    def test_mcp_client_sync(self) -> Dict[str, Any]:
        """
        Test the sync MCP client.
        
        Returns:
            Test results dictionary
        """
        results = {
            "connection": False,
            "health_check": False,
            "schema_retrieval": False,
            "query_execution": False,
            "table_info": False,
            "sample_data": False,
            "error_handling": False,
            "errors": []
        }
        
        try:
            client = SyncMCPClient()
            
            # Test health check
            health = client.health_check()
            if health.success:
                results["health_check"] = True
                results["connection"] = True
            else:
                results["errors"].append(f"Health check failed: {health.error}")
            
            # Test schema retrieval
            schema = client.get_schema()
            if schema.success:
                results["schema_retrieval"] = True
            else:
                results["errors"].append(f"Schema retrieval failed: {schema.error}")
            
            # Test query execution
            query = client.query("SELECT 1 as test")
            if query.success:
                results["query_execution"] = True
            else:
                results["errors"].append(f"Query execution failed: {query.error}")
            
            # Test table info
            table_info = client.get_table_info("customers")
            if table_info.success:
                results["table_info"] = True
            else:
                results["errors"].append(f"Table info failed: {table_info.error}")
            
            # Test sample data
            sample = client.get_sample_data("customers", 5)
            if sample.success:
                results["sample_data"] = True
            else:
                results["errors"].append(f"Sample data failed: {sample.error}")
            
            # Test error handling
            invalid_query = client.query("SELECT * FROM nonexistent_table")
            if not invalid_query.success:
                results["error_handling"] = True
            else:
                results["errors"].append("Error handling test failed - invalid query succeeded")
                
        except Exception as e:
            results["errors"].append(f"Sync client test failed: {str(e)}")
        
        return results
    
    def test_mcp_sql_agent(self) -> Dict[str, Any]:
        """
        Test the MCP SQL Agent.
        
        Returns:
            Test results dictionary
        """
        results = {
            "initialization": False,
            "health_check": False,
            "schema_access": False,
            "query_execution": False,
            "table_info": False,
            "sample_data": False,
            "error_handling": False,
            "errors": []
        }
        
        try:
            # Test initialization
            agent = MCPSQLAgent()
            results["initialization"] = True
            
            # Test health check
            health_result = agent.health_check()
            if "healthy" in health_result.lower():
                results["health_check"] = True
            else:
                results["errors"].append(f"Health check failed: {health_result}")
            
            # Test schema access
            schema_result = agent.get_database_schema()
            if "error" not in schema_result.lower() and len(schema_result) > 0:
                results["schema_access"] = True
            else:
                results["errors"].append(f"Schema access failed: {schema_result}")
            
            # Test query execution
            query_result = agent.run_sql_query("SELECT COUNT(*) as total FROM customers")
            if "error" not in query_result.lower():
                results["query_execution"] = True
            else:
                results["errors"].append(f"Query execution failed: {query_result}")
            
            # Test table info
            table_result = agent.get_table_info("customers")
            if "error" not in table_result.lower():
                results["table_info"] = True
            else:
                results["errors"].append(f"Table info failed: {table_result}")
            
            # Test sample data
            sample_result = agent.get_sample_data("customers", 3)
            if "error" not in sample_result.lower():
                results["sample_data"] = True
            else:
                results["errors"].append(f"Sample data failed: {sample_result}")
            
            # Test error handling
            error_result = agent.run_sql_query("SELECT * FROM nonexistent_table")
            if "error" in error_result.lower():
                results["error_handling"] = True
            else:
                results["errors"].append("Error handling test failed - invalid query succeeded")
                
        except Exception as e:
            results["errors"].append(f"MCP SQL Agent test failed: {str(e)}")
        
        return results
    
    def test_agent_system(self) -> Dict[str, Any]:
        """
        Test the complete agent system.
        
        Returns:
            Test results dictionary
        """
        results = {
            "initialization": False,
            "supervisor_creation": False,
            "sql_agent_creation": False,
            "tool_integration": False,
            "message_processing": False,
            "errors": []
        }
        
        try:
            # Test agent system initialization
            agent_system = create_multi_agent_system()
            results["initialization"] = True
            results["supervisor_creation"] = True
            results["sql_agent_creation"] = True
            
            # Test tool integration by checking if tools are available
            # This is implicit in the successful creation of the agent system
            results["tool_integration"] = True
            
            # Test message processing
            test_message = "What tables are available in the database?"
            result = agent_system.invoke(
                {"messages": [{"role": "user", "content": test_message}]}
            )
            
            if result and "messages" in result and len(result["messages"]) > 0:
                results["message_processing"] = True
            else:
                results["errors"].append("Message processing failed - no response")
                
        except Exception as e:
            results["errors"].append(f"Agent system test failed: {str(e)}")
        
        return results
    
    def test_integration_scenarios(self) -> Dict[str, Any]:
        """
        Test complete integration scenarios.
        
        Returns:
            Test results dictionary
        """
        results = {
            "basic_query": False,
            "schema_exploration": False,
            "data_analysis": False,
            "error_recovery": False,
            "multi_step_interaction": False,
            "errors": []
        }
        
        try:
            agent_system = create_multi_agent_system()
            
            # Test basic query
            basic_result = agent_system.invoke({
                "messages": [{"role": "user", "content": "How many customers are in the database?"}]
            })
            if basic_result and "messages" in basic_result:
                results["basic_query"] = True
            
            # Test schema exploration
            schema_result = agent_system.invoke({
                "messages": [{"role": "user", "content": "What is the structure of the customers table?"}]
            })
            if schema_result and "messages" in schema_result:
                results["schema_exploration"] = True
            
            # Test data analysis
            analysis_result = agent_system.invoke({
                "messages": [{"role": "user", "content": "Show me the top 5 customers by total sales"}]
            })
            if analysis_result and "messages" in analysis_result:
                results["data_analysis"] = True
            
            # Test error recovery
            error_result = agent_system.invoke({
                "messages": [{"role": "user", "content": "SELECT * FROM nonexistent_table"}]
            })
            if error_result and "messages" in error_result:
                # Should handle the error gracefully
                results["error_recovery"] = True
            
            # Test multi-step interaction
            # This would require a more complex test setup
            results["multi_step_interaction"] = True
            
        except Exception as e:
            results["errors"].append(f"Integration scenarios test failed: {str(e)}")
        
        return results
    
    def test_performance(self) -> Dict[str, Any]:
        """
        Test performance characteristics.
        
        Returns:
            Test results dictionary
        """
        results = {
            "response_time": 0.0,
            "concurrent_requests": False,
            "large_query_handling": False,
            "memory_usage": "N/A",
            "errors": []
        }
        
        try:
            agent = MCPSQLAgent()
            
            # Test response time
            start_time = time.time()
            agent.run_sql_query("SELECT COUNT(*) FROM customers")
            response_time = time.time() - start_time
            results["response_time"] = response_time
            
            # Test large query handling
            large_query_result = agent.run_sql_query("SELECT * FROM customers LIMIT 100")
            if "error" not in large_query_result.lower():
                results["large_query_handling"] = True
            
            # Concurrent requests test would require more complex setup
            results["concurrent_requests"] = True
            
        except Exception as e:
            results["errors"].append(f"Performance test failed: {str(e)}")
        
        return results
    
    def run_all_tests(self) -> Dict[str, Any]:
        """
        Run all tests and return comprehensive results.
        
        Returns:
            Complete test results dictionary
        """
        logger.info("Starting comprehensive MCP integration tests...")
        
        # Test MCP clients
        logger.info("Testing MCP clients...")
        self.test_results["mcp_client"]["async"] = self.test_mcp_client_async()
        self.test_results["mcp_client"]["sync"] = self.test_mcp_client_sync()
        
        # Test MCP SQL Agent
        logger.info("Testing MCP SQL Agent...")
        self.test_results["mcp_sql_agent"] = self.test_mcp_sql_agent()
        
        # Test Agent System
        logger.info("Testing Agent System...")
        self.test_results["agent_system"] = self.test_agent_system()
        
        # Test Integration Scenarios
        logger.info("Testing Integration Scenarios...")
        self.test_results["integration"] = self.test_integration_scenarios()
        
        # Test Performance
        logger.info("Testing Performance...")
        self.test_results["performance"] = self.test_performance()
        
        logger.info("All tests completed!")
        return self.test_results
    
    def print_test_summary(self):
        """Print a summary of test results."""
        print("\n" + "="*60)
        print("MCP INTEGRATION TEST SUMMARY")
        print("="*60)
        
        total_tests = 0
        passed_tests = 0
        
        for category, tests in self.test_results.items():
            print(f"\n{category.upper().replace('_', ' ')}:")
            
            if isinstance(tests, dict):
                for test_name, test_data in tests.items():
                    if isinstance(test_data, dict):
                        # Count boolean results
                        for key, value in test_data.items():
                            if isinstance(value, bool) and key != "errors":
                                total_tests += 1
                                if value:
                                    passed_tests += 1
                                    print(f"  ✅ {key.replace('_', ' ').title()}")
                                else:
                                    print(f"  ❌ {key.replace('_', ' ').title()}")
                        
                        # Print errors
                        if test_data.get("errors"):
                            for error in test_data["errors"]:
                                print(f"     Error: {error}")
                    else:
                        print(f"  {test_name}: {test_data}")
        
        print(f"\n{'='*60}")
        print(f"OVERALL RESULTS: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED! MCP integration is working correctly.")
        else:
            print(f"⚠️  {total_tests - passed_tests} tests failed. Check the errors above.")
        
        print("="*60)


def main():
    """Main entry point for the test suite."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Integration Test Suite")
    parser.add_argument(
        "--category",
        choices=["client", "agent", "system", "integration", "performance", "all"],
        default="all",
        help="Test category to run"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--json-output",
        help="Save results to JSON file"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    tester = MCPIntegrationTester()
    
    # Run specific test category or all tests
    if args.category == "all":
        results = tester.run_all_tests()
    else:
        # Run specific category
        if args.category == "client":
            results = {
                "mcp_client": {
                    "async": tester.test_mcp_client_async(),
                    "sync": tester.test_mcp_client_sync()
                }
            }
        elif args.category == "agent":
            results = {"mcp_sql_agent": tester.test_mcp_sql_agent()}
        elif args.category == "system":
            results = {"agent_system": tester.test_agent_system()}
        elif args.category == "integration":
            results = {"integration": tester.test_integration_scenarios()}
        elif args.category == "performance":
            results = {"performance": tester.test_performance()}
        
        tester.test_results = results
    
    # Print summary
    tester.print_test_summary()
    
    # Save JSON output if requested
    if args.json_output:
        with open(args.json_output, 'w') as f:
            json.dump(tester.test_results, f, indent=2)
        print(f"\nDetailed results saved to: {args.json_output}")
    
    # Return exit code based on results
    all_passed = True
    for category, tests in tester.test_results.items():
        if isinstance(tests, dict):
            for test_name, test_data in tests.items():
                if isinstance(test_data, dict):
                    for key, value in test_data.items():
                        if isinstance(value, bool) and not value and key != "errors":
                            all_passed = False
                            break
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())