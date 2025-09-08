#!/usr/bin/env python3
"""
Startup script for the ERP Chatbot system.
Starts both the LangGraph service and the Streamlit UI.
"""

import os
import sys
import subprocess
import time
import signal
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import streamlit
        import requests
        import fastapi
        import uvicorn
        print("✅ All dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def check_environment():
    """Check if environment variables are set."""
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = ["OPENAI_API_KEY", "API_KEY"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file")
        return False
    
    print("✅ Environment variables are set")
    return True

def start_langgraph_service():
    """Start the LangGraph service."""
    print("🚀 Starting LangGraph service...")
    return subprocess.Popen([
        sys.executable, "langgraph_service.py"
    ], cwd=Path(__file__).parent)

def start_streamlit_ui():
    """Start the Streamlit UI."""
    print("🚀 Starting Streamlit UI...")
    return subprocess.Popen([
        "streamlit", "run", "app.py", "--server.port", "8501"
    ], cwd=Path(__file__).parent)

def main():
    """Main startup function."""
    print("🤖 ERP Chatbot System Startup")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Start services
    processes = []
    
    try:
        # Start LangGraph service
        langgraph_process = start_langgraph_service()
        processes.append(langgraph_process)
        
        # Wait a bit for the service to start
        print("⏳ Waiting for LangGraph service to start...")
        time.sleep(5)
        
        # Start Streamlit UI
        streamlit_process = start_streamlit_ui()
        processes.append(streamlit_process)
        
        print("\n✅ Services started successfully!")
        print("📋 Service URLs:")
        print("   - LangGraph Service: http://localhost:5000")
        print("   - Streamlit UI: http://localhost:8501")
        print("   - API Documentation: http://localhost:5000/docs")
        print("\n🔧 Make sure the following are also running:")
        print("   - MCP Server: http://localhost:8000")
        print("   - PostgreSQL database")
        print("\n⚠️  Press Ctrl+C to stop all services")
        
        # Wait for processes
        while True:
            time.sleep(1)
            # Check if any process has died
            for i, process in enumerate(processes):
                if process.poll() is not None:
                    print(f"❌ Process {i} has stopped unexpectedly")
                    return
    
    except KeyboardInterrupt:
        print("\n🛑 Stopping services...")
        for process in processes:
            process.terminate()
        
        # Wait for graceful shutdown
        time.sleep(2)
        
        # Force kill if needed
        for process in processes:
            if process.poll() is None:
                process.kill()
        
        print("✅ All services stopped")

if __name__ == "__main__":
    main()