#!/usr/bin/env python3
"""
Startup script for the MCP server.
"""

import logging
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        import uvicorn
        
        # Get port from environment or default
        port = int(os.getenv("MCP_PORT", "8000"))
        
        logger = logging.getLogger(__name__)
        logger.info(f"Starting MCP Database Server on port {port}")
        
        uvicorn.run(
            "mcp_server.server:app",
            host="0.0.0.0",
            port=port,
            reload=False,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Server error: {e}")
        sys.exit(1)