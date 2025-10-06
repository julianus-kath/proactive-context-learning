#!/usr/bin/env python3
"""
Phase 4 Verification Script

This script verifies that Phase 4 (MCP Discovery Tools) is properly implemented
and all components are working correctly.

Usage:
    python scripts/verify_phase4.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def verify_imports():
    """Verify all Phase 4 modules can be imported."""
    print("=" * 80)
    print("PHASE 4 VERIFICATION")
    print("=" * 80)
    print()
    
    print("1. Verifying imports...")
    try:
        from mcp_server.discovery_tools import (
            DiscoveryTools,
            ResponseCache,
            RateLimiter,
            DiscoveryResponse,
            PageInfo,
            TableSummary
        )
        print("   ✅ discovery_tools.py - All classes imported successfully")
    except ImportError as e:
        print(f"   ❌ discovery_tools.py - Import failed: {e}")
        return False
    
    try:
        from mcp_server.tools import MCPTools
        print("   ✅ tools.py - MCPTools imported successfully")
    except ImportError as e:
        print(f"   ❌ tools.py - Import failed: {e}")
        return False
    
    try:
        from models import MCPTool, MCPToolResult
        print("   ✅ models.py - MCP models imported successfully")
    except ImportError as e:
        print(f"   ❌ models.py - Import failed: {e}")
        return False
    
    print()
    return True


def verify_tools_registered():
    """Verify Phase 4 tools are registered in MCPTools."""
    print("2. Verifying tool registration...")
    
    try:
        from mcp_server.tools import MCPTools
        
        tools = MCPTools.get_available_tools()
        tool_names = [tool.name for tool in tools]
        
        required_tools = ["list_tables", "search_tables", "describe_table", "list_relations"]
        
        for tool_name in required_tools:
            if tool_name in tool_names:
                print(f"   ✅ {tool_name} - Registered")
            else:
                print(f"   ❌ {tool_name} - NOT registered")
                return False
        
        print()
        return True
        
    except Exception as e:
        print(f"   ❌ Tool registration check failed: {e}")
        print()
        return False


def verify_tool_schemas():
    """Verify Phase 4 tools have proper input schemas."""
    print("3. Verifying tool schemas...")
    
    try:
        from mcp_server.tools import MCPTools
        
        tools = MCPTools.get_available_tools()
        phase4_tools = {
            "list_tables": ["page", "page_size", "schema", "pattern"],
            "search_tables": ["query", "page", "page_size"],
            "describe_table": ["table_name", "include_sample"],
            "list_relations": ["table_name"]
        }
        
        for tool in tools:
            if tool.name in phase4_tools:
                schema = tool.inputSchema
                properties = schema.get("properties", {})
                expected_params = phase4_tools[tool.name]
                
                all_present = all(param in properties for param in expected_params)
                
                if all_present:
                    print(f"   ✅ {tool.name} - Schema valid ({len(expected_params)} parameters)")
                else:
                    missing = [p for p in expected_params if p not in properties]
                    print(f"   ❌ {tool.name} - Missing parameters: {missing}")
                    return False
        
        print()
        return True
        
    except Exception as e:
        print(f"   ❌ Schema verification failed: {e}")
        print()
        return False


def verify_discovery_tools_class():
    """Verify DiscoveryTools class has all required methods."""
    print("4. Verifying DiscoveryTools class...")
    
    try:
        from mcp_server.discovery_tools import DiscoveryTools
        
        required_methods = [
            "list_tables",
            "search_tables",
            "describe_table",
            "list_relations",
            "clear_cache",
            "get_cache_stats",
            "get_rate_limiter_stats"
        ]
        
        for method_name in required_methods:
            if hasattr(DiscoveryTools, method_name):
                print(f"   ✅ {method_name} - Method exists")
            else:
                print(f"   ❌ {method_name} - Method NOT found")
                return False
        
        print()
        return True
        
    except Exception as e:
        print(f"   ❌ DiscoveryTools verification failed: {e}")
        print()
        return False


def verify_cache_and_rate_limiter():
    """Verify ResponseCache and RateLimiter classes."""
    print("5. Verifying ResponseCache and RateLimiter...")
    
    try:
        from mcp_server.discovery_tools import ResponseCache, RateLimiter
        
        # Test ResponseCache
        cache = ResponseCache(ttl=300)
        test_response = {"ok": True, "data": "test"}
        
        # Test cache miss
        result = cache.get("test_tool", {"arg": "value"})
        if result is None:
            print("   ✅ ResponseCache - Cache miss works")
        else:
            print("   ❌ ResponseCache - Cache miss failed")
            return False
        
        # Test cache set
        cache.set("test_tool", {"arg": "value"}, test_response)
        
        # Test cache hit
        result = cache.get("test_tool", {"arg": "value"})
        if result == test_response:
            print("   ✅ ResponseCache - Cache hit works")
        else:
            print("   ❌ ResponseCache - Cache hit failed")
            return False
        
        # Test cache stats
        stats = cache.get_stats()
        if "hits" in stats and "misses" in stats:
            print("   ✅ ResponseCache - Stats tracking works")
        else:
            print("   ❌ ResponseCache - Stats tracking failed")
            return False
        
        # Test RateLimiter
        limiter = RateLimiter(rate=10, burst_size=20)
        
        # Test allow request
        allowed, retry_after = limiter.allow_request()
        if allowed:
            print("   ✅ RateLimiter - Allow request works")
        else:
            print("   ❌ RateLimiter - Allow request failed")
            return False
        
        # Test stats
        stats = limiter.get_stats()
        if "total_requests" in stats and "throttled_requests" in stats:
            print("   ✅ RateLimiter - Stats tracking works")
        else:
            print("   ❌ RateLimiter - Stats tracking failed")
            return False
        
        print()
        return True
        
    except Exception as e:
        print(f"   ❌ Cache/RateLimiter verification failed: {e}")
        print()
        return False


def verify_data_structures():
    """Verify Phase 4 data structures."""
    print("6. Verifying data structures...")
    
    try:
        from mcp_server.discovery_tools import (
            DiscoveryResponse,
            PageInfo,
            TableSummary
        )
        
        # Test PageInfo
        page_info = PageInfo(
            page=1,
            page_size=25,
            total_items=100,
            total_pages=4,
            has_next=True,
            has_prev=False
        )
        print("   ✅ PageInfo - Structure valid")
        
        # Test TableSummary
        table_summary = TableSummary(
            schema="public",
            name="customers",
            full_name="public.customers",
            type="BASE TABLE",
            estimated_rows=1000,
            column_count=10,
            has_foreign_keys=True,
            has_primary_keys=True
        )
        print("   ✅ TableSummary - Structure valid")
        
        # Test DiscoveryResponse
        response = DiscoveryResponse(
            ok=True,
            data={"test": "data"},
            error=None,
            error_code=None,
            execution_time_ms=1.5,
            cached=False,
            page_info=page_info
        )
        
        # Test to_dict method
        response_dict = response.to_dict()
        if "ok" in response_dict and "data" in response_dict:
            print("   ✅ DiscoveryResponse - Structure valid and to_dict() works")
        else:
            print("   ❌ DiscoveryResponse - to_dict() failed")
            return False
        
        print()
        return True
        
    except Exception as e:
        print(f"   ❌ Data structure verification failed: {e}")
        print()
        return False


def verify_tests():
    """Verify Phase 4 tests exist and can be imported."""
    print("7. Verifying test suite...")
    
    try:
        import tests.test_phase4_discovery
        print("   ✅ test_phase4_discovery.py - Test module imported successfully")
        
        # Count test classes
        test_classes = [
            "TestResponseCache",
            "TestRateLimiter",
            "TestListTables",
            "TestSearchTables",
            "TestDescribeTable",
            "TestListRelations",
            "TestCatalogNotInitialized"
        ]
        
        for test_class in test_classes:
            if hasattr(tests.test_phase4_discovery, test_class):
                print(f"   ✅ {test_class} - Test class exists")
            else:
                print(f"   ❌ {test_class} - Test class NOT found")
                return False
        
        print()
        return True
        
    except ImportError as e:
        print(f"   ❌ Test suite import failed: {e}")
        print()
        return False


def verify_documentation():
    """Verify Phase 4 documentation exists."""
    print("8. Verifying documentation...")
    
    docs = [
        "PHASE_4_COMPLETE.md",
        "PHASE_4_READY.md",
        "PHASE_4_SUMMARY.md"
    ]
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    for doc in docs:
        doc_path = os.path.join(project_root, doc)
        if os.path.exists(doc_path):
            size_kb = os.path.getsize(doc_path) / 1024
            print(f"   ✅ {doc} - Exists ({size_kb:.1f} KB)")
        else:
            print(f"   ❌ {doc} - NOT found")
            return False
    
    print()
    return True


def print_summary(results):
    """Print verification summary."""
    print("=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print()
    
    total = len(results)
    passed = sum(results.values())
    failed = total - passed
    
    for check, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {check}")
    
    print()
    print(f"Total: {passed}/{total} checks passed")
    
    if failed == 0:
        print()
        print("🎉 Phase 4 verification SUCCESSFUL!")
        print()
        print("Next steps:")
        print("  1. Run unit tests: python -m pytest tests/test_phase4_discovery.py -v")
        print("  2. Run integration tests with real database")
        print("  3. Update LangGraph to use new discovery tools")
        print("  4. Test end-to-end system")
        print()
        return True
    else:
        print()
        print(f"⚠️  Phase 4 verification FAILED ({failed} checks failed)")
        print()
        print("Please review the failed checks above and fix any issues.")
        print()
        return False


def main():
    """Run all verification checks."""
    results = {
        "Imports": verify_imports(),
        "Tool Registration": verify_tools_registered(),
        "Tool Schemas": verify_tool_schemas(),
        "DiscoveryTools Class": verify_discovery_tools_class(),
        "Cache & Rate Limiter": verify_cache_and_rate_limiter(),
        "Data Structures": verify_data_structures(),
        "Test Suite": verify_tests(),
        "Documentation": verify_documentation()
    }
    
    success = print_summary(results)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()