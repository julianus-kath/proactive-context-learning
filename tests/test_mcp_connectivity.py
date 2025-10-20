#!/usr/bin/env python3
"""
MCP Server Connectivity Diagnostic Tool

This script tests if your MCP server is reachable and responding correctly.
Run this when you're getting timeout errors in the logs.

Usage:
    python tests/test_mcp_connectivity.py
"""

import os
import sys
import asyncio
import aiohttp
import time
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "supersecretapikey")

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_status(status: str, message: str):
    """Print colored status message."""
    if status == "OK":
        print(f"{Colors.GREEN}✅ {status}{Colors.END}: {message}")
    elif status == "FAIL":
        print(f"{Colors.RED}❌ {status}{Colors.END}: {message}")
    elif status == "WARN":
        print(f"{Colors.YELLOW}⚠️  {status}{Colors.END}: {message}")
    else:
        print(f"{Colors.BLUE}ℹ️  {status}{Colors.END}: {message}")

async def test_health_endpoint():
    """Test if MCP server health endpoint responds."""
    print(f"\n{Colors.BOLD}1. Testing MCP server health endpoint...{Colors.END}")
    
    try:
        async with aiohttp.ClientSession() as session:
            start = time.time()
            async with session.get(
                f"{MCP_SERVER_URL}/health",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                duration = (time.time() - start) * 1000
                
                if response.status == 200:
                    print_status("OK", f"Health endpoint responded in {duration:.0f}ms")
                    data = await response.json()
                    print(f"   Response: {data}")
                    return True
                else:
                    print_status("FAIL", f"Health endpoint returned {response.status}")
                    return False
    except asyncio.TimeoutError:
        print_status("FAIL", f"Health endpoint timeout after 10s - server not responding")
        return False
    except Exception as e:
        print_status("FAIL", f"Cannot reach health endpoint: {e}")
        return False

async def test_mcp_tool_call():
    """Test if MCP tool call endpoint works."""
    print(f"\n{Colors.BOLD}2. Testing MCP tool call endpoint (list_tables)...{Colors.END}")
    
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "list_tables", "arguments": {"page": 1, "page_size": 5}},
        "id": 1
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            start = time.time()
            async with session.post(
                f"{MCP_SERVER_URL}/mcp",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                duration = (time.time() - start) * 1000
                
                if response.status == 200:
                    print_status("OK", f"Tool call succeeded in {duration:.0f}ms")
                    data = await response.json()
                    
                    # Check for errors in response
                    if "error" in data and data["error"] is not None:
                        print_status("FAIL", f"MCP returned error: {data['error']}")
                        return False
                    
                    # Check for result
                    result = data.get("result", {})
                    content = result.get("content", [])
                    
                    if content:
                        text = content[0].get("text", "")[:200]
                        print(f"   Response preview: {text}...")
                    
                    return True
                else:
                    print_status("FAIL", f"Tool call returned {response.status}")
                    text = await response.text()
                    print(f"   Response: {text[:200]}")
                    return False
    except asyncio.TimeoutError:
        print_status("FAIL", f"Tool call timeout after 60s - MCP server is overloaded or unresponsive")
        return False
    except Exception as e:
        print_status("FAIL", f"Cannot call MCP tool: {e}")
        return False

async def test_connection_speed():
    """Test basic network connectivity speed."""
    print(f"\n{Colors.BOLD}3. Testing network connectivity speed...{Colors.END}")
    
    # Parse URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(MCP_SERVER_URL)
        host = parsed.hostname
        port = parsed.port or 80
        
        print(f"   Target: {host}:{port}")
        
        # Try simple TCP connection
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        start = time.time()
        try:
            sock.connect((host, port))
            duration = (time.time() - start) * 1000
            print_status("OK", f"TCP connection successful in {duration:.0f}ms")
            sock.close()
            return True
        except socket.timeout:
            print_status("FAIL", f"TCP connection timeout after 5s")
            return False
        except Exception as e:
            print_status("FAIL", f"TCP connection failed: {e}")
            return False
    except Exception as e:
        print_status("WARN", f"Could not test TCP: {e}")
        return None

async def main():
    """Run all diagnostics."""
    print(f"\n{Colors.BOLD}{'='*60}")
    print("MCP Server Connectivity Diagnostic")
    print(f"{'='*60}{Colors.END}")
    
    print(f"\n📋 Configuration:")
    print(f"   MCP_SERVER_URL: {MCP_SERVER_URL}")
    print(f"   API_KEY: {'***' if API_KEY else 'NOT SET'}")
    
    results = {}
    
    # Test 1: Health endpoint
    results["health"] = await test_health_endpoint()
    
    # Test 2: Network connectivity
    results["network"] = await test_connection_speed()
    
    # Test 3: Tool call
    if results["health"]:
        results["tool_call"] = await test_mcp_tool_call()
    else:
        print(f"\n{Colors.BOLD}2. Skipping tool call test (health check failed){Colors.END}")
        results["tool_call"] = None
    
    # Summary
    print(f"\n{Colors.BOLD}{'='*60}")
    print("Diagnostic Summary")
    print(f"{'='*60}{Colors.END}")
    
    if all([v for v in results.values() if v is not None]):
        print(f"{Colors.GREEN}✅ All tests passed! MCP server is responding correctly.{Colors.END}")
        print(f"\nYour system should be working. If you're still seeing errors:")
        print(f"1. Check the error message in langgraph.log")
        print(f"2. Verify API authentication (check MCP_API_KEY)")
        print(f"3. Check Windows firewall on the MCP server machine")
        return 0
    else:
        print(f"{Colors.RED}❌ Some tests failed!{Colors.END}")
        print(f"\nTroubleshooting:")
        
        if not results.get("network"):
            print(f"❌ Network: Cannot reach server at {MCP_SERVER_URL}")
            print(f"   → Check Windows machine IP address")
            print(f"   → Check both machines are on same network")
            print(f"   → Check firewall on Windows machine allows port {MCP_SERVER_URL.split(':')[-1]}")
        
        if not results.get("health"):
            print(f"❌ Health: Server not responding to health check")
            print(f"   → Start Windows MCP server: start_mcp_server_windows.bat")
            print(f"   → Verify MCP_SERVER_URL is correct in .env")
        
        if results.get("health") and not results.get("tool_call"):
            print(f"❌ Tool Call: Server responded to health but failed tool call")
            print(f"   → Check MCP_API_KEY is correct")
            print(f"   → Check MCP server logs for errors")
        
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)