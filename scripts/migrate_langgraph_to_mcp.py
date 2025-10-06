#!/usr/bin/env python3
"""
LangGraph to MCP Migration Script

This script helps migrate LangGraph from using the old Flask proxy
to using the MCP server as the single database gateway.

Phase 1.5 of the MCP-First Migration
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")


def print_success(text: str):
    """Print success message."""
    print(f"✅ {text}")


def print_error(text: str):
    """Print error message."""
    print(f"❌ {text}")


def print_info(text: str):
    """Print info message."""
    print(f"ℹ️  {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"⚠️  {text}")


def analyze_proxy_client():
    """Analyze the proxy_db_client.py to understand what needs to be migrated."""
    print_header("Step 1: Analyzing proxy_db_client.py")
    
    proxy_client_path = project_root / "langgraph_integration" / "proxy_db_client.py"
    
    if not proxy_client_path.exists():
        print_error(f"File not found: {proxy_client_path}")
        return None
    
    with open(proxy_client_path, 'r') as f:
        content = f.read()
    
    # Find all function definitions
    import re
    functions = re.findall(r'^(?:async )?def (\w+)\(', content, re.MULTILINE)
    
    print_info(f"Found {len(functions)} functions in proxy_db_client.py:")
    for func in functions:
        print(f"  • {func}()")
    
    return functions


def analyze_mcp_client():
    """Analyze the mcp_client.py to see what's already implemented."""
    print_header("Step 2: Analyzing mcp_client.py")
    
    mcp_client_path = project_root / "langgraph_integration" / "mcp_client.py"
    
    if not mcp_client_path.exists():
        print_error(f"File not found: {mcp_client_path}")
        return None
    
    with open(mcp_client_path, 'r') as f:
        content = f.read()
    
    # Find all function definitions
    import re
    functions = re.findall(r'^(?:async )?def (\w+)\(', content, re.MULTILINE)
    
    print_info(f"Found {len(functions)} functions in mcp_client.py:")
    for func in functions:
        print(f"  • {func}()")
    
    return functions


def compare_clients(proxy_funcs, mcp_funcs):
    """Compare the two clients and identify gaps."""
    print_header("Step 3: Comparing Clients")
    
    if not proxy_funcs or not mcp_funcs:
        print_error("Cannot compare - missing function lists")
        return
    
    # Filter out private functions and class methods
    proxy_public = [f for f in proxy_funcs if not f.startswith('_') and f != 'ProxyDatabaseClient']
    mcp_public = [f for f in mcp_funcs if not f.startswith('_') and f != 'MCPDatabaseTool']
    
    # Find functions in proxy but not in MCP
    missing = set(proxy_public) - set(mcp_public)
    
    # Find functions in both
    common = set(proxy_public) & set(mcp_public)
    
    print_success(f"Functions available in both clients: {len(common)}")
    for func in sorted(common):
        print(f"  ✅ {func}()")
    
    if missing:
        print_warning(f"\nFunctions in proxy_db_client but NOT in mcp_client: {len(missing)}")
        for func in sorted(missing):
            print(f"  ⚠️  {func}()")
        print_info("\nThese functions need to be:")
        print_info("  1. Implemented in mcp_client.py, OR")
        print_info("  2. Removed from graph_definition.py if not used, OR")
        print_info("  3. Refactored to use existing MCP functions")
    else:
        print_success("\nAll proxy functions are available in MCP client!")


def analyze_graph_definition():
    """Analyze graph_definition.py to see what functions it uses."""
    print_header("Step 4: Analyzing graph_definition.py Usage")
    
    graph_def_path = project_root / "langgraph_integration" / "graph_definition.py"
    
    if not graph_def_path.exists():
        print_error(f"File not found: {graph_def_path}")
        return None
    
    with open(graph_def_path, 'r') as f:
        content = f.read()
    
    # Find the import statement
    import re
    import_match = re.search(
        r'from \.proxy_db_client import \((.*?)\)',
        content,
        re.DOTALL
    )
    
    if import_match:
        imports = import_match.group(1)
        # Clean up and split
        imported_funcs = [
            func.strip().strip(',')
            for func in imports.split('\n')
            if func.strip() and not func.strip().startswith('#')
        ]
        
        print_info(f"graph_definition.py imports {len(imported_funcs)} functions:")
        for func in imported_funcs:
            print(f"  • {func}")
        
        return imported_funcs
    else:
        print_warning("Could not find proxy_db_client import in graph_definition.py")
        return None


