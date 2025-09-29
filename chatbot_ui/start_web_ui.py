#!/usr/bin/env python3
"""
Start script for the ERP Chatbot Web UI
This script starts both the LangGraph service and the new web interface.
"""

import os
import sys
import subprocess
import time
import signal
import threading
from pathlib import Path

def print_banner():
    """Print startup banner."""
    print("=" * 60)
    print("🚀 ERP Chatbot Web UI - Starting Services")
    print("=" * 60)
    print()

def check_port(port):
    """Check if a port is available."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

def start_langgraph_service():
    """Start the LangGraph service."""
    print("📡 Starting LangGraph Service on port 5001...")
    
    # Check if port is available
    if not check_port(5001):
        print("⚠️  Port 5001 is already in use. LangGraph service might already be running.")
        return None
    
    try:
        process = subprocess.Popen([
            sys.executable, "langgraph_service.py"
        ], cwd=Path(__file__).parent)
        
        # Give it time to start
        time.sleep(3)
        
        if process.poll() is None:
            print("✅ LangGraph Service started successfully")
            return process
        else:
            print("❌ Failed to start LangGraph Service")
            return None
            
    except Exception as e:
        print(f"❌ Error starting LangGraph Service: {e}")
        return None

def start_web_ui():
    """Start the web UI server."""
    print("🌐 Starting Web UI on port 3000...")
    
    # Check if port is available
    if not check_port(3000):
        print("⚠️  Port 3000 is already in use. Please stop the existing service.")
        return None
    
    try:
        process = subprocess.Popen([
            sys.executable, "web_app.py"
        ], cwd=Path(__file__).parent)
        
        # Give it time to start
        time.sleep(2)
        
        if process.poll() is None:
            print("✅ Web UI started successfully")
            return process
        else:
            print("❌ Failed to start Web UI")
            return None
            
    except Exception as e:
        print(f"❌ Error starting Web UI: {e}")
        return None

def check_prerequisites():
    """Check if all prerequisites are met."""
    print("🔍 Checking prerequisites...")
    
    # Check if .env file exists
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        print("⚠️  .env file not found. Please create one with your OpenAI API key.")
        print("   Copy .env.example to .env and fill in your API key.")
        return False
    
    # Check if required files exist
    required_files = ["langgraph_service.py", "web_app.py", "index.html", "styles.css", "script.js"]
    for file in required_files:
        if not (Path(__file__).parent / file).exists():
            print(f"❌ Required file missing: {file}")
            return False
    
    print("✅ Prerequisites check passed")
    return True

def main():
    """Main function to start all services."""
    print_banner()
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites check failed. Please fix the issues above.")
        sys.exit(1)
    
    processes = []
    
    try:
        # Start LangGraph service
        langgraph_process = start_langgraph_service()
        if langgraph_process:
            processes.append(langgraph_process)
        
        # Start Web UI
        web_process = start_web_ui()
        if web_process:
            processes.append(web_process)
        
        if not processes:
            print("\n❌ Failed to start any services. Exiting.")
            sys.exit(1)
        
        print("\n" + "=" * 60)
        print("🎉 ERP Chatbot Web UI is ready!")
        print("=" * 60)
        print()
        print("📍 Services running:")
        if langgraph_process:
            print("   • LangGraph Service: http://localhost:5001")
        if web_process:
            print("   • Web UI: http://localhost:3000")
        print()
        print("🌐 Open your browser and go to: http://localhost:3000")
        print()
        print("📋 Make sure these are also running:")
        print("   • MCP Server: http://localhost:8000")
        print("   • PostgreSQL database")
        print()
        print("Press Ctrl+C to stop all services")
        print("=" * 60)
        
        # Wait for processes
        def signal_handler(sig, frame):
            print("\n\n🛑 Shutting down services...")
            for process in processes:
                if process.poll() is None:
                    process.terminate()
            print("✅ All services stopped")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep the script running
        while True:
            time.sleep(1)
            # Check if any process has died
            for process in processes[:]:
                if process.poll() is not None:
                    print(f"⚠️  A service has stopped unexpectedly")
                    processes.remove(process)
            
            if not processes:
                print("❌ All services have stopped. Exiting.")
                break
                
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down services...")
        for process in processes:
            if process.poll() is None:
                process.terminate()
        print("✅ All services stopped")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        for process in processes:
            if process.poll() is None:
                process.terminate()
        sys.exit(1)

if __name__ == "__main__":
    main()