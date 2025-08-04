#!/usr/bin/env python3
"""
Startup script for the MCP server.
"""

import uvicorn
import logging
import sys
import os
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Start the MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Check if .env file exists
    env_file = Path(__file__).parent / '.env'
    if not env_file.exists():
        print("⚠️  .env file not found. Creating from .env.example...")
        example_file = Path(__file__).parent / '.env.example'
        if example_file.exists():
            import shutil
            shutil.copy(example_file, env_file)
            print("✅ Created .env file. Please edit it with your database credentials.")
        else:
            print("❌ .env.example file not found. Please create .env manually.")
            return 1
    
    print("🚀 Starting MCP Database Server...")
    print("📍 Server will be available at: http://localhost:8000")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("❤️  Health Check: http://localhost:8000/health")
    print("🔧 MCP Endpoint: http://localhost:8000/mcp")
    print("\nPress Ctrl+C to stop the server")
    
    try:
        uvicorn.run(
            "server:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Server error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())