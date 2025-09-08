"""
Test Flow for LangGraph MCP Integration
Phase 2 Blueprint Implementation

This module provides comprehensive testing for the LangGraph workflow
that integrates with the MCP database server.
"""

import os
import sys
import asyncio
import logging
import time
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our modules
from mcp_client import MCPDatabaseTool, test_mcp_connection
from graph_definition import create_database_workflow, DatabaseWorkflow

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LangGraphMCPTester:
    """
    Comprehensive tester for the LangGraph MCP integration.
    
    This class tests the complete workflow from user input to formatted response,
    including all the intermediate steps and error handling.
    """
    
    def __init__(self):
        """Initialize the tester."""
        self.workflow = None
        self.test_results = {
            "setup": {},
            "basic_functionality": {},
            "workflow_tests": {},
            "error_handling": {},
            "performance": {}
        }
    
    async def setup_test_environment(self) -> Dict[str, Any]:
        """
        Set up the test environment and verify prerequisites.
        
        Returns:
            Setup test results
        """
        results = {
            "environment_variables": False,
            "mcp_server_connection": False,
            "workflow_initialization": False,
            "errors": []
        }
        
        try:
            # Check environment variables
            required_vars = ["OPENAI_API_KEY", "MCP_SERVER_URL", "API_KEY"]
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            
            if not missing_vars:
                results["environment_variables"] = True
            else:
                results["errors"].append(f"Missing environment variables: {missing_vars}")
            
            # Test MCP server connection
            print("Testing MCP server connection...")
            mcp_tool = MCPDatabaseTool()
            is_healthy = await mcp_tool.health_check()
            
            if is_healthy:
                results["mcp_server_connection"] = True
                print("✅ MCP server is healthy")
            else:
                results["errors"].append("MCP server is not healthy")
                print("❌ MCP server is not healthy")
            
            # Initialize workflow
            if results["environment_variables"] and results["mcp_server_connection"]:
                self.workflow = create_database_workflow()
                results["workflow_initialization"] = True
                print("✅ Workflow initialized successfully")
            else:
                results["errors"].append("Cannot initialize workflow due to setup issues")
                print("❌ Cannot initialize workflow")
                
        except Exception as e:
            results["errors"].append(f"Setup error: {str(e)}")
            logger.error(f"Setup error: {e}")
        
        self.test_results["setup"] = results
        return results
    
    async def test_basic_mcp_functionality(self) -> Dict[str, Any]:
        """
        Test basic MCP client functionality.
        
        Returns:
            Basic functionality test results
        """
        results = {
            "health_check": False,
            "schema_retrieval": False,
            "query_execution": False,
            "table_info": False,
            "sample_data": False,
            "errors": []
        }
        
        try:
            mcp_tool = MCPDatabaseTool()
            
            # Test health check
            is_healthy = await mcp_tool.health_check()
            results["health_check"] = is_healthy
            if not is_healthy:
                results["errors"].append("Health check failed")
            
            # Test schema retrieval
            try:
                schema_content = await mcp_tool.get_schema()
                if schema_content:
                    results["schema_retrieval"] = True
                else:
                    results["errors"].append("Schema retrieval returned empty result")
            except Exception as e:
                results["errors"].append(f"Schema retrieval failed: {str(e)}")
            
            # Test query execution
            try:
                query_content = await mcp_tool.query("SELECT 1 as test")
                if query_content:
                    results["query_execution"] = True
                else:
                    results["errors"].append("Query execution returned empty result")
            except Exception as e:
                results["errors"].append(f"Query execution failed: {str(e)}")
            
            # Test table info
            try:
                table_content = await mcp_tool.get_table_info("customers")
                if table_content:
                    results["table_info"] = True
                else:
                    results["errors"].append("Table info returned empty result")
            except Exception as e:
                results["errors"].append(f"Table info failed: {str(e)}")
            
            # Test sample data
            try:
                sample_content = await mcp_tool.get_sample_data("customers", 5)
                if sample_content:
                    results["sample_data"] = True
                else:
                    results["errors"].append("Sample data returned empty result")
            except Exception as e:
                results["errors"].append(f"Sample data failed: {str(e)}")
                
        except Exception as e:
            results["errors"].append(f"Basic functionality test error: {str(e)}")
            logger.error(f"Basic functionality test error: {e}")
        
        self.test_results["basic_functionality"] = results
        return results
    
    async def test_workflow_scenarios(self) -> Dict[str, Any]:
        """
        Test different workflow scenarios.
        
        Returns:
            Workflow test results
        """
        results = {
            "schema_query": False,
            "data_query": False,
            "analysis_query": False,
            "sample_data_query": False,
            "health_check_query": False,
            "responses": {},
            "errors": []
        }
        
        if not self.workflow:
            results["errors"].append("Workflow not initialized")
            self.test_results["workflow_tests"] = results
            return results
        
        # Test scenarios
        test_scenarios = [
            ("schema_query", "What tables are available in the database?"),
            ("data_query", "How many customers do we have?"),
            ("analysis_query", "Show me the top 5 customers by total sales"),
            ("sample_data_query", "Can you show me some sample customer data?"),
            ("health_check_query", "Is the system working properly?")
        ]
        
        for scenario_name, query in test_scenarios:
            try:
                print(f"\nTesting {scenario_name}: {query}")
                start_time = time.time()
                
                response = await self.workflow.process_query(query)
                
                end_time = time.time()
                response_time = end_time - start_time
                
                if response and len(response) > 0:
                    results[scenario_name] = True
                    results["responses"][scenario_name] = {
                        "query": query,
                        "response": response[:200] + "..." if len(response) > 200 else response,
                        "response_time": response_time
                    }
                    print(f"✅ {scenario_name} completed in {response_time:.2f}s")
                else:
                    results["errors"].append(f"{scenario_name} returned empty response")
                    print(f"❌ {scenario_name} failed - empty response")
                    
            except Exception as e:
                results["errors"].append(f"{scenario_name} failed: {str(e)}")
                logger.error(f"{scenario_name} test error: {e}")
                print(f"❌ {scenario_name} failed with error: {e}")
        
        self.test_results["workflow_tests"] = results
        return results
    
    async def test_error_handling(self) -> Dict[str, Any]:
        """
        Test error handling scenarios.
        
        Returns:
            Error handling test results
        """
        results = {
            "invalid_sql": False,
            "nonexistent_table": False,
            "malformed_query": False,
            "empty_input": False,
            "responses": {},
            "errors": []
        }
        
        if not self.workflow:
            results["errors"].append("Workflow not initialized")
            self.test_results["error_handling"] = results
            return results
        
        # Error test scenarios
        error_scenarios = [
            ("invalid_sql", "SELECT * FROM nonexistent_table"),
            ("nonexistent_table", "Show me data from the unicorns table"),
            ("malformed_query", "This is not a valid database query at all"),
            ("empty_input", "")
        ]
        
        for scenario_name, query in error_scenarios:
            try:
                print(f"\nTesting error scenario {scenario_name}: {query}")
                
                response = await self.workflow.process_query(query)
                
                # For error scenarios, we expect a helpful error message, not a crash
                if response and "error" in response.lower() or "sorry" in response.lower():
                    results[scenario_name] = True
                    results["responses"][scenario_name] = {
                        "query": query,
                        "response": response[:200] + "..." if len(response) > 200 else response
                    }
                    print(f"✅ {scenario_name} handled gracefully")
                else:
                    results["errors"].append(f"{scenario_name} did not handle error appropriately")
                    print(f"❌ {scenario_name} error handling failed")
                    
            except Exception as e:
                # Exceptions during error handling are actually failures
                results["errors"].append(f"{scenario_name} threw exception: {str(e)}")
                logger.error(f"{scenario_name} error handling test failed: {e}")
                print(f"❌ {scenario_name} threw exception: {e}")
        
        self.test_results["error_handling"] = results
        return results
    
    async def test_performance(self) -> Dict[str, Any]:
        """
        Test performance characteristics.
        
        Returns:
            Performance test results
        """
        results = {
            "average_response_time": 0.0,
            "max_response_time": 0.0,
            "min_response_time": float('inf'),
            "successful_queries": 0,
            "total_queries": 0,
            "errors": []
        }
        
        if not self.workflow:
            results["errors"].append("Workflow not initialized")
            self.test_results["performance"] = results
            return results
        
        # Performance test queries
        performance_queries = [
            "How many customers do we have?",
            "What tables are in the database?",
            "Show me 5 sample products",
            "Count the total number of sales",
            "Is the system healthy?"
        ]
        
        response_times = []
        
        for i, query in enumerate(performance_queries):
            try:
                print(f"\nPerformance test {i+1}/{len(performance_queries)}: {query}")
                
                start_time = time.time()
                response = await self.workflow.process_query(query)
                end_time = time.time()
                
                response_time = end_time - start_time
                response_times.append(response_time)
                
                results["total_queries"] += 1
                
                if response and len(response) > 0:
                    results["successful_queries"] += 1
                    print(f"✅ Query completed in {response_time:.2f}s")
                else:
                    print(f"❌ Query failed - empty response")
                    
            except Exception as e:
                results["errors"].append(f"Performance test query failed: {str(e)}")
                logger.error(f"Performance test error: {e}")
                print(f"❌ Query failed with error: {e}")
        
        # Calculate performance metrics
        if response_times:
            results["average_response_time"] = sum(response_times) / len(response_times)
            results["max_response_time"] = max(response_times)
            results["min_response_time"] = min(response_times)
        
        self.test_results["performance"] = results
        return results
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """
        Run all tests and return comprehensive results.
        
        Returns:
            Complete test results
        """
        print("🚀 Starting LangGraph MCP Integration Tests")
        print("=" * 60)
        
        # Setup
        print("\n📋 Setting up test environment...")
        setup_results = await self.setup_test_environment()
        
        if not all([setup_results["environment_variables"], 
                   setup_results["mcp_server_connection"], 
                   setup_results["workflow_initialization"]]):
            print("❌ Setup failed. Cannot proceed with tests.")
            return self.test_results
        
        # Basic functionality
        print("\n🔧 Testing basic MCP functionality...")
        await self.test_basic_mcp_functionality()
        
        # Workflow scenarios
        print("\n🔄 Testing workflow scenarios...")
        await self.test_workflow_scenarios()
        
        # Error handling
        print("\n⚠️  Testing error handling...")
        await self.test_error_handling()
        
        # Performance
        print("\n⚡ Testing performance...")
        await self.test_performance()
        
        print("\n✅ All tests completed!")
        return self.test_results
    
    def print_test_summary(self):
        """Print a comprehensive test summary."""
        print("\n" + "=" * 60)
        print("LANGGRAPH MCP INTEGRATION TEST SUMMARY")
        print("=" * 60)
        
        total_tests = 0
        passed_tests = 0
        
        for category, tests in self.test_results.items():
            if not tests:
                continue
                
            print(f"\n{category.upper().replace('_', ' ')}:")
            
            category_tests = 0
            category_passed = 0
            
            for test_name, result in tests.items():
                if test_name == "errors" or test_name == "responses":
                    continue
                    
                if isinstance(result, bool):
                    category_tests += 1
                    total_tests += 1
                    
                    if result:
                        category_passed += 1
                        passed_tests += 1
                        print(f"  ✅ {test_name.replace('_', ' ').title()}")
                    else:
                        print(f"  ❌ {test_name.replace('_', ' ').title()}")
                elif isinstance(result, (int, float)) and test_name != "total_queries":
                    print(f"  📊 {test_name.replace('_', ' ').title()}: {result}")
            
            # Print errors for this category
            if tests.get("errors"):
                print(f"  Errors in {category}:")
                for error in tests["errors"]:
                    print(f"    - {error}")
            
            if category_tests > 0:
                print(f"  Category Score: {category_passed}/{category_tests}")
        
        print(f"\n{'=' * 60}")
        print(f"OVERALL RESULTS: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED! LangGraph MCP integration is working perfectly.")
        else:
            print(f"⚠️  {total_tests - passed_tests} tests failed. Check the details above.")
        
        # Performance summary
        perf = self.test_results.get("performance", {})
        if perf.get("average_response_time"):
            print(f"\n📈 PERFORMANCE SUMMARY:")
            print(f"  Average Response Time: {perf['average_response_time']:.2f}s")
            print(f"  Min Response Time: {perf['min_response_time']:.2f}s")
            print(f"  Max Response Time: {perf['max_response_time']:.2f}s")
            print(f"  Success Rate: {perf['successful_queries']}/{perf['total_queries']}")
        
        print("=" * 60)


async def main():
    """Main test execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="LangGraph MCP Integration Test Suite")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--quick", action="store_true", help="Run only basic tests")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run tester
    tester = LangGraphMCPTester()
    
    if args.quick:
        # Quick test - just setup and basic functionality
        await tester.setup_test_environment()
        await tester.test_basic_mcp_functionality()
    else:
        # Full test suite
        await tester.run_all_tests()
    
    # Print summary
    tester.print_test_summary()
    
    # Return appropriate exit code
    setup_ok = tester.test_results.get("setup", {})
    if not all([setup_ok.get("environment_variables", False),
               setup_ok.get("mcp_server_connection", False),
               setup_ok.get("workflow_initialization", False)]):
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))