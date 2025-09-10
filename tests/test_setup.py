#!/usr/bin/env python3
"""
Test script to verify the chatbot UI setup is working correctly.
"""

import os
import sys
import requests
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_environment():
    """Test environment variables."""
    print("🔧 Testing environment variables...")
    
    required_vars = ["OPENAI_API_KEY", "API_KEY", "LANGGRAPH_URL", "MCP_SERVER_URL"]
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            # Mask API keys for security
            if "API_KEY" in var:
                display_value = f"{value[:10]}...{value[-4:]}" if len(value) > 14 else "***"
            else:
                display_value = value
            print(f"  ✅ {var}: {display_value}")
    
    if missing_vars:
        print(f"  ❌ Missing variables: {', '.join(missing_vars)}")
        return False
    
    return True

def test_mcp_server():
    """Test MCP server connection."""
    print("\n🗄️ Testing MCP server connection...")
    
    mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
    
    try:
        response = requests.get(f"{mcp_url}/health", timeout=5)
        if response.status_code == 200:
            print(f"  ✅ MCP server is healthy at {mcp_url}")
            return True
        else:
            print(f"  ❌ MCP server returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Cannot connect to MCP server: {e}")
        print(f"  💡 Make sure MCP server is running: cd ../mcp_server && python start_server.py")
        return False

def test_imports():
    """Test required imports."""
    print("\n📦 Testing imports...")
    
    try:
        import streamlit
        print(f"  ✅ Streamlit: {streamlit.__version__}")
    except ImportError:
        print("  ❌ Streamlit not found")
        return False
    
    try:
        import fastapi
        print(f"  ✅ FastAPI: {fastapi.__version__}")
    except ImportError:
        print("  ❌ FastAPI not found")
        return False
    
    try:
        import uvicorn
        print(f"  ✅ Uvicorn: {uvicorn.__version__}")
    except ImportError:
        print("  ❌ Uvicorn not found")
        return False
    
    # Test LangGraph integration import
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from langgraph_integration.graph_definition import create_database_workflow
        print("  ✅ LangGraph integration import successful")
        return True
    except ImportError as e:
        print(f"  ❌ LangGraph integration import failed: {e}")
        return False

def test_langgraph_workflow():
    """Test LangGraph workflow creation."""
    print("\n🔄 Testing LangGraph workflow...")
    
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from langgraph_integration.graph_definition import create_database_workflow
        
        workflow = create_database_workflow()
        print("  ✅ LangGraph workflow created successfully")
        return True
    except Exception as e:
        print(f"  ❌ Failed to create LangGraph workflow: {e}")
        return False

def main():
    """Main test function."""
    print("🤖 ERP Chatbot UI - Setup Test")
    print("=" * 50)
    
    tests = [
        ("Environment Variables", test_environment),
        ("Required Imports", test_imports),
        ("MCP Server Connection", test_mcp_server),
        ("LangGraph Workflow", test_langgraph_workflow),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"  ⚠️ {test_name} test failed")
        except Exception as e:
            print(f"  ❌ {test_name} test error: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The chatbot UI is ready to run.")
        print("\n🚀 Next steps:")
        print("  1. Start the services: python start_services.py")
        print("  2. Or manually:")
        print("     - Terminal 1: python langgraph_service.py")
        print("     - Terminal 2: streamlit run app.py")
        print("  3. Open http://localhost:8501 in your browser")
    else:
        print("❌ Some tests failed. Please fix the issues before running the chatbot.")
        
        if not test_mcp_server():
            print("\n💡 To start MCP server:")
            print("  cd ../mcp_server && python start_server.py")

if __name__ == "__main__":
    main()