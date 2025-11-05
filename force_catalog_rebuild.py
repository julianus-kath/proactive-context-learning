"""
Force MCP Catalog Rebuild

This script forces the MCP server to rebuild its catalog with accurate row counts.
Run this after consolidating scout_runner.py to refresh the catalog.
"""
import asyncio
import requests
import sys

MCP_URL = "http://localhost:8000"

async def main():
    print("🔄 Forcing MCP catalog rebuild...")
    print(f"   MCP Server: {MCP_URL}")
    
    try:
        # Try to call refresh endpoint
        response = requests.post(f"{MCP_URL}/refresh_catalog", timeout=120)
        
        if response.status_code == 200:
            print("✅ Catalog refresh triggered successfully!")
            data = response.json()
            print(f"   Tables indexed: {data.get('tables_count', 'unknown')}")
            print(f"   Build time: {data.get('build_time_seconds', 'unknown')}s")
        else:
            print(f"❌ Refresh failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return 1
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to MCP server")
        print(f"   Is it running at {MCP_URL}?")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    print("\n✅ Done! The catalog should now have accurate row counts.")
    print("   Test with: 'How many customers do we have?'")
    print("   Expected: Should use KHKAdressen (419 rows), not archive tables!")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

