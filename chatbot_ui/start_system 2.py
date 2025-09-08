#!/usr/bin/env python3
"""
Start the complete ERP Assistant system
"""

import os
import sys
import time
import subprocess
import signal
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

def start_langgraph_service():
    """Start the LangGraph service."""
    print("🚀 Starting LangGraph Service...")
    
    # Change to the chatbot_ui directory
    os.chdir(Path(__file__).parent)
    
    try:
        # Test that everything imports correctly first
        from langgraph_integration.graph_definition import create_database_workflow
        workflow = create_database_workflow()
        print("✅ LangGraph workflow initialized successfully")
        
        # Start the FastAPI service
        import uvicorn
        from langgraph_service import app
        
        print("🌐 Starting FastAPI server on http://localhost:5001")
        uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
        
    except Exception as e:
        print(f"❌ Failed to start LangGraph service: {e}")
        import traceback
        traceback.print_exc()
        return False

def start_streamlit_ui():
    """Start the Streamlit UI."""
    print("🎨 Starting Streamlit UI...")
    
    try:
        # Change to the chatbot_ui directory
        os.chdir(Path(__file__).parent)
        
        # Start Streamlit
        cmd = [sys.executable, "-m", "streamlit", "run", "app.py", 
               "--server.port", "8501", "--server.address", "0.0.0.0"]
        
        print("🌐 Starting Streamlit on http://localhost:8501")
        subprocess.run(cmd)
        
    except Exception as e:
        print(f"❌ Failed to start Streamlit: {e}")
        return False

def main():
    """Main function to start the system."""
    print("🎯 ERP Assistant System Startup")
    print("=" * 40)
    
    # Check if we should start both services or just one
    if len(sys.argv) > 1:
        service = sys.argv[1].lower()
        if service == "langgraph":
            start_langgraph_service()
        elif service == "streamlit":
            start_streamlit_ui()
        else:
            print("Usage: python start_system.py [langgraph|streamlit]")
    else:
        print("Starting LangGraph service...")
        print("Run 'python start_system.py streamlit' in another terminal for the UI")
        start_langgraph_service()

if __name__ == "__main__":
    main()