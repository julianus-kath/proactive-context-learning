#!/usr/bin/env python3
"""
Debug version of startup indexing demo.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Add the project root to the path
sys.path.append(os.path.dirname(__file__))

# Load environment variables
load_dotenv()

from langgraph_integration.direct_db_client import (
    get_all_schemas, 
    index_database,
    health_check
)

async def debug_startup():
    """Debug the startup process."""
    print("🔍 Debug Startup Indexing")
    print("="*50)
    
    try:
        # Test health check
        print("\n1️⃣ Health check...")
        is_healthy = await health_check()
        print(f"Health: {'✅' if is_healthy else '❌'}")
        
        # Test schema discovery
        print("\n2️⃣ Schema discovery...")
        schemas = await get_all_schemas()
        print(f"Schemas found: {schemas}")
        
        # Test database indexing
        print("\n3️⃣ Database indexing...")
        index_info = await index_database()
        print(f"Index info: {index_info}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_startup())