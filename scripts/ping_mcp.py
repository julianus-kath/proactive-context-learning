#!/usr/bin/env python3
"""
MCP Server Diagnostic Tool - Phase 0 Reality Check

Tests MCP server connectivity, health, and basic operations.
Supports both Postgres (dev) and MSSQL (prod) via environment switching.

Usage:
    python scripts/ping_mcp.py
    
Environment Variables:
    MCP_SERVER_URL - MCP server URL (default: http://localhost:8000)
    MCP_API_KEY - API key for authentication
    DB_MODE - Database mode (local/proxy)
"""

import os
import sys
import json
import time
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
MCP_API_KEY = os.getenv("MCP_API_KEY", "supersecretapikey")
DB_MODE = os.getenv("DB_MODE", "local")

# Colors for output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color


def print_color(message: str, color: str = NC):
    """Print colored message."""
    print(f"{color}{message}{NC}")


def print_section(title: str):
    """Print section header."""
    print_color(f"\n{'='*60}", BLUE)
    print_color(f"  {title}", BLUE)
    print_color(f"{'='*60}", BLUE)


def test_health() -> bool:
    """Test MCP server health endpoint."""
    print_section("1. Health Check")
    
    try:
        response = requests.get(
            f"{MCP_SERVER_URL}/health",
            timeout=10
        )
        
        if response.status_code == 200:
            health_data = response.json()
            print_color("✅ Health endpoint reachable", GREEN)
            
            # Display health information
            print(f"\n  Service: {health_data.get('service', 'Unknown')}")
            print(f"  Version: {health_data.get('version', 'Unknown')}")
            print(f"  Status: {'OK' if health_data.get('ok') else 'ERROR'}")
            print(f"  DB Connected: {health_data.get('db_connected', False)}")
            print(f"  DB Mode: {health_data.get('db_mode', 'Unknown')}")
            print(f"  Dialects: {', '.join(health_data.get('dialects', []))}")
            
            if health_data.get('catalog_cached'):
                print(f"  Catalog Cached: Yes (age: {health_data.get('catalog_age_s', 0)}s)")
                print(f"  Cache Hits: {health_data.get('cache_hits', 0)}")
            else:
                print(f"  Catalog Cached: No")
            
            if health_data.get('query_test'):
                print(f"  Query Test: {health_data['query_test']}")
            
            if not health_data.get('ok'):
                print_color(f"\n  ⚠️  Error: {health_data.get('error', 'Unknown error')}", YELLOW)
                return False
            
            return True
        else:
            print_color(f"❌ Health check failed: HTTP {response.status_code}", RED)
            return False
            
    except requests.exceptions.ConnectionError:
        print_color("❌ Cannot connect to MCP server", RED)
        print_color(f"   URL: {MCP_SERVER_URL}", YELLOW)
        print_color("   Is the server running? Try: ./start_all_services.sh", YELLOW)
        return False
    except Exception as e:
        print_color(f"❌ Health check error: {e}", RED)
        return False


def jsonrpc_call(method: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Make a JSON-RPC call to MCP server."""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": int(time.time() * 1000)
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": MCP_API_KEY
    }
    
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/mcp",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 401:
            print_color("❌ Authentication failed - check MCP_API_KEY", RED)
            return None
        
        if response.status_code != 200:
            print_color(f"❌ HTTP {response.status_code}: {response.text}", RED)
            return None
        
        result = response.json()
        
        if result.get("error"):
            error = result["error"]
            print_color(f"❌ JSON-RPC Error {error.get('code')}: {error.get('message')}", RED)
            return None
        
        return result.get("result")
        
    except Exception as e:
        print_color(f"❌ JSON-RPC call failed: {e}", RED)
        return None


def test_get_schema() -> bool:
    """Test get_schema tool."""
    print_section("2. Get Schema Test")
    
    print("Calling tools/call with name='get_schema'...")
    
    start_time = time.time()
    result = jsonrpc_call("tools/call", {
        "name": "get_schema",
        "arguments": {}
    })
    elapsed = time.time() - start_time
    
    if result is None:
        return False
    
    print_color(f"✅ get_schema succeeded in {elapsed:.2f}s", GREEN)
    
    # Parse the result
    if result.get("isError"):
        print_color(f"   ⚠️  Tool returned error", YELLOW)
        return False
    
    content = result.get("content", [])
    if content:
        text = content[0].get("text", "")
        lines = text.split('\n')
        
        # Count tables
        table_count = sum(1 for line in lines if line.startswith("Table:"))
        print(f"\n  Tables found: {table_count}")
        
        # Show first few tables
        if table_count > 0:
            print("\n  Sample tables:")
            shown = 0
            for line in lines:
                if line.startswith("Table:") and shown < 5:
                    print(f"    {line}")
                    shown += 1
            
            if table_count > 5:
                print(f"    ... and {table_count - 5} more")
    
    return True


def test_query() -> bool:
    """Test query tool with SELECT 1."""
    print_section("3. Query Test (SELECT 1)")
    
    print("Calling tools/call with name='query', sql='SELECT 1 as test'...")
    
    start_time = time.time()
    result = jsonrpc_call("tools/call", {
        "name": "query",
        "arguments": {
            "sql": "SELECT 1 as test",
            "limit": 1
        }
    })
    elapsed = time.time() - start_time
    
    if result is None:
        return False
    
    print_color(f"✅ Query succeeded in {elapsed:.2f}s", GREEN)
    
    # Parse the result
    if result.get("isError"):
        print_color(f"   ⚠️  Query returned error", YELLOW)
        content = result.get("content", [])
        if content:
            print(f"   Error: {content[0].get('text', '')}")
        return False
    
    content = result.get("content", [])
    if content:
        text = content[0].get("text", "")
        print(f"\n  Result:\n{text}")
    
    return True


def test_tools_list() -> bool:
    """Test tools/list method."""
    print_section("4. Tools List Test")
    
    print("Calling tools/list...")
    
    result = jsonrpc_call("tools/list", {})
    
    if result is None:
        return False
    
    tools = result.get("tools", [])
    print_color(f"✅ Found {len(tools)} tools", GREEN)
    
    print("\n  Available tools:")
    for tool in tools:
        print(f"    - {tool.get('name')}: {tool.get('description')}")
    
    return True


def main():
    """Run all diagnostic tests."""
    print_color("\n" + "="*60, BLUE)
    print_color("  MCP Server Diagnostic Tool - Phase 0 Reality Check", BLUE)
    print_color("="*60, BLUE)
    
    print(f"\n  MCP Server: {MCP_SERVER_URL}")
    print(f"  DB Mode: {DB_MODE}")
    print(f"  API Key: {'*' * len(MCP_API_KEY) if MCP_API_KEY else 'NOT SET'}")
    
    # Run tests
    tests = [
        ("Health Check", test_health),
        ("Tools List", test_tools_list),
        ("Get Schema", test_get_schema),
        ("Query Test", test_query),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print_color(f"\n❌ Test '{test_name}' crashed: {e}", RED)
            results.append((test_name, False))
    
    # Summary
    print_section("Test Summary")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = f"{GREEN}✅ PASS{NC}" if success else f"{RED}❌ FAIL{NC}"
        print(f"  {test_name:20s} {status}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print_color("\n🎉 All tests passed! MCP server is ready.", GREEN)
        return 0
    else:
        print_color(f"\n⚠️  {total - passed} test(s) failed.", YELLOW)
        return 1


if __name__ == "__main__":
    sys.exit(main())