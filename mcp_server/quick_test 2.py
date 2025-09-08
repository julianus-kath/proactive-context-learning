#!/usr/bin/env python3
"""
Quick test script for the MCP server.
"""

import asyncio
import aiohttp
import json
import subprocess
import time
import sys
import signal
import os

async def test_mcp_server():
    """Test the MCP server functionality."""
    
    print("🧪 MCP Server Quick Test")
    print("=" * 50)
    
    # Start server
    print("🚀 Starting MCP Server...")
    server_process = subprocess.Popen([
        sys.executable, '-c', '''
import uvicorn
from server import app
uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")
'''
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    await asyncio.sleep(3)
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test 1: Health check
            print("\n🔍 Test 1: Health Check")
            try:
                async with session.get('http://localhost:8000/health') as response:
                    if response.status == 200:
                        health_data = await response.json()
                        print(f"✅ Health Check: {health_data}")
                    else:
                        print(f"❌ Health Check failed: {response.status}")
            except Exception as e:
                print(f"❌ Health Check error: {e}")
            
            # Test 2: Root endpoint
            print("\n🔍 Test 2: Root Endpoint")
            try:
                async with session.get('http://localhost:8000/') as response:
                    if response.status == 200:
                        root_data = await response.json()
                        print(f"✅ Root Endpoint: {root_data}")
                    else:
                        print(f"❌ Root Endpoint failed: {response.status}")
            except Exception as e:
                print(f"❌ Root Endpoint error: {e}")
            
            # Test 3: MCP Initialize
            print("\n🔍 Test 3: MCP Initialize")
            headers = {
                "Authorization": "Bearer supersecretapikey",
                "Content-Type": "application/json"
            }
            
            init_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    }
                },
                "id": 1
            }
            
            try:
                async with session.post(
                    'http://localhost:8000/mcp',
                    json=init_request,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        init_data = await response.json()
                        print(f"✅ MCP Initialize: {json.dumps(init_data, indent=2)}")
                    else:
                        print(f"❌ MCP Initialize failed: {response.status}")
                        error_text = await response.text()
                        print(f"Error: {error_text}")
            except Exception as e:
                print(f"❌ MCP Initialize error: {e}")
            
            # Test 4: List Tools
            print("\n🔍 Test 4: List Tools")
            tools_request = {
                "jsonrpc": "2.0",
                "method": "list_tools",
                "id": 2
            }
            
            try:
                async with session.post(
                    'http://localhost:8000/mcp',
                    json=tools_request,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        tools_data = await response.json()
                        print(f"✅ List Tools: {json.dumps(tools_data, indent=2)}")
                    else:
                        print(f"❌ List Tools failed: {response.status}")
            except Exception as e:
                print(f"❌ List Tools error: {e}")
            
            # Test 5: Query Database
            print("\n🔍 Test 5: Query Database")
            query_request = {
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "query",
                    "arguments": {
                        "sql": "SELECT COUNT(*) as total_customers FROM customers",
                        "limit": 10
                    }
                },
                "id": 3
            }
            
            try:
                async with session.post(
                    'http://localhost:8000/mcp',
                    json=query_request,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        query_data = await response.json()
                        print(f"✅ Database Query: {json.dumps(query_data, indent=2)}")
                    else:
                        print(f"❌ Database Query failed: {response.status}")
            except Exception as e:
                print(f"❌ Database Query error: {e}")
    
    finally:
        # Stop server
        print("\n🛑 Stopping server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
        print("✅ Server stopped")
    
    print("\n🎉 Test completed!")

if __name__ == "__main__":
    asyncio.run(test_mcp_server())