def check_mcp_server():
    """Check if MCP server is running."""
    print_header("Step 5: Checking MCP Server")
    
    import requests
    
    mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
    
    try:
        response = requests.get(f"{mcp_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"MCP server is running at {mcp_url}")
            print_info(f"Status: {data}")
            return True
        else:
            print_error(f"MCP server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error(f"Cannot connect to MCP server at {mcp_url}")
        print_info("Start the server with: cd mcp_server && python server.py")
        return False
    except Exception as e:
        print_error(f"Error checking MCP server: {e}")
        return False


def generate_migration_plan(proxy_funcs, mcp_funcs, used_funcs):
    """Generate a migration plan."""
    print_header("Step 6: Migration Plan")
    
    if not all([proxy_funcs, mcp_funcs, used_funcs]):
        print_error("Cannot generate plan - missing data")
        return
    
    # Filter out private functions
    mcp_public = set(f for f in mcp_funcs if not f.startswith('_') and f != 'MCPDatabaseTool')
    
    # Check each used function
    ready = []
    needs_impl = []
    
    for func in used_funcs:
        if func in mcp_public:
            ready.append(func)
        else:
            needs_impl.append(func)
    
    print_info("Migration Readiness:")
    print(f"\n  ✅ Ready to migrate: {len(ready)}/{len(used_funcs)}")
    for func in ready:
        print(f"     • {func}()")
    
    if needs_impl:
        print(f"\n  ⚠️  Need implementation: {len(needs_impl)}/{len(used_funcs)}")
        for func in needs_impl:
            print(f"     • {func}()")
    
    # Calculate readiness percentage
    readiness = (len(ready) / len(used_funcs) * 100) if used_funcs else 0
    
    print(f"\n{'='*70}")
    print(f"  Migration Readiness: {readiness:.1f}%")
    print(f"{'='*70}")
    
    if readiness == 100:
        print_success("\n🎉 All functions are ready! You can proceed with migration.")
        print_info("\nNext steps:")
        print_info("  1. Update graph_definition.py to import from mcp_client")
        print_info("  2. Test with: python langgraph_integration/test_flow.py")
        print_info("  3. Run end-to-end tests")
    elif readiness >= 80:
        print_warning("\n⚠️  Almost ready! A few functions need implementation.")
        print_info("\nOptions:")
        print_info("  A. Implement missing functions in mcp_client.py")
        print_info("  B. Refactor graph_definition.py to use existing functions")
        print_info("  C. Remove unused functions from imports")
    else:
        print_error("\n❌ Significant work needed before migration.")
        print_info("\nRecommendation:")
        print_info("  1. Implement missing functions in mcp_client.py")
        print_info("  2. Or refactor graph_definition.py to simplify dependencies")


def main():
    """Run the migration analysis."""
    print_header("LangGraph to MCP Migration Analysis")
    print_info("This script analyzes the current state and provides a migration plan.")
    
    # Step 1: Analyze proxy client
    proxy_funcs = analyze_proxy_client()
    
    # Step 2: Analyze MCP client
    mcp_funcs = analyze_mcp_client()
    
    # Step 3: Compare clients
    if proxy_funcs and mcp_funcs:
        compare_clients(proxy_funcs, mcp_funcs)
    
    # Step 4: Analyze what graph_definition.py actually uses
    used_funcs = analyze_graph_definition()
    
    # Step 5: Check if MCP server is running
    mcp_running = check_mcp_server()
    
    # Step 6: Generate migration plan
    if proxy_funcs and mcp_funcs and used_funcs:
        generate_migration_plan(proxy_funcs, mcp_funcs, used_funcs)
    
    # Final summary
    print_header("Summary")
    
    if mcp_running:
        print_success("MCP server is running and ready")
    else:
        print_warning("MCP server needs to be started")
    
    print_info("\nFor detailed documentation, see:")
    print_info("  • docs/PHASE_1_STATUS.md")
    print_info("  • docs/PHASE_1_COMPLETE.md")
    
    print_info("\nFor questions or issues, review the troubleshooting section in:")
    print_info("  • docs/PHASE_1_STATUS.md")
    
    print("\n")


if __name__ == "__main__":
    main()