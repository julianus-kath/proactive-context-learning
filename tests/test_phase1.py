#!/usr/bin/env python3
"""
Phase 1 Test Script - Validate Direct Database Connectors

Tests:
1. Configuration validation
2. Connector initialization
3. Connection health checks
4. Basic query execution
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set environment for testing
os.environ.setdefault("DB_DIALECT", "postgres")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DATABASE", "synthetic_erp_data")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "")


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_success(text: str):
    """Print success message."""
    print(f"✅ {text}")


def print_error(text: str):
    """Print error message."""
    print(f"❌ {text}")


def print_info(text: str):
    """Print info message."""
    print(f"ℹ️  {text}")


async def test_config():
    """Test configuration loading."""
    print_header("Test 1: Configuration")
    
    try:
        from mcp_server.config import config
        
        print_info(f"DB_DIALECT: {config.db_dialect}")
        
        if config.db_dialect == "postgres":
            print_info(f"POSTGRES_HOST: {config.postgres_host}")
            print_info(f"POSTGRES_PORT: {config.postgres_port}")
            print_info(f"POSTGRES_DATABASE: {config.postgres_database}")
            print_info(f"POSTGRES_USER: {config.postgres_user}")
        elif config.db_dialect == "mssql":
            print_info(f"MSSQL_SERVER: {config.mssql_server}")
            print_info(f"MSSQL_DATABASE: {config.mssql_database}")
            print_info(f"MSSQL_USER: {config.mssql_user}")
        
        print_info(f"MAX_QUERY_RESULTS: {config.max_query_results}")
        print_info(f"QUERY_TIMEOUT: {config.query_timeout}")
        
        # Validate configuration
        config.validate()
        print_success("Configuration loaded and validated")
        return True
        
    except Exception as e:
        print_error(f"Configuration failed: {e}")
        return False


async def test_connector_init():
    """Test connector initialization."""
    print_header("Test 2: Connector Initialization")
    
    try:
        from mcp_server.database_adapter import DatabaseAdapter
        
        adapter = DatabaseAdapter()
        print_info(f"Dialect: {adapter.dialect}")
        print_info(f"Connector: {type(adapter.connector).__name__}")
        print_success("Connector initialized")
        return adapter
        
    except Exception as e:
        print_error(f"Connector initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_connection(adapter):
    """Test database connection."""
    print_header("Test 3: Connection Health Check")
    
    try:
        await adapter.initialize()
        print_success("Connection established and verified")
        return True
        
    except Exception as e:
        print_error(f"Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_query(adapter):
    """Test basic query execution."""
    print_header("Test 4: Query Execution")
    
    try:
        # Test simple query
        result = await adapter.fetch("SELECT 1 as test", limit=1)
        
        if result and len(result) > 0:
            print_info(f"Query result: {result}")
            print_success("Query executed successfully")
            return True
        else:
            print_error("Query returned no results")
            return False
        
    except Exception as e:
        print_error(f"Query failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_schema_fetch(adapter):
    """Test schema fetching."""
    print_header("Test 5: Schema Discovery")
    
    try:
        import time
        
        start = time.time()
        schema = await adapter.fetch_schema()
        elapsed = time.time() - start
        
        print_info(f"Tables found: {len(schema)}")
        print_info(f"Time taken: {elapsed:.2f}s")
        
        if schema:
            # Show first few tables
            print_info("Sample tables:")
            for table in schema[:3]:
                table_name = table.get('name', 'unknown')
                col_count = len(table.get('columns', []))
                print_info(f"  - {table_name} ({col_count} columns)")
        
        # Test cache
        print_info("\nTesting cache...")
        start = time.time()
        schema2 = await adapter.fetch_schema()
        elapsed2 = time.time() - start
        
        print_info(f"Cached fetch time: {elapsed2:.2f}s")
        
        if elapsed2 < 0.1:
            print_success("Schema caching works!")
        else:
            print_error("Schema caching may not be working")
        
        print_success(f"Schema discovery completed ({len(schema)} tables)")
        return True
        
    except Exception as e:
        print_error(f"Schema fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_cache_stats(adapter):
    """Test cache statistics."""
    print_header("Test 6: Cache Statistics")
    
    try:
        stats = adapter.get_cache_stats()
        
        print_info(f"Cache age: {stats['age_s']}s")
        print_info(f"Cache hits: {stats['hits']}")
        print_info(f"Cache TTL: {stats['ttl']}s")
        
        print_success("Cache statistics retrieved")
        return True
        
    except Exception as e:
        print_error(f"Cache stats failed: {e}")
        return False


async def main():
    """Run all tests."""
    print_header("Phase 1 Validation Tests")
    print_info(f"Testing dialect: {os.getenv('DB_DIALECT', 'postgres')}")
    
    results = []
    adapter = None
    
    # Test 1: Configuration
    results.append(await test_config())
    
    # Test 2: Connector initialization
    adapter = await test_connector_init()
    results.append(adapter is not None)
    
    if adapter:
        # Test 3: Connection
        results.append(await test_connection(adapter))
        
        # Test 4: Query execution
        results.append(await test_query(adapter))
        
        # Test 5: Schema discovery
        results.append(await test_schema_fetch(adapter))
        
        # Test 6: Cache statistics
        results.append(await test_cache_stats(adapter))
        
        # Cleanup
        try:
            await adapter.close()
            print_info("\nConnection closed")
        except Exception as e:
            print_error(f"Cleanup failed: {e}")
    
    # Summary
    print_header("Test Summary")
    passed = sum(results)
    total = len(results)
    
    print_info(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print_success("All tests passed! Phase 1 is working correctly.")
        return 0
    else:
        print_error(f"{total - passed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)