#!/usr/bin/env python3
"""
Test script for the ERP Chatbot Web UI
This script tests the web interface endpoints and functionality.
"""

import requests
import json
import time
from pathlib import Path

def test_web_ui_health():
    """Test the web UI health endpoint."""
    try:
        response = requests.get("http://localhost:3000/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Web UI Health Check:", data)
            return True
        else:
            print(f"❌ Web UI Health Check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Web UI Health Check error: {e}")
        return False

def test_langgraph_health():
    """Test the LangGraph service health endpoint."""
    try:
        response = requests.get("http://localhost:5001/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ LangGraph Service Health Check:", data)
            return True
        else:
            print(f"❌ LangGraph Service Health Check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ LangGraph Service Health Check error: {e}")
        return False

def test_static_files():
    """Test that static files are served correctly."""
    files_to_test = [
        ("http://localhost:3000/", "text/html"),
        ("http://localhost:3000/styles.css", "text/css"),
        ("http://localhost:3000/script.js", "application/javascript")
    ]
    
    for url, expected_type in files_to_test:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').split(';')[0]
                if expected_type in content_type or content_type in expected_type:
                    print(f"✅ Static file served: {url}")
                else:
                    print(f"⚠️  Static file wrong type: {url} (got {content_type}, expected {expected_type})")
            else:
                print(f"❌ Static file failed: {url} ({response.status_code})")
        except Exception as e:
            print(f"❌ Static file error: {url} - {e}")

def test_config_endpoint():
    """Test the configuration endpoint."""
    try:
        response = requests.get("http://localhost:3000/config", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Config endpoint:", data)
            return True
        else:
            print(f"❌ Config endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Config endpoint error: {e}")
        return False

def test_conversation_api():
    """Test the conversation API through LangGraph service."""
    try:
        payload = {
            "messages": [{"role": "user", "content": "Hello, can you help me?"}],
            "api_key": "supersecretapikey"
        }
        
        response = requests.post(
            "http://localhost:5001/process_conversation",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Conversation API test successful")
            print(f"   Response: {data.get('final_response', 'No response')[:100]}...")
            return True
        else:
            print(f"❌ Conversation API test failed: {response.status_code}")
            if response.status_code == 401:
                print("   Check your API key configuration")
            elif response.status_code == 503:
                print("   LangGraph workflow not initialized")
            return False
    except Exception as e:
        print(f"❌ Conversation API test error: {e}")
        return False

def check_file_structure():
    """Check that all required files exist."""
    current_dir = Path(__file__).parent
    required_files = [
        "index.html",
        "styles.css", 
        "script.js",
        "web_app.py",
        "langgraph_service.py",
        "start_web_ui.py"
    ]
    
    print("📁 Checking file structure...")
    all_exist = True
    for file in required_files:
        file_path = current_dir / file
        if file_path.exists():
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - MISSING")
            all_exist = False
    
    return all_exist

def main():
    """Run all tests."""
    print("🧪 Testing ERP Chatbot Web UI")
    print("=" * 50)
    
    # Check file structure first
    if not check_file_structure():
        print("\n❌ File structure check failed. Please ensure all files are present.")
        return
    
    print("\n🔍 Testing services...")
    
    # Test web UI
    web_ui_ok = test_web_ui_health()
    
    # Test LangGraph service
    langgraph_ok = test_langgraph_health()
    
    if web_ui_ok:
        # Test static files
        print("\n📄 Testing static files...")
        test_static_files()
        
        # Test config
        print("\n⚙️  Testing configuration...")
        test_config_endpoint()
    
    if langgraph_ok:
        # Test conversation API
        print("\n💬 Testing conversation API...")
        test_conversation_api()
    
    print("\n" + "=" * 50)
    print("🏁 Test Summary")
    print("=" * 50)
    
    if web_ui_ok and langgraph_ok:
        print("✅ All services are running correctly!")
        print("🌐 Web UI: http://localhost:3000")
        print("📡 LangGraph API: http://localhost:5001")
        print("\nYou can now use the web interface.")
    elif web_ui_ok:
        print("✅ Web UI is running")
        print("❌ LangGraph service is not available")
        print("\nStart the LangGraph service to enable chat functionality.")
    elif langgraph_ok:
        print("❌ Web UI is not running")
        print("✅ LangGraph service is running")
        print("\nStart the web UI to access the interface.")
    else:
        print("❌ Neither service is running")
        print("\nRun: python start_web_ui.py")

if __name__ == "__main__":
    main()